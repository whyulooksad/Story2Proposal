from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from story2proposal.schemas import ManuscriptBlueprint, ManuscriptContract, ResearchStory
from story2proposal.workflow.context_ops import initialize_contract

server = FastMCP("s2p_contract")


@server.tool()
async def initialize_contract_tool(
    story: dict,
    blueprint: dict,
) -> dict:
    contract = initialize_contract(
        ResearchStory.model_validate(story),
        ManuscriptBlueprint.model_validate(blueprint),
    )
    return contract.model_dump(mode="json")


@server.tool()
async def get_current_section_contract(contract: dict, section_id: str) -> dict | None:
    for section in ManuscriptContract.model_validate(contract).sections:
        if section.section_id == section_id:
            return section.model_dump(mode="json")
    return None


@server.tool()
async def snapshot_contract(contract: dict) -> dict:
    return ManuscriptContract.model_validate(contract).model_dump(mode="json")


if __name__ == "__main__":
    server.run()
