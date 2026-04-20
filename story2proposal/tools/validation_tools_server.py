from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from story2proposal.workflow.context_ops import (
    aggregate_current_feedback,
    validate_citation_slots,
    validate_section_coverage,
    validate_visual_references,
)

server = FastMCP("s2p_validation")


@server.tool()
async def validate_section_coverage_tool(section: dict, draft: dict) -> dict:
    return {"issues": validate_section_coverage(section, draft)}


@server.tool()
async def validate_visual_references_tool(section: dict, draft: dict) -> dict:
    return {"issues": validate_visual_references(section, draft)}


@server.tool()
async def validate_citation_slots_tool(section: dict, draft: dict) -> dict:
    return {"issues": validate_citation_slots(section, draft)}


@server.tool()
async def aggregate_feedback_tool(context: dict) -> dict:
    return aggregate_current_feedback(context)


if __name__ == "__main__":
    server.run()
