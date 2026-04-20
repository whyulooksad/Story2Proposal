from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

server = FastMCP("hook_demo")


@server.tool()
async def prepare_brand_context(
    messages: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(context or {})
    context["tone"] = "专业、简洁、偏企业级"
    context["target_audience"] = "企业软件采购者"
    context["headline_style"] = "短标题 + 两句价值说明"
    context["hook_agent_name"] = (agent or {}).get("name")
    context["hook_message_count"] = len(messages)
    return context


@server.tool()
async def mark_run_finished(
    messages: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(context or {})
    context["hook_finished"] = True
    context["final_message_count"] = len(messages)
    context["final_agent_name"] = (agent or {}).get("name")
    return context


if __name__ == "__main__":
    server.run()
