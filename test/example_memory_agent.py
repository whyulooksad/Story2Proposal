from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import Agent, MemoryProvider, MemoryQuery, MemoryRecord, settings


class DemoMemoryProvider(MemoryProvider):
    """仅用于演示的简易 memory provider"""

    def __init__(self) -> None:
        self.storage: dict[str, dict[str, Any]] = {}

    async def load_context(
        self,
        *,
        agent_name: str,
        messages: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot = self.storage.get(agent_name, {})
        return {
            "preferred_style": snapshot.get("preferred_style", "简洁、专业"),
            "user_goal": snapshot.get("user_goal", "为 AI 产品写中文文案"),
            "last_answer_summary": snapshot.get("last_answer_summary", "暂无历史回答"),
        }

    async def save(
        self,
        *,
        agent_name: str,
        messages: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> None:
        snapshot = self.storage.setdefault(agent_name, {})
        last_user = next(
            (
                message["content"]
                for message in reversed(messages)
                if message.get("role") == "user" and isinstance(message.get("content"), str)
            ),
            "",
        )
        last_assistant = next(
            (
                message["content"]
                for message in reversed(messages)
                if message.get("role") == "assistant"
                and isinstance(message.get("content"), str)
            ),
            "",
        )

        if "记住" in last_user and "企业级" in last_user:
            snapshot["preferred_style"] = "企业级、简洁、可信"
        if last_user:
            snapshot["user_goal"] = last_user
        if last_assistant:
            snapshot["last_answer_summary"] = last_assistant[:80]

    async def search(self, query: MemoryQuery) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        for agent_name, snapshot in self.storage.items():
            for key, value in snapshot.items():
                if query.query in key or query.query in str(value):
                    records.append(
                        MemoryRecord(
                            key=f"{agent_name}.{key}",
                            content=str(value),
                            metadata={"agent_name": agent_name},
                        )
                    )
        return records[: query.limit]


async def main() -> None:
    settings.mcp_servers = {}
    memory = DemoMemoryProvider()

    agent = Agent(
        name="memory_writer",
        model="qwen-plus",
        instructions=(
            "You are a Chinese copywriting assistant.\n"
            "Current preferred style: {{ preferred_style }}\n"
            "Current user goal: {{ user_goal }}\n"
            "Last answer summary: {{ last_answer_summary }}\n"
            "Always answer in Chinese. Keep the output concise and directly usable."
        ),
    ).with_memory(memory)

    try:
        print("Round 1:")
        first_result = await agent(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "记住：后续给我的产品文案都用企业级、简洁的风格。先写一句 AI 助手首页主标题。",
                    }
                ],
                "temperature": 0.2,
            }
        )
        for message in first_result["messages"]:
            print(message)

        print("\nRound 2:")
        second_result = await agent(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "继续写一句首页副标题，不要重复主标题，要延续刚才记住的风格。",
                    }
                ],
                "temperature": 0.2,
            }
        )
        for message in second_result["messages"]:
            print(message)

        print("\nMemory search:")
        for record in await memory.search(MemoryQuery(query="企业级")):
            print(record.model_dump())
    finally:
        await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
