from __future__ import annotations

"""API-side story persistence and process-based run lifecycle management."""

import json
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from config import DEFAULT_MODEL, OUTPUTS_DIR, STORIES_DIR
from schemas import ResearchStory

from .models import (
    RunArtifactResponse,
    RunDetailResponse,
    RunItemResponse,
    RunOverviewResponse,
    RunReviewStateResponse,
    SectionStateResponse,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return _read_json(path)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _combine_files(paths: list[Path]) -> str:
    chunks: list[str] = []
    for path in sorted(paths):
        chunks.append(f"# {path.name}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def _map_section_status(status: str) -> str:
    mapping = {
        "pending": "pending",
        "drafted": "writing",
        "needs_revision": "revise",
        "approved": "approved",
        "manual_review": "manual_review",
    }
    return mapping.get(status, status)


def _map_run_status(status: str | None) -> str:
    """Map persisted final status values to frontend statuses."""
    if status in {None, "", "running"}:
        return "running"
    if status == "rendered":
        return "completed"
    if status in {"completed", "failed", "stopped", "stopping", "pending"}:
        return status
    return "failed"


def _count_workflow_warnings(contract_payload: dict[str, Any]) -> int:
    return len((contract_payload.get("global_status") or {}).get("warnings", []))


def _build_stop_payload(*, requested_at: str) -> dict[str, str]:
    return {
        "message": "Run was stopped by user request.",
        "requested_at": requested_at,
    }


def _build_summary_snapshot(output_dir: Path, *, final_status: str) -> dict[str, Any]:
    state_payload = _read_json_if_exists(output_dir / "logs" / "run_state.json") or {}
    runtime = state_payload.get("runtime", {})
    evaluation = _read_json_if_exists(output_dir / "logs" / "evaluation.json") or {}
    rendered_path = output_dir / "rendered" / "final_manuscript.md"
    return {
        "run_id": output_dir.name,
        "final_status": final_status,
        "completed_sections": runtime.get("completed_sections", []),
        "rewrite_count": runtime.get("rewrite_count", {}),
        "needs_manual_review": runtime.get("needs_manual_review", []),
        "render_warnings": [],
        "evaluation_overall_score": evaluation.get("overall_score"),
        "evaluation_risks": evaluation.get("risks", []),
        "output_dir": str(output_dir),
        "has_rendered_manuscript": rendered_path.exists(),
    }


def _load_error_message(output_dir: Path) -> str | None:
    error_payload = _read_json_if_exists(output_dir / "logs" / "error.json")
    if isinstance(error_payload, dict):
        return error_payload.get("message")
    summary_payload = _read_json_if_exists(output_dir / "logs" / "run_summary.json") or {}
    if not summary_payload and (output_dir / "logs" / "run_state.json").exists():
        return "Run metadata is incomplete. This run is not active in the current server process."
    return None


def _launch_run_process(story_path: Path, output_dir: Path, model: str) -> subprocess.Popen[str]:
    stdout_path = output_dir / "logs" / "worker_stdout.log"
    stderr_path = output_dir / "logs" / "worker_stderr.log"
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "api.run_job",
            "--story",
            str(story_path),
            "--output-dir",
            str(output_dir),
            "--model",
            model,
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
        creationflags=creationflags,
    )


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        process.send_signal(signal.SIGTERM)


@dataclass
class ActiveRun:
    run_id: str
    story_id: str
    model: str
    started_at: str
    updated_at: str
    output_dir: Path
    process: subprocess.Popen[str]
    stop_requested_at: str | None = None


class StoryRepository:
    def list(self) -> list[ResearchStory]:
        items: list[tuple[float, ResearchStory]] = []
        for path in STORIES_DIR.glob("*.json"):
            story = ResearchStory.from_path(path)
            items.append((path.stat().st_mtime, story))
        items.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in items]

    def save(self, story: ResearchStory) -> ResearchStory:
        path = STORIES_DIR / f"{story.story_id}.json"
        path.write_text(story.model_dump_json(indent=2), encoding="utf-8")
        return story


class RunRepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self._active_runs: dict[str, ActiveRun] = {}

    def _status_for_active(self, run: ActiveRun) -> str:
        return "stopping" if run.stop_requested_at else "running"

    def _reconcile_active(self, run_id: str, active: ActiveRun) -> str:
        if active.process.poll() is None:
            return self._status_for_active(active)

        final_status = "stopped" if active.stop_requested_at else ("failed" if active.process.returncode else "completed")
        if final_status in {"stopped", "failed"}:
            summary_path = active.output_dir / "logs" / "run_summary.json"
            if not summary_path.exists():
                _write_json(summary_path, _build_summary_snapshot(active.output_dir, final_status=final_status))

        with self._lock:
            self._active_runs.pop(run_id, None)
        return final_status

    def list(self) -> list[RunItemResponse]:
        items: dict[str, RunItemResponse] = {}

        if OUTPUTS_DIR.exists():
            for output_dir in sorted(OUTPUTS_DIR.iterdir(), reverse=True):
                if not output_dir.is_dir():
                    continue
                logs_dir = output_dir / "logs"
                summary_path = logs_dir / "run_summary.json"
                state_path = logs_dir / "run_state.json"
                error_path = logs_dir / "error.json"
                stop_path = logs_dir / "stop.json"
                if not any(path.exists() for path in (summary_path, state_path, error_path, stop_path)):
                    continue

                summary = _read_json_if_exists(summary_path) or {}
                story_payload = _read_json_if_exists(output_dir / "input_story.json") or {}
                story_id = story_payload.get("story_id", summary.get("run_id", output_dir.name).split("_20")[0])
                status = _map_run_status(summary.get("final_status")) if summary_path.exists() else ("failed" if error_path.exists() else "failed")
                latest_path = next((path for path in (summary_path, state_path, error_path, stop_path) if path.exists()), output_dir)

                items[output_dir.name] = RunItemResponse(
                    id=output_dir.name,
                    storyId=story_id,
                    model=DEFAULT_MODEL,
                    status=status,
                    startedAt=_format_mtime(output_dir),
                    updatedAt=_format_mtime(latest_path),
                    error=_load_error_message(output_dir),
                )

        with self._lock:
            active_items = list(self._active_runs.items())

        for run_id, active in active_items:
            status = self._reconcile_active(run_id, active)
            latest_path = next(
                (
                    path
                    for path in (
                        active.output_dir / "logs" / "run_summary.json",
                        active.output_dir / "logs" / "run_state.json",
                        active.output_dir / "logs" / "stop.json",
                        active.output_dir / "logs" / "error.json",
                    )
                    if path.exists()
                ),
                active.output_dir,
            )
            items[run_id] = RunItemResponse(
                id=run_id,
                storyId=active.story_id,
                model=active.model,
                status=status,
                startedAt=active.started_at,
                updatedAt=_format_mtime(latest_path) if latest_path.exists() else active.updated_at,
                error=_load_error_message(active.output_dir),
            )

        return sorted(items.values(), key=lambda item: item.updatedAt, reverse=True)

    def create(self, story: ResearchStory, model: str) -> RunDetailResponse:
        timestamp = datetime.now()
        run_id = f"{story.story_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        output_dir = OUTPUTS_DIR / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "drafts").mkdir(exist_ok=True)
        (output_dir / "reviews").mkdir(exist_ok=True)
        (output_dir / "rendered").mkdir(exist_ok=True)
        (output_dir / "logs").mkdir(exist_ok=True)

        story_path = STORIES_DIR / f"{story.story_id}.json"
        story_path.write_text(story.model_dump_json(indent=2), encoding="utf-8")

        process = _launch_run_process(story_path, output_dir, model)
        active = ActiveRun(
            run_id=run_id,
            story_id=story.story_id,
            model=model,
            started_at=timestamp.strftime("%Y-%m-%d %H:%M"),
            updated_at=timestamp.strftime("%Y-%m-%d %H:%M"),
            output_dir=output_dir,
            process=process,
        )
        with self._lock:
            self._active_runs[run_id] = active

        return self.get(run_id)

    def stop(self, run_id: str) -> RunDetailResponse:
        with self._lock:
            active = self._active_runs.get(run_id)
        if active is None:
            if (OUTPUTS_DIR / run_id).exists():
                raise RuntimeError("Run is not active in the current server process and cannot be stopped.")
            raise FileNotFoundError(run_id)
        if active.process.poll() is not None:
            raise RuntimeError("Run is no longer active.")
        if active.stop_requested_at:
            return self.get(run_id)

        requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        active.stop_requested_at = requested_at
        active.updated_at = requested_at[:16]
        _write_json(active.output_dir / "logs" / "stop.json", _build_stop_payload(requested_at=requested_at))
        _terminate_process(active.process)
        return self.get(run_id)

    def delete(self, run_id: str) -> None:
        output_dir = OUTPUTS_DIR / run_id
        with self._lock:
            active = self._active_runs.get(run_id)
        if active is not None and active.process.poll() is None:
            raise RuntimeError("Cannot delete a running run. Stop it first.")
        if active is None and not output_dir.exists():
            raise FileNotFoundError(run_id)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        with self._lock:
            self._active_runs.pop(run_id, None)

    def get(self, run_id: str) -> RunDetailResponse:
        output_dir = OUTPUTS_DIR / run_id
        with self._lock:
            active = self._active_runs.get(run_id)

        if active is not None:
            status = self._reconcile_active(run_id, active)
        elif not output_dir.exists():
            raise FileNotFoundError(run_id)
        else:
            summary_payload = _read_json_if_exists(output_dir / "logs" / "run_summary.json") or {}
            if summary_payload:
                status = _map_run_status(summary_payload.get("final_status"))
            else:
                status = "failed" if (output_dir / "logs" / "run_state.json").exists() else "failed"

        if not output_dir.exists():
            raise FileNotFoundError(run_id)

        state_payload = _read_json_if_exists(output_dir / "logs" / "run_state.json") or {}
        runtime = state_payload.get("runtime", {})
        state_artifacts = state_payload.get("artifacts", {})
        story_payload = _read_json_if_exists(output_dir / "input_story.json") or {}
        contract_payload = _read_json_if_exists(output_dir / "contract_final.json") or {}
        summary_payload = _read_json_if_exists(output_dir / "logs" / "run_summary.json") or {}

        sections = [
            SectionStateResponse(
                id=section["section_id"],
                title=section["title"],
                status=_map_section_status(section.get("status", "pending")),
                rewriteCount=runtime.get("rewrite_count", {}).get(section["section_id"], 0),
            )
            for section in contract_payload.get("sections", [])
        ]

        latest_review = state_artifacts.get("last_aggregate_feedback") or {}
        overview = RunOverviewResponse(
            finalStatus=summary_payload.get("final_status", status),
            contractState=(contract_payload.get("global_status") or {}).get("state", "unknown"),
            completedSections=len(runtime.get("completed_sections", [])),
            pendingSections=len(runtime.get("pending_sections", [])),
            manualReviewCount=len(runtime.get("needs_manual_review", [])),
            workflowWarningCount=_count_workflow_warnings(contract_payload),
            evaluationOverallScore=summary_payload.get("evaluation_overall_score"),
        )
        latest_review_state = RunReviewStateResponse(
            status=latest_review.get("status"),
            nextAction=state_artifacts.get("next_action"),
            issueCount=len(latest_review.get("issues", [])),
            patchCount=len(latest_review.get("patches", [])),
            deterministicChecks=latest_review.get("deterministic_checks", {}),
        )

        latest_path = next(
            (
                path
                for path in (
                    output_dir / "logs" / "run_summary.json",
                    output_dir / "logs" / "run_state.json",
                    output_dir / "logs" / "stop.json",
                    output_dir / "logs" / "error.json",
                )
                if path.exists()
            ),
            output_dir,
        )
        started_at = active.started_at if active is not None else _format_mtime(output_dir)
        updated_at = active.updated_at if active is not None else _format_mtime(latest_path)
        model = active.model if active is not None else DEFAULT_MODEL

        return RunDetailResponse(
            id=run_id,
            storyId=story_payload.get("story_id", run_id.split("_20")[0]),
            model=model,
            status=status,
            startedAt=started_at,
            updatedAt=updated_at,
            error=_load_error_message(output_dir),
            currentNode=runtime.get("next_node") or ("renderer" if status == "completed" else "orchestrator"),
            currentSectionId=runtime.get("current_section_id"),
            nextNode=runtime.get("next_node"),
            sections=sections,
            artifacts=self._build_artifacts(output_dir),
            overview=overview,
            latestReview=latest_review_state,
        )

    def _build_artifacts(self, output_dir: Path) -> list[RunArtifactResponse]:
        artifacts: list[RunArtifactResponse] = []
        single_files = [
            ("blueprint", "Blueprint", output_dir / "blueprint.json"),
            ("contract", "Contract", output_dir / "contract_final.json"),
        ]
        for artifact_id, label, path in single_files:
            artifacts.append(
                RunArtifactResponse(
                    id=artifact_id,
                    label=label,
                    kind=artifact_id,
                    content=path.read_text(encoding="utf-8") if path.exists() else "",
                )
            )

        artifacts.append(
            RunArtifactResponse(
                id="drafts",
                label="Drafts",
                kind="drafts",
                content=_combine_files(list((output_dir / "drafts").glob("*.md"))),
            )
        )
        artifacts.append(
            RunArtifactResponse(
                id="reviews",
                label="Reviews",
                kind="reviews",
                content=_combine_files(list((output_dir / "reviews").glob("*.json"))),
            )
        )

        manuscript_path = output_dir / "rendered" / "final_manuscript.md"
        artifacts.append(
            RunArtifactResponse(
                id="manuscript",
                label="Manuscript",
                kind="manuscript",
                content=manuscript_path.read_text(encoding="utf-8") if manuscript_path.exists() else "",
            )
        )

        evaluation_path = output_dir / "logs" / "evaluation.json"
        artifacts.append(
            RunArtifactResponse(
                id="evaluation",
                label="Evaluation",
                kind="evaluation",
                content=evaluation_path.read_text(encoding="utf-8") if evaluation_path.exists() else "",
            )
        )

        benchmark_path = output_dir / "logs" / "benchmark.json"
        artifacts.append(
            RunArtifactResponse(
                id="benchmark",
                label="Benchmark",
                kind="benchmark",
                content=benchmark_path.read_text(encoding="utf-8") if benchmark_path.exists() else "",
            )
        )

        log_files = [
            output_dir / "logs" / "run_summary.json",
            output_dir / "logs" / "run_state.json",
            output_dir / "logs" / "stop.json",
            output_dir / "logs" / "error.json",
            output_dir / "logs" / "worker_stdout.log",
            output_dir / "logs" / "worker_stderr.log",
        ]
        artifacts.append(
            RunArtifactResponse(
                id="logs",
                label="Logs",
                kind="logs",
                content=_combine_files([path for path in log_files if path.exists()]),
            )
        )
        return artifacts
