from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from domain import (
    append_review,
    apply_review_cycle as apply_review_cycle_impl,
    initialize_contract,
    persist_run_state,
    refresh_prompt_views,
    render_markdown_manuscript,
    save_section_draft,
    set_blueprint_and_contract,
    store_refiner_output,
    store_render_output,
    trim_blueprint_to_sections,
)
from llm_io import parse_model
from schemas import (
    EvaluationFeedback,
    ManuscriptBlueprint,
    RefinerOutput,
    ResearchStory,
    SectionDraft,
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


def _agent_name(agent: dict[str, Any] | None) -> str | None:
    return (agent or {}).get("name")


def _parse_agent_output(
    messages: list[dict[str, Any]],
    agent: dict[str, Any] | None,
    schema: type[Any],
) -> Any:
    return parse_model(_latest_agent_message(messages, _agent_name(agent)), schema)


def _store_feedback(
    context: dict[str, Any],
    evaluator_type: str,
    feedback: EvaluationFeedback,
) -> dict[str, Any]:
    if feedback.evaluator_type != evaluator_type:
        feedback.evaluator_type = evaluator_type
    append_review(context, feedback)
    return context


@server.tool()
async def capture_architect_output(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blueprint = _parse_agent_output(messages, agent, ManuscriptBlueprint)
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
    draft = _parse_agent_output(messages, agent, SectionDraft)
    save_section_draft(context, draft)
    return context


def _capture_feedback(
    evaluator_type: str,
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    feedback = _parse_agent_output(messages, agent, EvaluationFeedback)
    return _store_feedback(context, evaluator_type, feedback)


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
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


@server.tool()
async def capture_refiner_output(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = _parse_agent_output(messages, agent, RefinerOutput)
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
