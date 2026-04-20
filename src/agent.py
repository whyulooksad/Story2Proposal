from __future__ import annotations

import asyncio
import json
import logging
import uuid
import warnings
from collections.abc import AsyncGenerator
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Any, Iterable, get_args, cast

from cel import evaluate
from httpx import Timeout
from jinja2 import Template
from openai import DEFAULT_MAX_RETRIES, AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionFunctionToolParam,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallUnionParam,
)
from openai.types.chat.completion_create_params import CompletionCreateParamsBase
from pydantic import Field, PrivateAttr, TypeAdapter, field_serializer, field_validator

from ._settings import settings
from .edge import Edge
from .hook import Hook, HookType
from .mcp_manager import MCPManager, result_to_message
from .memory import MemoryProvider
from .nodes import Node, Tool
from .skill import Skill, SkillCatalog, SkillLoader
from .types import CompletionCreateParams, MCPServer, MessagesState
from .utils import completion_to_message

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Agent(Node[CompletionCreateParams, MessagesState]):
    """执行 graph 中的 Agent 节点"""

    name: Annotated[
        str, Field(pattern=r"([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*)", frozen=True)
    ]
    description: str | None = None
    inputSchema: dict[str, Any] = Field(
        default_factory=lambda: TypeAdapter(CompletionCreateParams).json_schema()
    )
    model: str
    instructions: str | None = None
    mcp_servers: dict[str, MCPServer] = Field(default_factory=dict, alias="mcpServers")
    client: AsyncOpenAI | None = None
    nodes: set[Node] = Field(default_factory=set)
    edges: set[Edge] = Field(default_factory=set)
    hooks: list[Hook] = Field(default_factory=list)

    _visited: dict[str, bool] = PrivateAttr(
        default_factory=lambda: defaultdict(lambda: False)
    )
    _mcp_manager: MCPManager = PrivateAttr(default_factory=MCPManager)
    _memory_provider: MemoryProvider | None = PrivateAttr(default=None)
    _active_skill: Skill | None = PrivateAttr(default=None)
    _skill_loader: SkillLoader | None = PrivateAttr(default=None)
    _skill_catalog: SkillCatalog | None = PrivateAttr(default=None)
    _skill_agent_name: str | None = PrivateAttr(default=None)

    @property
    def agents(self) -> dict[str, "Agent"]:
        """返回当前 graph 中所有 Agent，键为唯一的 name"""
        return self._collect_agents()

    def _collect_agents(self) -> dict[str, "Agent"]:
        collected: dict[str, "Agent"] = {}

        def visit(node: "Agent") -> None:
            if node.name in collected:
                raise ValueError(f"Duplicated agent name: {node.name}")
            collected[node.name] = node
            for child in node.nodes:
                if isinstance(child, Agent):
                    visit(child)

        visit(self)
        return collected

    @classmethod
    def as_init_tool(cls) -> ChatCompletionFunctionToolParam:
        """把 Agent 暴露成 create_agent 内建工具"""
        return {
            "type": "function",
            "function": {
                "name": "create_agent",
                "description": cls.__doc__ or "",
                "parameters": cls.model_json_schema(),
            },
        }

    def as_call_tool(self) -> ChatCompletionFunctionToolParam:
        """把当前 Agent 暴露成可调用工具"""
        tool: ChatCompletionFunctionToolParam = {
            "type": "function",
            "function": {
                "name": self.name,
                "parameters": self.inputSchema,
            },
        }
        if self.description is not None:
            tool["function"]["description"] = self.description
        return tool

    @field_validator("client", mode="plain")
    def validate_client(cls, value: Any) -> AsyncOpenAI | None:
        """将客户端配置反序列化为 AsyncOpenAI 实例"""
        if value is None:
            return None
        if isinstance(value, AsyncOpenAI):
            return value
        if isinstance(timeout_dict := value.get("timeout"), dict):
            value["timeout"] = Timeout(**timeout_dict)
        return AsyncOpenAI(**value)

    @field_serializer("client", mode="plain")
    def serialize_client(self, value: AsyncOpenAI | None) -> dict[str, Any] | None:
        """序列化 AsyncOpenAI，忽略默认字段。"""
        if value is None:
            return None
        client: dict[str, Any] = {}
        if str(value.base_url) != "https://api.openai.com/v1":
            client["base_url"] = str(value.base_url)
        for key in ("organization", "project", "websocket_base_url"):
            if (attr := getattr(value, key, None)) is not None:
                client[key] = attr
        if isinstance(value.timeout, float | None):
            client["timeout"] = value.timeout
        elif isinstance(value.timeout, Timeout):
            client["timeout"] = value.timeout.as_dict()
        if value.max_retries != DEFAULT_MAX_RETRIES:
            client["max_retries"] = value.max_retries
        if bool(value._custom_headers):
            client["default_headers"] = value._custom_headers
        if bool(value._custom_query):
            client["default_query"] = value._custom_query
        return client

    def model_post_init(self, context: Any) -> None:
        """初始化 runtime state ，并对执行图进行校验。"""
        mcp_manager = (self.model_extra or {}).get("mcp_manager")
        if isinstance(mcp_manager, MCPManager):
            self._mcp_manager = mcp_manager
        self._collect_agents()

    def _share_runtime_with_child(self, child: "Agent") -> None:
        """执行前向子智能体共享 runtime state"""
        child._mcp_manager = self._mcp_manager
        child._memory_provider = self._memory_provider
        if child._skill_loader is None and self._skill_loader is not None:
            child._skill_loader = self._skill_loader
        if child._skill_catalog is None and self._skill_catalog is not None:
            child._skill_catalog = self._skill_catalog
        if child._skill_agent_name is None and self._skill_agent_name is not None:
            child._skill_agent_name = self._skill_agent_name
        if child._active_skill is None and self._active_skill is not None:
            child._active_skill = self._active_skill.for_child()

    def with_memory(self, provider: MemoryProvider | None) -> "Agent":
        """挂载 Memory Provider"""
        self._memory_provider = provider
        return self

    def with_skill_loader(
        self,
        loader: SkillLoader,
        *,
        agent_name: str | None = None,
    ) -> "Agent":
        """挂载 agent 的 skill catalog"""
        resolved_agent_name = agent_name or self.name
        self._skill_loader = loader
        self._skill_agent_name = resolved_agent_name
        self._skill_catalog = loader.load_catalog(resolved_agent_name)
        return self

    async def _prepare_runtime(self) -> None:
        """执行入口统一准备 runtime 共享与 MCP server 连接"""
        for child in self.agents.values():
            if child is not self:
                self._share_runtime_with_child(child)
        for name, server_params in self._effective_mcp_servers().items():
            await self._mcp_manager.add_server(name, server_params)

    def _skill_catalog_text(self) -> str | None:
        """返回 skill 激活前展示的 skill catalog 提示词"""
        if self._skill_catalog is None or self._active_skill is not None:
            return None
        lines = [
            "Skill catalog:",
            "Choose a skill first if the user goal matches one of the following skills.",
            "Do not call MCP tools before activating a skill.",
        ]
        if self._skill_catalog.overview.strip():
            lines.append(self._skill_catalog.overview.strip())
        for skill in self._skill_catalog.skills:
            line = f"- {skill.name}: {skill.purpose}"
            if skill.description:
                line += f" {skill.description}"
            lines.append(line)
        return "\n".join(lines)

    def _activate_skill_tool(self) -> ChatCompletionFunctionToolParam | None:
        """返回用于激活 skill 的内置工具"""
        if self._skill_catalog is None:
            return None
        return {
            "type": "function",
            "function": {
                "name": "activate_skill",
                "description": (
                    "Activate one skill from the current skill catalog "
                    "before making MCP tool calls."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Exact skill name from the catalog.",
                            "enum": self._skill_catalog.skill_names,
                        }
                    },
                    "required": ["skill_name"],
                    "additionalProperties": False,
                },
            },
        }

    def _effective_mcp_servers(self) -> dict[str, MCPServer]:
        """返回当前运行可见的 MCP 服务器"""
        return (settings.mcp_servers if settings is not None else {}) | self.mcp_servers

    def _can_current_turn_see_mcp_tools(self) -> bool:
        """返回本轮交互中 MCP工具 是否应可见"""
        if self._skill_catalog is None:
            return True
        return self._active_skill is not None

    def _is_tool_visible_for_skill(self, tool_name: str) -> bool:
        """检查 MCP 工具是否在当前激活的 skill 下可见"""
        if not self._can_current_turn_see_mcp_tools():
            return False
        if self._active_skill is None:
            return True
        if self._active_skill.tool_names:
            return tool_name in set(self._active_skill.tool_names)
        if self._active_skill.visible_mcp_servers:
            parts = tool_name.split("__", maxsplit=2)
            if len(parts) < 3:
                return False
            return parts[1] in set(self._active_skill.visible_mcp_servers)
        return True

    async def _load_memory_context(
        self,
        messages: list[ChatCompletionMessageParam],
        context: dict[str, Any],
    ) -> None:
        """执行前合并 Memory Context 至当前运行流程"""
        if self._memory_provider is None:
            return
        loaded = await self._memory_provider.load_context(
            agent_name=self.name,
            messages=messages,
            context=context,
        )
        if loaded:
            context |= loaded

    async def _save_memory(
        self,
        messages: list[ChatCompletionMessageParam],
        context: dict[str, Any],
    ) -> None:
        """执行结束后持久化 Memory"""
        if self._memory_provider is None:
            return
        await self._memory_provider.save(
            agent_name=self.name,
            messages=messages,
            context=context,
        )

    async def __call__(
        self,
        params: CompletionCreateParams | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> MessagesState:
        """运行 Agent"""
        await self._prepare_runtime()
        if params is None:
            params = {"messages": []}
        stream = params.get("stream", False)
        if stream:
            raise NotImplementedError("Stream mode is not yet supported now.")
        params = deepcopy(params)
        messages = params["messages"]
        init_len = len(messages)
        if context is None:
            context = {}
        await self._load_memory_context(messages, context)
        self._visited.clear()
        self._cleanup_runtime_tools()
        await self._execute_hooks("on_start", messages, context)
        try:
            completion = await self._create_chat_completion(
                params=params,
                context=context,
            )
            logger.info(
                json.dumps(
                    completion.model_dump(mode="json", exclude_unset=True)
                    | {"request_id": completion._request_id}
                )
            )

            message = completion_to_message(completion)
            message["name"] = self.name
            messages.append(message)

            if (tool_calls := messages[-1].get("tool_calls")) is not None:
                messages.extend(self._register_tool_calls(tool_calls, messages))
            self._visited[self.name] = True
            pending_sources: set[str] = {self.name}
            while pending_sources:
                targets: dict[str, Node] = {}
                for edge in self.edges:
                    if not self._edge_triggers(edge, pending_sources):
                        continue
                    resolved = await self._resolve_edge_target(edge.target, context)
                    for target in resolved:
                        targets[target.name] = target
                if not targets:
                    break
                task_entries: list[tuple[Node, asyncio.Task[MessagesState]]] = []
                async with asyncio.TaskGroup() as tg:
                    for target in targets.values():
                        if isinstance(target, Agent):
                            task = tg.create_task(
                                self._run_agent_node(target, messages, context)
                            )
                        elif isinstance(target, Tool):
                            task = tg.create_task(
                                self._run_tool_node(
                                    target, {"messages": messages}, context
                                )
                            )
                        else:
                            raise TypeError("Unknown type of Node.")
                        task_entries.append((target, task))
                pending_sources = set()
                for target, task in task_entries:
                    result = task.result()
                    messages.extend(result["messages"])
                    self._visited[target.name] = True
                    pending_sources.add(target.name)
            await self._execute_hooks("on_end", messages, context)
            await self._save_memory(messages, context)
            return {"messages": messages[init_len:]}
        finally:
            self._cleanup_runtime_tools()

    async def stream(
        self,
        params: CompletionCreateParams | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """以真实流式事件的方式运行 Agent"""
        await self._prepare_runtime()
        if params is None:
            params = {"messages": []}
        params = deepcopy(params)
        params["stream"] = True
        if context is None:
            context = {}
        await self._load_memory_context(params["messages"], context)
        self._visited.clear()
        self._cleanup_runtime_tools()
        try:
            async for event in self._stream_graph(params=params, context=context):
                yield event
            await self._save_memory(params["messages"], context)
            yield {"type": "done", "agent": self.name}
        finally:
            self._cleanup_runtime_tools()

    async def _stream_graph(
        self,
        *,
        params: CompletionCreateParams,
        context: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """顺序执行 graph，并逐步产出流式事件"""
        messages = params["messages"]
        await self._execute_hooks("on_start", messages, context)
        try:
            yield {"type": "agent_start", "agent": self.name}
            assistant_message: dict[str, Any] | None = None
            async for event in self._stream_chat_completion(
                params=params,
                context=context,
            ):
                if event["type"] == "completion_message":
                    assistant_message = cast(dict[str, Any], event["message"])
                    continue
                yield event
            if assistant_message is None:
                raise ValueError("Stream completion did not produce a final assistant message")

            messages.append(assistant_message)
            yield {
                "type": "message",
                "agent": self.name,
                "message": assistant_message,
            }

            if (tool_calls := assistant_message.get("tool_calls")) is not None:
                generated_tool_messages = self._register_tool_calls(tool_calls, messages)
                messages.extend(generated_tool_messages)
                for tool_message in generated_tool_messages:
                    yield {
                        "type": "tool_result",
                        "agent": self.name,
                        "tool_name": "activate_skill",
                        "message": tool_message,
                    }
            self._visited[self.name] = True
            pending_sources: set[str] = {self.name}
            while pending_sources:
                targets: dict[str, Node] = {}
                for edge in self.edges:
                    if not self._edge_triggers(edge, pending_sources):
                        continue
                    resolved = await self._resolve_edge_target(edge.target, context)
                    for target in resolved:
                        targets[target.name] = target
                if not targets:
                    break

                pending_sources = set()
                for target_name in sorted(targets):
                    target = targets[target_name]
                    if isinstance(target, Agent):
                        await target._prepare_runtime()
                        await self._execute_hooks(
                            "on_handoff",
                            messages,
                            context,
                            to_agent=target,
                        )
                        async for event in target._stream_graph(
                            params={"messages": messages},
                            context=context,
                        ):
                            yield event
                    elif isinstance(target, Tool):
                        result = await self._run_tool_node(
                            target,
                            {"messages": messages},
                            context,
                        )
                        tool_message = result["messages"][0]
                        messages.append(tool_message)
                        yield {
                            "type": "tool_result",
                            "agent": self.name,
                            "tool_name": target.tool_name or target.name,
                            "message": tool_message,
                        }
                    else:
                        raise TypeError("Unknown type of Node.")
                    self._visited[target.name] = True
                    pending_sources.add(target.name)
            await self._execute_hooks("on_end", messages, context)
            yield {"type": "agent_end", "agent": self.name}
        finally:
            self._cleanup_runtime_tools()

    def _edge_triggers(self, edge: Edge, pending_sources: set[str]) -> bool:
        """检查边是否可触发"""
        if isinstance(edge.source, tuple):
            return all(self._visited.get(name, False) for name in edge.source) and any(
                name in pending_sources for name in edge.source
            )
        return edge.source in pending_sources

    async def _run_tool_node(
        self,
        tool: Tool,
        state: MessagesState,
        context: dict[str, Any],
    ) -> MessagesState:
        """通过 Hook 执行工具节点"""
        messages = state["messages"]
        await self._execute_hooks(
            "on_tool_start",
            messages,
            context,
            tool_name=tool.name,
        )
        try:
            result = await tool(tool.tool_arguments)
        except Exception:
            await self._execute_hooks(
                "on_tool_end",
                messages,
                context,
                tool_name=tool.name,
            )
            raise
        await self._execute_hooks(
            "on_tool_end",
            messages,
            context,
            tool_name=tool.name,
        )
        return {"messages": [result_to_message(tool.name, result)]}

    async def _run_agent_node(
        self,
        target: "Agent",
        messages: list[ChatCompletionMessageParam],
        context: dict[str, Any],
    ) -> MessagesState:
        """触发 handoff hook,执行下游 agent"""
        await self._execute_hooks(
            "on_handoff",
            messages,
            context,
            to_agent=target,
        )
        return await target({"messages": messages}, context=context)

    def _builtin_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """返回当前 Agent 默认可见的 graph 管理工具"""
        tools = [
            *[
                agent.as_call_tool()
                for agent in [self, *self.nodes]
                if isinstance(agent, Agent)
            ],
            Agent.as_init_tool(),
            Edge.as_tool(),
        ]
        if (activate_tool := self._activate_skill_tool()) is not None:
            tools.append(activate_tool)
        return tools

    def _visible_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """返回当前轮次模型可见的全部工具"""
        hook_names = [
            getattr(hook, hook_type)
            for hook in self.hooks
            for hook_type in get_args(HookType)
            if getattr(hook, hook_type, None) is not None
        ]
        visible_mcp_tools = [
            tool
            for tool in self._mcp_manager.tools
            if tool["function"]["name"] not in hook_names
        ]
        visible_mcp_tools = [
            tool
            for tool in visible_mcp_tools
            if self._is_tool_visible_for_skill(tool["function"]["name"])
        ]
        return visible_mcp_tools + self._builtin_tools()

    def _is_tool_call_allowed(self, tool_name: str) -> bool:
        """Return whether a tool call is allowed in the current runtime state."""
        builtin_tool_names = {
            tool["function"]["name"]
            for tool in self._builtin_tools()
            if tool["type"] == "function"
        }
        if tool_name in builtin_tool_names:
            return True
        return self._is_tool_visible_for_skill(tool_name)

    def _blocked_tool_call_message(
        self,
        tool_call: ChatCompletionMessageToolCallUnionParam,
    ) -> ChatCompletionMessageParam:
        """Return a synthetic tool result when the model calls a hidden MCP tool."""
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": (
                f"Tool `{tool_call['function']['name']}` is not visible in the current skill. "
                "Choose or activate the correct skill first."
            ),
        }

    async def _execute_hooks(
        self,
        hook_type: HookType,
        messages: list[ChatCompletionMessageParam],
        context: dict[str, Any],
        *,
        tool_name: str | None = None,
        available_tools: list[ChatCompletionFunctionToolParam] | None = None,
        to_agent: Agent | None = None,
        chunk: ChatCompletionChunk | None = None,
        completion: Any | None = None,
    ) -> None:
        """执行指定类型的 Hook"""
        for hook in [h for h in self.hooks if getattr(h, hook_type, None) is not None]:
            hook_name: str = getattr(hook, hook_type)
            hook_tool = self._mcp_manager.get_tool(hook_name)
            properties = hook_tool.inputSchema["properties"]
            arguments: dict[str, Any] = {}
            available: dict[str, Any] = {"messages": messages, "context": context}
            if chunk is not None:
                available["chunk"] = chunk
            if completion is not None:
                available["completion"] = completion
            if tool_name is not None:
                available["tool"] = self._mcp_manager.get_tool(tool_name)
            if to_agent is not None:
                available["to_agent"] = to_agent.model_dump(
                    mode="json", exclude_unset=True
                )
            else:
                available["agent"] = self.model_dump(mode="json", exclude_unset=True)
            if available_tools is not None:
                available["available_tools"] = available_tools
            if chunk is not None:
                available["chunk"] = chunk
            if completion is not None:
                available["completion"] = completion
            for key, value in available.items():
                if key in properties:
                    arguments |= {key: value}
            result = await self._mcp_manager.call_tool(hook_name, arguments)
            if result.structuredContent is None:
                raise ValueError("Hook tool must return structured content")
            context |= result.structuredContent

    async def _get_system_prompt(
        self,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """组装 system prompt"""
        parts = []
        if self.instructions is not None:
            parts.append(
                await Template(self.instructions, enable_async=True).render_async(
                    context or {}
                )
            )
        if (skill_catalog_text := self._skill_catalog_text()) is not None:
            parts.append(skill_catalog_text)
        if self._active_skill is not None and self._active_skill.instructions is not None:
            parts.append(
                "Active skill instructions:\n"
                + await Template(
                    self._active_skill.instructions, enable_async=True
                ).render_async(context or {})
            )
        if len(agent_md_content := settings.get_agents_md_content()) > 0:
            parts.append(
                "Following are extra contexts, what were considered as long-term memory.\n"
                + agent_md_content
            )
        if len(parts) > 0:
            return "\n\n".join(parts)
        return None

    async def _prepare_chat_completion_params(
        self,
        parameters: CompletionCreateParams,
        context: dict[str, Any] | None = None,
    ) -> CompletionCreateParamsBase:
        """准备 OpenAI 对话请求参数"""
        messages = [
            cast(
                ChatCompletionMessageParam,
                {
                    key: value
                    for key, value in message.items()
                    if key not in ("parsed", "reasoning_content")
                },
            )
            for message in parameters["messages"]
            if not (message.get("role") == "user" and message.get("name") == "approval")
        ]
        system_prompt = await self._get_system_prompt(context)
        if system_prompt is not None:
            messages = [{"role": "system", "content": system_prompt}, *messages]
        tools: list[ChatCompletionFunctionToolParam] = [*parameters.get("tools", [])]
        existing_tool_names = {
            tool["function"]["name"] for tool in tools if tool["type"] == "function"
        }
        for tool in self._visible_tools():
            if (
                tool["type"] == "function"
                and tool["function"]["name"] in existing_tool_names
            ):
                continue
            tools.append(tool)
            if tool["type"] == "function":
                existing_tool_names.add(tool["function"]["name"])
        if tools:
            parameters["tools"] = tools
        else:
            parameters.pop("tools", None)
        return parameters | {
            "messages": messages,
            "model": self.model,
        }

    async def _create_chat_completion(
        self,
        *,
        params: CompletionCreateParams,
        context: dict[str, Any],
    ) -> ChatCompletion:
        """创建一次 chat completion，并使用 request_id  进行追踪。"""
        request_id = str(uuid.uuid4())
        parameters = await self._prepare_chat_completion_params(params, context)
        logger.info(json.dumps(parameters | {"request_id": request_id}))
        client = self.client or AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        messages = params["messages"]
        await self._execute_hooks(
            "on_llm_start",
            messages,
            context,
            available_tools=self._visible_tools(),
        )
        result = await client.chat.completions.create(**parameters)
        result._request_id = request_id
        await self._execute_hooks("on_llm_end", messages, context, completion=result)
        return result

    async def _stream_chat_completion(
        self,
        *,
        params: CompletionCreateParams,
        context: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """创建一次真实流式 chat completion，并逐步聚合最终消息。"""
        request_id = str(uuid.uuid4())
        parameters = await self._prepare_chat_completion_params(params, context)
        logger.info(json.dumps(parameters | {"request_id": request_id, "stream": True}))
        client = self.client or AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        messages = params["messages"]
        await self._execute_hooks(
            "on_llm_start",
            messages,
            context,
            available_tools=self._visible_tools(),
        )
        yield {"type": "llm_start", "agent": self.name, "request_id": request_id}

        stream = await client.chat.completions.create(**parameters)
        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            await self._execute_hooks(
                "on_chunk",
                messages,
                context,
                chunk=chunk,
            )
            yield {"type": "chunk", "agent": self.name, "chunk": chunk}
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            delta_content = getattr(delta, "content", None)
            if delta_content is not None:
                if isinstance(delta_content, str):
                    content_parts.append(delta_content)
                    yield {
                        "type": "token",
                        "agent": self.name,
                        "delta": delta_content,
                    }
                elif isinstance(delta_content, list):
                    for item in delta_content:
                        text = getattr(item, "text", None)
                        if text:
                            content_parts.append(text)
                            yield {
                                "type": "token",
                                "agent": self.name,
                                "delta": text,
                            }
            for delta_tool_call in getattr(delta, "tool_calls", None) or []:
                index = getattr(delta_tool_call, "index", 0)
                aggregated = tool_calls.setdefault(
                    index,
                    {
                        "type": "function",
                        "id": "",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                if getattr(delta_tool_call, "id", None):
                    aggregated["id"] = delta_tool_call.id
                function = getattr(delta_tool_call, "function", None)
                if function is not None:
                    if getattr(function, "name", None):
                        aggregated["function"]["name"] += function.name
                    if getattr(function, "arguments", None):
                        aggregated["function"]["arguments"] += function.arguments

        message: dict[str, Any] = {"role": "assistant", "name": self.name}
        content = "".join(content_parts).strip()
        if content:
            message["content"] = content
        if tool_calls:
            message["tool_calls"] = [tool_calls[index] for index in sorted(tool_calls)]

        completion_payload = {
            "id": request_id,
            "object": "chat.completion.stream.final",
            "message": message,
        }
        await self._execute_hooks(
            "on_llm_end",
            messages,
            context,
            completion=completion_payload,
        )
        yield {
            "type": "completion_message",
            "agent": self.name,
            "message": message,
            "request_id": request_id,
        }

    def _activate_skill_from_call(
        self,
        tool_call: ChatCompletionMessageToolCallUnionParam,
    ) -> ChatCompletionMessageParam:
        """激活指定 skill，并生成工具调用的模拟返回消息"""
        arguments = json.loads(tool_call["function"]["arguments"])
        skill_name = arguments["skill_name"]
        self.edges.add(Edge(source=self.name, target=self.name))
        if self._skill_loader is None or self._skill_agent_name is None:
            return {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": "Skill loader is not configured for this agent.",
            }
        try:
            self._active_skill = self._skill_loader.load(
                skill_name=skill_name,
                agent_name=self._skill_agent_name,
            )
        except Exception as exc:
            return {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": f"Failed to activate skill `{skill_name}`: {exc}",
            }
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": f"Skill `{skill_name}` activated.",
        }

    def _register_tool_calls(
        self,
        tool_calls: Iterable[ChatCompletionMessageToolCallUnionParam],
        messages: list[ChatCompletionMessageParam],
    ) -> list[ChatCompletionMessageParam]:
        """把 assistant 返回的 tool_calls 注册成 graph 中的 node 和 edge"""
        generated_messages: list[ChatCompletionMessageParam] = []
        for tool_call in tool_calls:
            if tool_call["type"] == "custom":
                continue
            name = tool_call["function"]["name"]
            match name:
                case "activate_skill":
                    generated_messages.append(self._activate_skill_from_call(tool_call))
                case "create_agent":
                    payload = json.loads(tool_call["function"]["arguments"])
                    payload["model"] = self.model
                    if self.client is not None:
                        payload["client"] = self.client
                    child = Agent.model_validate(payload)
                    self._share_runtime_with_child(child)
                    self.nodes.add(child)
                case "create_edge":
                    self.edges.add(
                        Edge.model_validate_json(tool_call["function"]["arguments"])
                    )
                case known if known in [
                    self.name,
                    *[node.name for node in self.nodes if isinstance(node, Agent)],
                ]:
                    self.edges.add(Edge(source=self.name, target=known))
                case _:
                    if not self._is_tool_call_allowed(name):
                        generated_messages.append(
                            self._blocked_tool_call_message(tool_call)
                        )
                        continue
                    if self._tool_call_completed(messages, tool_call["id"]):
                        continue
                    tool_arguments = json.loads(tool_call["function"]["arguments"])
                    tool_node = self._mcp_manager.make_tool_node(
                        name,
                        tool_call["id"],
                        tool_arguments,
                    )
                    self.nodes.add(tool_node)
                    self.edges.add(Edge(source=self.name, target=tool_node.name))
                    self.edges.add(Edge(source=tool_node.name, target=self.name))
        return generated_messages

    def _tool_call_completed(
        self,
        messages: list[ChatCompletionMessageParam],
        tool_call_id: str,
    ) -> bool:
        return any(
            message.get("tool_call_id") == tool_call_id
            for message in messages
            if message["role"] == "tool"
        )

    def _cleanup_runtime_tools(self) -> None:
        """移除临时 MCP 工具节点及其关联的边"""
        runtime_nodes = [
            node
            for node in self.nodes
            if isinstance(node, Tool) and getattr(node, "tool_call_id", None)
        ]
        if not runtime_nodes:
            return
        runtime_names = {node.name for node in runtime_nodes}
        self.nodes = {node for node in self.nodes if node.name not in runtime_names}
        remaining_edges: set[Edge] = set()
        for edge in self.edges:
            sources = (
                set(edge.source) if isinstance(edge.source, tuple) else {edge.source}
            )
            if sources & runtime_names:
                continue
            if edge.target in runtime_names:
                continue
            remaining_edges.add(edge)
        self.edges = remaining_edges
        for name in runtime_names:
            self._visited.pop(name, None)

    def _get_node_by_name(self, name: str) -> Node:
        """返回自身或一级子节点"""
        if name == self.name:
            return self
        for node in self.nodes:
            if node.name == name:
                return node
        raise KeyError(f"Node {name} not exist in nodes")

    async def _resolve_edge_target(
        self, target: str, context: dict[str, Any] | None = None
    ) -> set[Node]:
        """按节点 name、tool 或 CEL 表达式解析边目标"""
        try:
            return {self._get_node_by_name(target)}
        except KeyError:
            pass

        try:
            result = await self._mcp_manager.call_tool(
                target,
                {"context": context or {}},
            )
            if result.structuredContent is not None:
                resolved = result.structuredContent.get("result")
                if isinstance(resolved, list) and all(
                    isinstance(item, str) for item in resolved
                ):
                    return {self._get_node_by_name(name) for name in resolved}
                if isinstance(resolved, str):
                    return {self._get_node_by_name(resolved)}
                raise TypeError(
                    "Conditional edge should return string or list of string only"
                )
            if len(result.content) != 1 or result.content[0].type != "text":
                raise ValueError(
                    "Conditional edge should return one text content block only"
                )
            return {self._get_node_by_name(result.content[0].text)}
        except (KeyError, ValueError):
            pass

        try:
            result = evaluate(target, context)
            if isinstance(result, str):
                return {self._get_node_by_name(result)}
            if isinstance(result, list) and all(
                isinstance(item, str) for item in result
            ):
                return {self._get_node_by_name(name) for name in result}
            raise ValueError(
                f"CEL expression must return str or list[str], got {type(result)}"
            )
        except Exception as exc:
            raise ValueError(f"Invalid edge target '{target}': {exc}") from exc
