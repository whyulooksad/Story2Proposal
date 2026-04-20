# Agent Graph Framework

一个轻量的、图驱动的 Agent 框架。它不是“LLM + 顺序工具循环”，而是把 `Agent`、`Tool`、`Edge` 都当成图里的节点和边，在一次运行里动态创建子 Agent、追加边、执行 MCP 工具，并沿着图继续调度。

## 这个框架能做什么								

- 运行单个 Agent，对话、调用工具、返回消息结果
- 把多个 Agent 组织成一个本地执行图
- 让模型在运行时动态创建 Agent 和 Edge
- 接入 MCP server，把 MCP tool 暴露成 OpenAI function tool
- 用 Hook 在 LLM、Tool、Handoff 等生命周期阶段注入逻辑
- 给 Agent 挂载 Memory Provider，在执行前加载上下文、执行后持久化
- 给 Agent 挂载 Skill Catalog，在不同任务下限制可见工具范围
- 以普通模式运行，或以流式事件模式运行
- 把整个 Agent 图再暴露成一个 MCP server

## 核心概念

### 1. `Agent`

`Agent` 是这个框架的核心对象。

- 它本身是一个可执行节点
- 它也可以作为一个局部图的根节点
- 它可以包含子节点 `nodes`
- 它可以通过 `edges` 描述控制流

最小示例：

```python
from src import Agent

agent = Agent(
    name="assistant",
    model="qwen-plus",
    instructions="You are a concise assistant. Always answer in Chinese.",
)
```

### 2. `Edge`

`Edge` 表示控制流边，从一个节点走到另一个节点。

```python
from src import Edge

Edge(source="root", target="writer")
```

也支持多源汇合：

```python
Edge(source=("planner", "researcher"), target="writer")
```

这表示 `planner` 和 `researcher` 都完成后，才会触发 `writer`。

### 3. `Tool`

`Tool` 是 MCP tool 的运行时节点表示。

MCP tool 会以这种名字暴露给模型：

```python
mcp__<server_name>__<tool_name>
```

例如：

```python
mcp__playwright__browser_navigate
```

### 4. `Hook`

`Hook` 用来在生命周期节点接 MCP tool。

支持的 hook 类型：

- `on_start`
- `on_end`
- `on_handoff`
- `on_tool_start`
- `on_tool_end`
- `on_llm_start`
- `on_llm_end`
- `on_chunk`

注意：

- Hook 值是 MCP tool 名称，不是 Python 回调
- Hook tool 必须返回 `structuredContent`
- Hook 返回的 `structuredContent` 会合并进运行时 `context`

示例：

```python
from src import Hook

hooks = [
    Hook(
        on_start="mcp__hook_demo__prepare_context",
        on_end="mcp__hook_demo__mark_finished",
    )
]
```

## 最常用语法

### 1. 创建一个最小 Agent

```python
from src import Agent

agent = Agent(
    name="assistant",
    model="qwen-plus",
    instructions="You are a Chinese assistant.",
)
```

字段说明：

- `name`: Agent 名称，图内必须唯一
- `model`: 调用的模型名
- `instructions`: system prompt 模板，支持 Jinja2 渲染
- `nodes`: 子节点集合，可放 `Agent` 或运行时 `Tool`
- `edges`: 图中的边
- `hooks`: 生命周期 hook
- `mcpServers`: 当前 Agent 额外挂载的 MCP server
- `client`: 可选，自定义 `AsyncOpenAI` 客户端

### 2. 调用 Agent

```python
result = await agent(
    {
        "messages": [
            {"role": "user", "content": "请用中文介绍这个框架。"}
        ],
        "temperature": 0.2,
    }
)
```

返回结果结构：

```python
{
    "messages": [...]
}
```

这里返回的是这次执行新增的消息，不一定只包含最后一条 assistant 消息，也可能包含 tool message、下游 agent 产生的消息。

### 3. 给 Agent 传 `context`

`instructions` 支持 Jinja2 模板，所以可以把外部上下文传进去：

```python
result = await agent(
    {
        "messages": [
            {"role": "user", "content": "写一段首页文案"}
        ]
    },
    context={"tone": "专业", "audience": "企业客户"},
)
```

```python
agent = Agent(
    name="writer",
    model="qwen-plus",
    instructions="""
You are a copywriting agent.
Tone: {{ tone }}
Audience: {{ audience }}
""".strip(),
)
```

### 4. 定义多 Agent 图

```python
from src import Agent, Edge

planner = Agent(
    name="planner",
    model="qwen-plus",
    instructions="You are a planning agent. Output a short plan in Chinese.",
)

writer = Agent(
    name="writer",
    model="qwen-plus",
    instructions="You are a writing agent. Produce the final Chinese answer.",
)

root = Agent(
    name="root",
    model="qwen-plus",
    instructions="Summarize the user request in one sentence.",
    nodes={planner, writer},
    edges={
        Edge(source="root", target="planner"),
        Edge(source="planner", target="writer"),
    },
)
```

运行时流程：

1. `root` 先执行
2. `root` 完成后触发 `planner`
3. `planner` 完成后触发 `writer`

### 5. 让模型动态创建 Agent 或 Edge

框架会自动把这些内建工具暴露给模型：

- `create_agent`
- `create_edge`
- 当前 agent 名
- 当前图中其他子 agent 名

这意味着模型在一轮输出里可以：

- 动态创建子 Agent
- 动态追加边
- 直接 handoff 给已有 Agent

