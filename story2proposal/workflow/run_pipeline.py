from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from story2proposal.config import OUTPUTS_DIR
from story2proposal.schemas import ResearchStory
from story2proposal.workflow.build_graph import build_story2proposal_graph
from story2proposal.workflow.context_ops import build_initial_context


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def run_story_to_proposal(
    story: ResearchStory,
    output_dir: Path | None = None,
    *,
    model: str = "qwen-plus",
) -> dict[str, Any]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    resolved_output = output_dir or (OUTPUTS_DIR / f"{story.story_id}_{run_id}")
    resolved_output.mkdir(parents=True, exist_ok=True)
    (resolved_output / "drafts").mkdir(exist_ok=True)
    (resolved_output / "reviews").mkdir(exist_ok=True)
    (resolved_output / "rendered").mkdir(exist_ok=True)
    (resolved_output / "logs").mkdir(exist_ok=True)

    context = build_initial_context(story, resolved_output)
    graph = build_story2proposal_graph(model=model)
    try:
        await graph(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Build a structured scientific manuscript scaffold from the story in context.",
                    }
                ],
                "temperature": 0.2,
            },
            context=context,
        )
    finally:
        for agent in graph.agents.values():
            await agent._mcp_manager.close()

    _write_json(resolved_output / "input_story.json", story.model_dump(mode="json"))
    _write_json(resolved_output / "blueprint.json", context.get("blueprint"))
    _write_json(
        resolved_output / "contract_init.json",
        context.get("artifacts", {}).get("contract_init"),
    )
    _write_json(resolved_output / "contract_final.json", context.get("contract"))
    for section_id, draft in context.get("drafts", {}).items():
        version = draft.get("version", 1)
        (resolved_output / "drafts" / f"{section_id}_v{version}.md").write_text(
            draft["content"],
            encoding="utf-8",
        )
    for section_id, reviews in context.get("reviews", {}).items():
        _write_json(resolved_output / "reviews" / f"{section_id}.json", reviews)
    rendered = context.get("artifacts", {}).get("rendered", {})
    (resolved_output / "rendered" / "final_manuscript.md").write_text(
        rendered.get("markdown", ""),
        encoding="utf-8",
    )
    (resolved_output / "rendered" / "final_manuscript.tex").write_text(
        rendered.get("latex", ""),
        encoding="utf-8",
    )
    summary = {
        "run_id": context.get("run_id"),
        "final_status": context.get("runtime", {}).get("final_status"),
        "completed_sections": context.get("runtime", {}).get("completed_sections", []),
        "rewrite_count": context.get("runtime", {}).get("rewrite_count", {}),
        "needs_manual_review": context.get("runtime", {}).get("needs_manual_review", []),
        "render_warnings": rendered.get("warnings", []),
        "output_dir": str(resolved_output),
    }
    _write_json(resolved_output / "logs" / "run_summary.json", summary)
    return {"context": context, "summary": summary}


def run_story_to_proposal_sync(
    story: ResearchStory,
    output_dir: Path | None = None,
    *,
    model: str = "qwen-plus",
) -> dict[str, Any]:
    return asyncio.run(run_story_to_proposal(story, output_dir=output_dir, model=model))
