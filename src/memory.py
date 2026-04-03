"""Memory Provider 接口与轻量级 Memory 数据结构"""

from __future__ import annotations

from abc import ABC
from typing import Any

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field


class MemoryQuery(BaseModel):
    """预留的结构化 Memory 查询，用于后续扩展"""

    query: str
    namespace: str | None = None
    limit: int = 5
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    """单条检索或持久化的 Memory 记录"""

    content: str
    key: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryProvider(ABC):
    """预留的抽象 Memory Provider 接口，用于 Agent 级 Memory 集成。"""

    async def load_context(
        self,
        *,
        agent_name: str,
        messages: list[ChatCompletionMessageParam],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """获取 Memory Context 并合并至当前运行环境"""
        return {}

    async def save(
        self,
        *,
        agent_name: str,
        messages: list[ChatCompletionMessageParam],
        context: dict[str, Any],
    ) -> None:
        """在执行完成后持久化 Memory"""
        return None

    async def search(self, query: MemoryQuery) -> list[MemoryRecord]:
        """当应用需要执行检索时，显式搜索 Memory"""
        return []


class NoopMemoryProvider(MemoryProvider):
    """默认无 Memory Provider"""

