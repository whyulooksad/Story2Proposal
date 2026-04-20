from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from story2proposal.llm_io import parse_model
from story2proposal.schemas import (
    EvaluationFeedback,
    ManuscriptBlueprint,
    RefinerOutput,
    ResearchStory,
    SectionDraft,
)
from story2proposal.workflow.context_ops import (
    apply_review_cycle as apply_review_cycle_impl,
    initialize_contract,
    refresh_prompt_views,
    render_markdown_manuscript,
    save_section_draft,
    set_blueprint_and_contract,
    store_refiner_output,
    store_render_output,
    trim_blueprint_to_sections,
    append_review,
)

server = FastMCP("s2p_workflow")


def _latest_agent_message(
    messages: list[dict[str, Any]],
    agent_name: str | None,
) -> str:
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        if agent_name is not None and message.get("name") != agent_name:
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
    raise ValueError(f"No assistant message found for agent {agent_name!r}")


@server.tool()
async def capture_architect_output(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blueprint = parse_model(
        _latest_agent_message(messages, (agent or {}).get("name")),
        ManuscriptBlueprint,
    )
    story = ResearchStory.model_validate(context["story"])
    active_sections = story.metadata.get("active_sections")
    if isinstance(active_sections, list) and active_sections:
        blueprint = trim_blueprint_to_sections(
            blueprint,
            [str(section_id) for section_id in active_sections],
        )
    contract = initialize_contract(story, blueprint)
    set_blueprint_and_contract(context, blueprint, contract)
    return context


@server.tool()
async def capture_section_writer_output(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    draft = parse_model(
        _latest_agent_message(messages, (agent or {}).get("name")),
        SectionDraft,
    )
    save_section_draft(context, draft)
    return context


def _capture_feedback(
    evaluator_type: str,
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    feedback = parse_model(
        _latest_agent_message(messages, (agent or {}).get("name")),
        EvaluationFeedback,
    )
    if feedback.evaluator_type != evaluator_type:
        feedback.evaluator_type = evaluator_type
    append_review(context, feedback)
    return context


@server.tool()
async def capture_reasoning_feedback(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _capture_feedback("reasoning", messages, context, agent)


@server.tool()
async def capture_structure_feedback(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _capture_feedback("structure", messages, context, agent)


@server.tool()
async def capture_visual_feedback(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _capture_feedback("visual", messages, context, agent)


@server.tool()
async def apply_review_cycle(
    context: dict[str, Any],
    messages: list[dict[str, Any]] | None = None,
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del messages, agent
    apply_review_cycle_impl(context)
    return context


@server.tool()
async def route_after_architect(
    run_id: str | None = None,
    story: dict[str, Any] | None = None,
    blueprint: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    drafts: dict[str, Any] | None = None,
    reviews: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
) -> dict[str, str]:
    refresh_prompt_views(
        {
            "run_id": run_id,
            "story": story,
            "blueprint": blueprint,
            "contract": contract,
            "drafts": drafts or {},
            "reviews": reviews or {},
            "artifacts": artifacts or {},
            "runtime": runtime or {},
        }
    )
    return {"result": "section_writer"}


@server.tool()
async def route_after_review_cycle(
    run_id: str | None = None,
    story: dict[str, Any] | None = None,
    blueprint: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    drafts: dict[str, Any] | None = None,
    reviews: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
) -> dict[str, str]:
    del run_id, story, blueprint, contract, drafts, reviews, artifacts
    if (runtime or {}).get("current_section_id") is None:
        return {"result": "refiner"}
    return {"result": "section_writer"}


@server.tool()
async def capture_refiner_output(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = parse_model(
        _latest_agent_message(messages, (agent or {}).get("name")),
        RefinerOutput,
    )
    store_refiner_output(context, output)
    return context


@server.tool()
async def render_and_finalize(
    context: dict[str, Any],
    messages: list[dict[str, Any]] | None = None,
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del messages, agent
    rendered = render_markdown_manuscript(context)
    store_render_output(context, rendered)
    return context


if __name__ == "__main__":
    server.run()
