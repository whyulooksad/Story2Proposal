from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from story2proposal.workflow.context_ops import render_markdown_manuscript

server = FastMCP("s2p_render")


@server.tool()
async def render_manuscript(context: dict) -> dict:
    return render_markdown_manuscript(context).model_dump(mode="json")


if __name__ == "__main__":
    server.run()
