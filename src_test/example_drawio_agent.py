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
        name="diagram_agent",
        model="qwen-plus",
        instructions="""
You are a diagram generation agent.

Your job is to turn the user's architecture description into a draw.io diagram.

Rules:
- You must use the draw.io MCP tool instead of only describing the diagram in text.
- Prefer the Mermaid-based draw.io tool when possible.
- First create a concise Mermaid diagram that matches the user's request.
- Then call the draw.io MCP tool to open or generate the diagram.
- After the tool call, reply in Chinese with a short summary of what was generated.

If draw.io MCP tools are available, use them.
""".strip(),
    )

    try:
        result = await agent(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "请画一个 AI 客服系统架构图，包含用户、Web 前端、API 网关、"
                            "客服编排 Agent、知识库检索、向量数据库、LLM 服务和日志监控。"
                        ),
                    }
                ],
                "temperature": 0.2,
            }
        )

        print("Run result:")
        for message in result["messages"]:
            print(message)
    finally:
        await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
