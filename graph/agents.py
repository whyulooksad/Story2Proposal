from __future__ import annotations

import sys

from src import Agent, Hook

from config import load_prompt


def workflow_server_config() -> dict[str, object]:
    return {
        "command": sys.executable,
        "args": ["-m", "servers.workflow"],
    }


def _make_agent(
    name: str,
    model: str,
    prompt_name: str,
    *,
    on_start: str | None = None,
    on_end: str | None = None,
) -> Agent:
    hooks = []
    if on_start is not None or on_end is not None:
        hooks.append(Hook(on_start=on_start, on_end=on_end))
    return Agent(
        name=name,
        model=model,
        instructions=load_prompt(prompt_name),
        hooks=hooks,
    )


def build_agents(model: str) -> dict[str, Agent]:
    return {
        "architect": _make_agent(
            "architect",
            model,
            "architect.md",
            on_end="mcp__s2p_workflow__capture_architect_output",
        ),
        "section_writer": _make_agent(
            "section_writer",
            model,
            "section_writer.md",
            on_end="mcp__s2p_workflow__capture_section_writer_output",
        ),
        "reasoning_evaluator": _make_agent(
            "reasoning_evaluator",
            model,
            "reasoning_evaluator.md",
            on_end="mcp__s2p_workflow__capture_reasoning_feedback",
        ),
        "structure_evaluator": _make_agent(
            "structure_evaluator",
            model,
            "structure_evaluator.md",
            on_end="mcp__s2p_workflow__capture_structure_feedback",
        ),
        "visual_evaluator": _make_agent(
            "visual_evaluator",
            model,
            "visual_evaluator.md",
            on_end="mcp__s2p_workflow__capture_visual_feedback",
        ),
        "review_controller": _make_agent(
            "review_controller",
            model,
            "review_controller.md",
            on_start="mcp__s2p_workflow__apply_review_cycle",
        ),
        "refiner": _make_agent(
            "refiner",
            model,
            "refiner.md",
            on_end="mcp__s2p_workflow__capture_refiner_output",
        ),
        "renderer": _make_agent(
            "renderer",
            model,
            "renderer.md",
            on_start="mcp__s2p_workflow__render_and_finalize",
        ),
    }