不需要手动注册这些工具。

### 6. 接 MCP server

可以在全局 `.mcp.json` 配，也可以直接挂到某个 Agent 上：

```python
import sys

agent = Agent(
    name="desktop_agent",
    model="qwen-plus",
    instructions="Use MCP tools to finish desktop tasks.",
    mcpServers={
        "playwright": {
            "command": sys.executable,
            "args": ["path/to/playwright_server.py"],
        }
    },
)
```

运行时框架会：

1. 连接 MCP server
2. 拉取工具 schema
3. 把工具转换成 OpenAI function tool
4. 当模型调用工具时，创建一个运行时 `Tool` 节点
5. 执行工具后把结果变成 `tool` message 再回到图里

### 7. 使用 Hook

```python
from src import Agent, Hook

agent = Agent(
    name="hook_writer",
    model="qwen-plus",
    instructions="""
Tone: {{ tone }}
Audience: {{ target_audience }}
Write a short Chinese hero copy.
""".strip(),
    hooks=[
        Hook(
            on_start="mcp__hook_demo__prepare_brand_context",
            on_handoff="mcp__hook_demo__record_handoff",
            on_end="mcp__hook_demo__mark_run_finished",
        )
    ],
)
```

几点规则：

- `on_start` 在 agent 开始执行前触发
- `on_handoff` 在执行下游 `Agent` 前触发，包括动态创建的 agent
- `on_tool_start` / `on_tool_end` 包住 MCP tool 执行
- `on_llm_start` / `on_llm_end` 包住模型调用
- `on_chunk` 只在流式模式下触发

### 8. 使用 Memory

```python
from src import Agent, MemoryProvider

class DemoMemory(MemoryProvider):
    async def load_context(self, *, agent_name, messages, context):
        return {"preferred_style": "专业、简洁"}

    async def save(self, *, agent_name, messages, context):
        return None

agent = Agent(
    name="memory_writer",
    model="qwen-plus",
    instructions="Preferred style: {{ preferred_style }}",
).with_memory(DemoMemory())
```

运行顺序是：

1. `load_context(...)`
2. 执行 Agent 图
3. `save(...)`

### 9. 使用 Skill

```python
from src import Agent, SkillLoader

loader = SkillLoader("skills")

agent = Agent(
    name="desktop_agent",
    model="qwen-plus",
    instructions="You are a desktop automation agent.",
).with_skill_loader(loader, agent_name="desktop_agent")
```

Skill 模式下有几个关键行为：

- 如果挂了 skill catalog，但还没激活 skill，MCP tool 默认不可见
- 模型会先看到 skill catalog，并被要求先选择 skill
- 激活 skill 后，工具可见范围由 `toolNames` /`visibleMcpServers` 决定
- 动态创建的子 Agent 会继承 skill 边界

### 10. 使用流式运行

```python
async for event in agent.stream(
    {
        "messages": [
            {"role": "user", "content": "请简要解释什么是图驱动 Agent。"}
        ]
    }
):
    if event["type"] == "token":
        print(event["delta"], end="", flush=True)
```

常见事件类型：

- `agent_start`
- `llm_start`
- `chunk`
- `token`
- `completion_message`
- `message`
- `tool_result`
- `agent_end`
- `done`

## 一个完整示例

### 单 Agent

```python
import asyncio
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
                        "content": "请介绍这个框架的定位。"
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
```

### 多 Agent Handoff

```python
import asyncio
from src import Agent, Edge


async def main() -> None:
    planner = Agent(
        name="planner",
        model="qwen-plus",
        instructions="You are a planning agent. Output a short 3-step plan in Chinese.",
    )
    writer = Agent(
        name="writer",
        model="qwen-plus",
        instructions="You are a writing agent. Produce the final answer in Chinese.",
    )

    root = Agent(
        name="root",
        model="qwen-plus",
        instructions="You are the entry agent. Summarize the request in one sentence.",
        nodes={planner, writer},
        edges={
            Edge(source="root", target="planner"),
            Edge(source="planner", target="writer"),
        },
    )

    try:
        result = await root(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "我要做一个企业知识库问答助手，请给我一个最小可行方案。"
                    }
                ],
                "temperature": 0.3,
            }
        )
        for message in result["messages"]:
            print(message)
    finally:
        for agent in root.agents.values():
            await agent._mcp_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
```

## 运行机制简述

一次 `await agent(...)` 的大致流程是：

1. 加载 MCP server
2. 加载 memory context
3. 拼 system prompt
4. 暴露当前可见工具
5. 调用 LLM
6. 把 `tool_calls` 转成图节点和边
7. 继续执行所有被触发的下游节点
8. 执行 hook
9. 保存 memory
10. 清理运行时临时 tool 节点

## 一些容易忽略的语法细节

- `instructions` 是模板，不只是纯字符串
- `name` 必须全图唯一，否则会报错
- `Hook` 配的是 `MCP tool` 名，不是 `Python` 函数
- `skill catalog` 已挂载但未激活时，`MCP tool` 默认不可见
- `Edge.target` 可以是节点名、MCP tool 名，或者对 `context` 求值的 CEL 表达式

## 对外暴露为 MCP server

也可以把整个 Agent 图暴露成 MCP server：

```python
from src import Agent, create_mcp_server

root = Agent(
    name="root_agent",
    model="qwen-plus",
    instructions="You are the root agent.",
)

server = create_mcp_server(root)
```

这样当前图里的每个可达 Agent 都会被注册成一个 MCP tool。
