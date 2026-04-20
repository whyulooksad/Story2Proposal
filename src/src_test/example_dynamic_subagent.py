from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent


async def main() -> None:
    orchestrator = Agent(
        name="orchestrator",
        model="qwen-plus",
        instructions="""
You are an orchestration agent.

You may use built-in tools to create agents and edges.
When the user asks for analysis plus final output:
1. Create a subagent named analyst to do analysis.
2. Create a subagent named responder to write the final answer.
3. Create edges so orchestrator -> analyst -> responder.
4. Call the new agents when needed.

The analyst should output a concise Chinese analysis.
The responder should output the final Chinese answer with a short title and bullets.
""".strip(),
    )

    try:
        result = await orchestrator(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "帮我给一个 AI 客服系统写一个上线前检查清单，先分析再给最终清单。",
                    }
                ],
                "temperature": 0.2,
            },
            context={"language": "zh-CN"},
        )

        for index, message in enumerate(result["messages"], start=1):
            print(f"[{index}] {message}")
    finally:
        for agent in orchestrator.agents.values():
            await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
