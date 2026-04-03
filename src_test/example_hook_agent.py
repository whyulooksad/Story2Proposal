from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent, Hook


async def main() -> None:
    hook_server_path = ROOT / "src_test" / "hook_demo_server.py"
    context: dict[str, object] = {}

    agent = Agent(
        name="hook_writer",
        model="qwen-plus",
        instructions="""
You are a product copywriting agent.

Write in Chinese.
Use the following runtime context injected by hooks:
- tone: {{ tone }}
- target audience: {{ target_audience }}
- headline style: {{ headline_style }}

Return:
1. one title line
2. two short value statements
""".strip(),
        hooks=[
            Hook(
                on_start="mcp__hook_demo__prepare_brand_context",
                on_end="mcp__hook_demo__mark_run_finished",
            )
        ],
        mcpServers={
            "hook_demo": {
                "command": sys.executable,
                "args": [str(hook_server_path)],
            }
        },
    )

    try:
        result = await agent(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "给一个 AI 知识库产品写一段首页 Hero 区文案。",
                    }
                ],
                "temperature": 0.2,
            },
            context=context,
        )

        print("Run result:")
        for message in result["messages"]:
            print(message)

        print("\nHook context:")
        print(context)
    finally:
        await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
