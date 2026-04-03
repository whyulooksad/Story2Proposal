"""Minimal true-streaming example for Agent.stream()."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent, settings


async def main() -> None:
    # settings.mcp_servers = {}

    agent = Agent(
        name="stream_writer",
        model="qwen-plus",
        instructions=(
            "You are a concise assistant. "
            "Answer in Chinese with one short paragraph."
        ),
    )

    try:
        async for event in agent.stream(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请用中文简要解释什么是图驱动的 Agent 框架。",
                    }
                ],
                "temperature": 0.2,
            }
        ):
            event_type = event["type"]
            if event_type == "token":
                print(event["delta"], end="", flush=True)
            elif event_type == "message":
                print("\n\nFinal message:")
                print(event["message"])
            elif event_type == "done":
                print("\n\nStream done.")
    finally:
        await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
