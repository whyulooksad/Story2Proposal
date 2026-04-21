from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from config import OUTPUTS_DIR
from domain import build_initial_context, persist_run_outputs
from graph import build_story2proposal_graph
from schemas import ResearchStory


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
        await graph._mcp_manager.close()

    summary = persist_run_outputs(context)
    return {"context": context, "summary": summary}


def run_story_to_proposal_sync(
    story: ResearchStory,
    output_dir: Path | None = None,
    *,
    model: str = "qwen-plus",
) -> dict[str, Any]:
    return asyncio.run(run_story_to_proposal(story, output_dir=output_dir, model=model))
