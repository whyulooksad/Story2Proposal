from __future__ import annotations

"""Story2Proposal 的应用层运行入口。

这个文件负责把输入 story、共享 context、应用图、输出目录和最终收尾
串成一次完整运行。它是应用本体入口，不负责命令行参数解析。
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DEFAULT_MODEL, OUTPUTS_DIR
from domain import build_initial_context, evaluate_and_store_manuscript, persist_run_outputs
from graph import build_story2proposal_graph
from schemas import ResearchStory


async def run_story_to_proposal(
    story: ResearchStory,
    output_dir: Path | None = None,
    *,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """异步运行一次 Story2Proposal，并返回 context 与 summary。"""
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
        # 应用层只需要给根图一个启动消息，真正的流程推进由 graph 和 hooks
        # 共同完成。
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
        # 这里关闭的是整张应用图共享的 MCP manager。
        await graph._mcp_manager.close()

    if context.get("artifacts", {}).get("rendered") is not None:
        evaluate_and_store_manuscript(context)

    summary = persist_run_outputs(context)
    return {"context": context, "summary": summary}


def run_story_to_proposal_sync(
    story: ResearchStory,
    output_dir: Path | None = None,
    *,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """同步包装器，方便脚本或外部调用方直接使用。"""
    return asyncio.run(run_story_to_proposal(story, output_dir=output_dir, model=model))
