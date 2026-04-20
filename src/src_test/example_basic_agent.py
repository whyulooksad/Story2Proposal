from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent


async def main() -> None:
    agent = Agent(
        name="assistant",
        model="qwen-plus",
        instructions=(
            "You are a concise assistant. "
            "Answer in Chinese and keep the reply under 80 Chinese characters."
        ),
    )

    try:
        result = await agent(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请用介绍这个 agent 框架的定位。",
                    }
                ],
                "temperature": 0.2,
            }
        )

        for message in result["messages"]:
            print(message)
    finally:
        await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
