from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent, settings


async def main() -> None:
    # Keep this demo isolated from the project's global draw.io MCP config.
    settings.mcp_servers = {}

    agent = Agent(
        name="gui_operator",
        model="qwen-plus",
        instructions=(
            "You are a browser GUI agent.\n"
            "You must use the available Playwright MCP tools to inspect and operate the page.\n"
            "Do not pretend you opened a page if you did not actually use a tool.\n"
            "First open https://example.com , then inspect the page, and finally answer in Chinese.\n"
            "Your final answer must include:\n"
            "1. 页面标题\n"
            "2. 页面主标题\n"
            "3. 这个页面的用途一句话总结\n"
            "Keep the final answer short and factual."
        ),
        mcpServers={
            "playwright": {
                "command": "cmd",
                "args": ["/c", "npx", "-y", "@playwright/mcp@latest"],
            }
        },
    )

    try:
        result = await agent(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请实际打开网页并读取页面信息，不要只凭常识回答。",
                    }
                ],
                "temperature": 0.1,
            }
        )
        for message in result["messages"]:
            print(message)
    finally:
        await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
