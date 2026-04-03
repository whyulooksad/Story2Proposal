from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent, Edge, create_mcp_server


async def smoke_run() -> None:
    classifier = Agent(
        name="classifier",
        model="qwen-plus",
        description="将用户意图分类为一个简短中文标签。",
        instructions="Read the latest user request and reply with one Chinese intent label only.",
    )
    responder = Agent(
        name="responder",
        model="qwen-plus",
        description="用中文回答用户问题。",
        instructions=(
            "Based on the full conversation, give the final Chinese answer. "
            "The first line should include the detected intent label."
        ),
    )
    root = Agent(
        name="root_agent",
        model="qwen-plus",
        description="演示工作流的入口智能体。",
        instructions="Summarize the user request in one Chinese sentence.",
        nodes={classifier, responder},
        edges={
            Edge(source="root_agent", target="classifier"),
            Edge(source="classifier", target="responder"),
        },
    )

    try:
        result = await root(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请帮我写一段适合产品首页的 AI 助手介绍文案。",
                    }
                ]
            }
        )
        print("Run result:")
        for message in result["messages"]:
            print(message)

        server = create_mcp_server(root)
        tools = await server.list_tools()
        print("\nExposed MCP tools:")
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")
    finally:
        for agent in root.agents.values():
            await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(smoke_run())
