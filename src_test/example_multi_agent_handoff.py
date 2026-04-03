from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent, Edge


async def main() -> None:
    planner = Agent(
        name="planner",
        model="qwen-plus",
        instructions=(
            "You are a planning agent. "
            "Read the user's request and output a short 3-step plan in Chinese."
        ),
    )
    writer = Agent(
        name="writer",
        model="qwen-plus",
        instructions=(
            "You are a writing agent. "
            "Based on the conversation history, produce the final answer in Chinese. "
            "Structure it as: 标题 + 3 条要点."
        ),
    )

    root = Agent(
        name="root",
        model="qwen-plus",
        instructions=(
            "You are the entry agent. "
            "Summarize the user's request in one short Chinese sentence."
        ),
        nodes={planner, writer},
        edges={
            Edge(source="root", target="planner"),
            Edge(source="planner", target="writer"),
        },
    )

    try:
        result = await root(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "我要做一个企业知识库问答助手，请给我一个最小可行版本方案。",
                    }
                ],
                "temperature": 0.3,
            }
        )

        for index, message in enumerate(result["messages"], start=1):
            print(f"[{index}] {message}")
    finally:
        for agent in root.agents.values():
            await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
