from __future__ import annotations

"""API 层的数据访问与运行管理。

这一层负责：
- 从 `data/stories/` 读取和保存 `ResearchStory`
- 从 `data/outputs/` 聚合 run 列表、run 详情和产物
- 在后台线程中启动一次真实 run，并把失败原因持久化出来
"""

import json
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from config import DEFAULT_MODEL, OUTPUTS_DIR, STORIES_DIR
from runner import run_story_to_proposal_sync
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
    """读取一个 UTF-8 JSON 文件并反序列化。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> Any | None:
    """如果文件存在则读取 JSON，否则返回 `None`。"""
    if not path.exists():
        return None
    return _read_json(path)


def _format_mtime(path: Path) -> str:
    """把文件修改时间格式化成前端可直接展示的字符串。"""
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _combine_files(paths: list[Path]) -> str:
    """把多份文件拼成一个文本块，便于前端一次性查看。"""
    chunks: list[str] = []
    for path in sorted(paths):
        chunks.append(f"# {path.name}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def _map_section_status(status: str) -> str:
    """把 contract 内部状态映射成前端使用的状态名。"""
    mapping = {
        "pending": "pending",
        "drafted": "writing",
        "needs_revision": "revise",
        "approved": "approved",
        "manual_review": "manual_review",
    }
    return mapping.get(status, status)


def _count_workflow_warnings(contract_payload: dict[str, Any]) -> int:
    """统计 contract / workflow 层面的 warning 数量。"""
    return len((contract_payload.get("global_status") or {}).get("warnings", []))


def _build_error_payload(exc: Exception) -> dict[str, str]:
    """构造一个可持久化、可暴露给前端的错误快照。"""
    return {
        "message": str(exc),
        "traceback": traceback.format_exc(),
        "failed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _load_error_message(output_dir: Path, active: "ActiveRun | None") -> str | None:
    """优先从活动 run 读取错误，回退到落盘的 error.json。"""
    if active is not None and active.error:
        return active.error
    error_payload = _read_json_if_exists(output_dir / "logs" / "error.json")
    if isinstance(error_payload, dict):
        return error_payload.get("message")
    return None


def _infer_run_status(
    output_dir: Path,
    summary_payload: dict[str, Any],
    active: "ActiveRun | None",
) -> str:
    """从活动状态、summary 和 error snapshot 推导 run 状态。"""
    if active is not None:
        return active.status
    if (output_dir / "logs" / "error.json").exists():
        return "failed"
    if summary_payload.get("final_status") == "rendered":
        return "completed"
    return "running"


@dataclass
class ActiveRun:
    """进程内维护的一条活动 run 记录。"""

    run_id: str
    story_id: str
    model: str
    started_at: str
    updated_at: str
    status: str
    output_dir: Path
    error: str | None = None


class StoryRepository:
    """管理 `ResearchStory` 的文件读写。"""

    def list(self) -> list[ResearchStory]:
        """读取 stories 目录下全部 story，并按修改时间倒序返回。"""
        items: list[tuple[float, ResearchStory]] = []
        for path in STORIES_DIR.glob("*.json"):
            story = ResearchStory.from_path(path)
            items.append((path.stat().st_mtime, story))
        items.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in items]

    def save(self, story: ResearchStory) -> ResearchStory:
        """把一份 `ResearchStory` 落盘到 stories 目录。"""
        path = STORIES_DIR / f"{story.story_id}.json"
        path.write_text(story.model_dump_json(indent=2), encoding="utf-8")
        return story


class RunRepository:
    """管理 run 的创建、跟踪和产物聚合。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active_runs: dict[str, ActiveRun] = {}

    def list(self) -> list[RunItemResponse]:
        """聚合历史输出目录和当前进程中的活动 run。"""
        items: dict[str, RunItemResponse] = {}

        if OUTPUTS_DIR.exists():
            for output_dir in sorted(OUTPUTS_DIR.iterdir(), reverse=True):
                if not output_dir.is_dir():
                    continue
                logs_dir = output_dir / "logs"
                summary_path = logs_dir / "run_summary.json"
                state_path = logs_dir / "run_state.json"
                error_path = logs_dir / "error.json"
                if not summary_path.exists() and not state_path.exists() and not error_path.exists():
                    continue

                summary = _read_json_if_exists(summary_path) or {}
                story_payload = _read_json_if_exists(output_dir / "input_story.json") or {}
                story_id = story_payload.get(
                    "story_id",
                    summary.get("run_id", output_dir.name).split("_20")[0],
                )
                status = _infer_run_status(output_dir, summary, None)

                items[output_dir.name] = RunItemResponse(
                    id=output_dir.name,
                    storyId=story_id,
                    model=DEFAULT_MODEL,
                    status=status,
                    startedAt=_format_mtime(output_dir),
                    updatedAt=_format_mtime(
                        summary_path if summary_path.exists() else (state_path if state_path.exists() else error_path)
                    ),
                    error=_load_error_message(output_dir, None),
                )

        # 活动 run 以内存状态为准，覆盖同名历史项。
        with self._lock:
            for run in self._active_runs.values():
                items[run.run_id] = RunItemResponse(
                    id=run.run_id,
                    storyId=run.story_id,
                    model=run.model,
                    status=run.status,
                    startedAt=run.started_at,
                    updatedAt=run.updated_at,
                    error=run.error,
                )

        return sorted(items.values(), key=lambda item: item.updatedAt, reverse=True)

    def create(self, story: ResearchStory, model: str) -> RunDetailResponse:
        """创建一个新 run，并在后台线程中启动。"""
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

        active = ActiveRun(
            run_id=run_id,
            story_id=story.story_id,
            model=model,
            started_at=timestamp.strftime("%Y-%m-%d %H:%M"),
            updated_at=timestamp.strftime("%Y-%m-%d %H:%M"),
            status="running",
            output_dir=output_dir,
        )
        with self._lock:
            self._active_runs[run_id] = active

        Thread(
            target=self._run_in_background,
            args=(story, output_dir, active),
            daemon=True,
        ).start()

        return self.get(run_id)

    def _run_in_background(self, story: ResearchStory, output_dir: Path, active: ActiveRun) -> None:
        """后台执行一次真实的 Story2Proposal run。"""
        try:
            run_story_to_proposal_sync(story, output_dir=output_dir, model=active.model)
            active.status = "completed"
        except Exception as exc:  # pragma: no cover
            active.status = "failed"
            active.error = str(exc)
            error_payload = _build_error_payload(exc)
            (output_dir / "logs" / "error.json").write_text(
                json.dumps(error_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            # 失败必须留在后端终端里，不能只在内存里吞掉。
            print(error_payload["traceback"])
        finally:
            active.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    def get(self, run_id: str) -> RunDetailResponse:
        """读取某个 run 的当前状态，并组装为前端详情响应。"""
        output_dir = OUTPUTS_DIR / run_id
        with self._lock:
            active = self._active_runs.get(run_id)

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

        status = _infer_run_status(output_dir, summary_payload, active)
        error_message = _load_error_message(output_dir, active)
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

        started_at = active.started_at if active is not None else _format_mtime(output_dir)
        updated_at = (
            active.updated_at
            if active is not None
            else _format_mtime(
                output_dir / "logs" / "run_summary.json"
                if (output_dir / "logs" / "run_summary.json").exists()
                else (
                    output_dir / "logs" / "run_state.json"
                    if (output_dir / "logs" / "run_state.json").exists()
                    else output_dir / "logs" / "error.json"
                )
            )
        )

        return RunDetailResponse(
            id=run_id,
            storyId=story_payload.get("story_id", run_id.split("_20")[0]),
            model=active.model if active is not None else DEFAULT_MODEL,
            status=status,
            startedAt=started_at,
            updatedAt=updated_at,
            error=error_message,
            currentNode=runtime.get("next_node") or ("renderer" if status == "completed" else "orchestrator"),
            currentSectionId=runtime.get("current_section_id"),
            nextNode=runtime.get("next_node"),
            sections=sections,
            artifacts=self._build_artifacts(output_dir),
            overview=overview,
            latestReview=latest_review_state,
        )

    def _build_artifacts(self, output_dir: Path) -> list[RunArtifactResponse]:
        """从输出目录读取前端需要的各类 artifact。"""
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
            output_dir / "logs" / "error.json",
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
