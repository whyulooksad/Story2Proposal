from __future__ import annotations

"""API 层的数据访问与运行管理。

这一层负责：
- 从 `data/stories/` 读取和保存 `ResearchStory`
- 从 `data/outputs/` 聚合 run 列表和 run 详情
- 启动后台 run，并把其状态暴露给 API 层

它是 API 和现有应用层 runtime 之间的桥接点。
"""

import json
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


def _format_mtime(path: Path) -> str:
    """把文件修改时间格式化成前端直接可展示的字符串。"""
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _combine_files(paths: list[Path]) -> str:
    """把多份文件拼成一个文本块，便于前端一次性查看。"""
    chunks: list[str] = []
    for path in sorted(paths):
        chunks.append(f"# {path.name}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def _map_section_status(status: str) -> str:
    """把 contract 里的内部状态映射成前端使用的状态名。"""
    mapping = {
        "pending": "pending",
        "drafted": "writing",
        "needs_revision": "revise",
        "approved": "approved",
    }
    return mapping.get(status, status)


def _count_validation_warnings(contract_payload: dict[str, Any]) -> int:
    """统计 contract global status 里的 warning 数量。"""
    return len((contract_payload.get("global_status") or {}).get("warnings", []))


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
        """初始化进程内活动 run 表。"""
        self._lock = Lock()
        self._active_runs: dict[str, ActiveRun] = {}

    def list(self) -> list[RunItemResponse]:
        """聚合历史输出目录和当前进程中的活动 run，返回 run 列表。"""
        items: dict[str, RunItemResponse] = {}

        if OUTPUTS_DIR.exists():
            for output_dir in sorted(OUTPUTS_DIR.iterdir(), reverse=True):
                if not output_dir.is_dir():
                    continue
                summary_path = output_dir / "logs" / "run_summary.json"
                story_path = output_dir / "input_story.json"
                if not summary_path.exists():
                    continue
                summary = _read_json(summary_path)
                story_id = summary.get("run_id", output_dir.name).split("_20")[0]
                if story_path.exists():
                    story = _read_json(story_path)
                    story_id = story.get("story_id", story_id)
                items[output_dir.name] = RunItemResponse(
                    id=output_dir.name,
                    storyId=story_id,
                    model=DEFAULT_MODEL,
                    status="completed" if summary.get("final_status") == "rendered" else "running",
                    startedAt=_format_mtime(output_dir),
                    updatedAt=_format_mtime(summary_path),
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
                )

        return sorted(items.values(), key=lambda item: item.updatedAt, reverse=True)

    def create(self, story: ResearchStory, model: str) -> RunDetailResponse:
        """创建一个新的输出目录，并在后台线程里启动 run。"""
        timestamp = datetime.now()
        run_id = f"{story.story_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        output_dir = OUTPUTS_DIR / run_id
        # 先准备好标准输出目录结构，后续运行过程中会持续往里写。
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

        # 运行放到后台线程，避免阻塞 API 请求。
        Thread(
            target=self._run_in_background,
            args=(story, output_dir, active),
            daemon=True,
        ).start()

        return self.get(run_id)

    def _run_in_background(self, story: ResearchStory, output_dir: Path, active: ActiveRun) -> None:
        """后台执行一次真正的 Story2Proposal run。"""
        try:
            run_story_to_proposal_sync(story, output_dir=output_dir, model=active.model)
            active.status = "completed"
        except Exception as exc:  # pragma: no cover
            active.status = "failed"
            active.error = str(exc)
        finally:
            active.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    def get(self, run_id: str) -> RunDetailResponse:
        """读取某个 run 的当前状态，并组装为前端详情响应。"""
        output_dir = OUTPUTS_DIR / run_id
        with self._lock:
            active = self._active_runs.get(run_id)

        if not output_dir.exists():
            raise FileNotFoundError(run_id)

        runtime = {}
        state_artifacts = {}
        state_path = output_dir / "logs" / "run_state.json"
        if state_path.exists():
            state_payload = _read_json(state_path)
            runtime = state_payload.get("runtime", {})
            state_artifacts = state_payload.get("artifacts", {})

        story_payload = {}
        story_path = output_dir / "input_story.json"
        if story_path.exists():
            story_payload = _read_json(story_path)

        contract_sections = []
        contract_payload = {}
        contract_path = output_dir / "contract_final.json"
        if contract_path.exists():
            contract_payload = _read_json(contract_path)
            contract_sections = contract_payload.get("sections", [])

        summary_payload = {}
        summary_path = output_dir / "logs" / "run_summary.json"
        if summary_path.exists():
            summary_payload = _read_json(summary_path)

        # 前端 section 列表来自最终 contract，同时叠加 runtime 中的 rewrite 次数。
        sections = [
            SectionStateResponse(
                id=section["section_id"],
                title=section["title"],
                status=_map_section_status(section.get("status", "pending")),
                rewriteCount=runtime.get("rewrite_count", {}).get(section["section_id"], 0),
            )
            for section in contract_sections
        ]

        # 活动 run 优先使用内存中的最新状态；否则回退到落盘 summary。
        status = active.status if active is not None else (
            "completed" if summary_payload.get("final_status") == "rendered" else "running"
        )
        latest_review = state_artifacts.get("last_aggregate_feedback") or {}
        overview = RunOverviewResponse(
            finalStatus=summary_payload.get("final_status", status),
            contractState=(contract_payload.get("global_status") or {}).get("state", "unknown"),
            completedSections=len(runtime.get("completed_sections", [])),
            pendingSections=len(runtime.get("pending_sections", [])),
            manualReviewCount=len(runtime.get("needs_manual_review", [])),
            renderWarningCount=_count_validation_warnings(contract_payload),
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
            else _format_mtime(summary_path if summary_path.exists() else output_dir)
        )

        return RunDetailResponse(
            id=run_id,
            storyId=story_payload.get("story_id", run_id.split("_20")[0]),
            model=active.model if active is not None else DEFAULT_MODEL,
            status=status,
            startedAt=started_at,
            updatedAt=updated_at,
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
        mapping = [
            ("blueprint", "Blueprint", output_dir / "blueprint.json"),
            ("contract", "Contract", output_dir / "contract_final.json"),
        ]
        # 单文件 artifact 直接读取。
        for artifact_id, label, path in mapping:
            artifacts.append(
                RunArtifactResponse(
                    id=artifact_id,
                    label=label,
                    kind=artifact_id,
                    content=path.read_text(encoding="utf-8") if path.exists() else "",
                )
            )

        # 多文件 artifact 统一聚合成单个文本块给前端显示。
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
        log_files = [output_dir / "logs" / "run_summary.json", output_dir / "logs" / "run_state.json"]
        artifacts.append(
            RunArtifactResponse(
                id="logs",
                label="Logs",
                kind="logs",
                content=_combine_files([path for path in log_files if path.exists()]),
            )
        )
        return artifacts
