from __future__ import annotations

import asyncio
import json
import logging
import uuid
import warnings
from collections.abc import AsyncGenerator
from collections import defaultdict
from copy import deepcopy
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
from .nodes import Node, Tool
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

    async def __call__(
        self,
        params: CompletionCreateParams | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> MessagesState:
        """运行 Agent"""
        for name, server_params in (
            (settings.mcp_servers if settings is not None else {}) | self.mcp_servers
        ).items():
            await self._mcp_manager.add_server(name, server_params)
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
                self._register_tool_calls(tool_calls, messages)
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
                            self._share_runtime_with_child(target)
                            task = tg.create_task(
                                target({"messages": messages}, context=context)
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
        for name, server_params in (
            (settings.mcp_servers if settings is not None else {}) | self.mcp_servers
        ).items():
            await self._mcp_manager.add_server(name, server_params)
        if params is None:
            params = {"messages": []}
        params = deepcopy(params)
        params["stream"] = True
        if context is None:
            context = {}
        self._visited.clear()
        self._cleanup_runtime_tools()
        try:
            async for event in self._stream_graph(params=params, context=context):
                yield event
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
                self._register_tool_calls(tool_calls, messages)
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
                        self._share_runtime_with_child(target)
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

    def _builtin_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """返回当前 Agent 默认可见的 graph 管理工具"""
        return [
            *[
                agent.as_call_tool()
                for agent in [self, *self.nodes]
                if isinstance(agent, Agent)
            ],
            Agent.as_init_tool(),
            Edge.as_tool(),
        ]

    def _visible_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """返回当前轮次模型可见的全部工具"""
        hook_names = [
            getattr(hook, hook_type)
            for hook in self.hooks
            for hook_type in get_args(HookType)
            if getattr(hook, hook_type, None) is not None
        ]
        return [
            tool
            for tool in self._mcp_manager.tools
            if tool["function"]["name"] not in hook_names
        ] + self._builtin_tools()

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

    def _register_tool_calls(
        self,
        tool_calls: Iterable[ChatCompletionMessageToolCallUnionParam],
        messages: list[ChatCompletionMessageParam],
    ) -> None:
        """把 assistant 返回的 tool_calls 注册成 graph 中的 node 和 edge"""
        for tool_call in tool_calls:
            if tool_call["type"] == "custom":
                continue
            name = tool_call["function"]["name"]
            match name:
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
            result = await self._mcp_manager.call_tool(target, context or {})
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
        except KeyError:
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
