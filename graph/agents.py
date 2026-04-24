from __future__ import annotations

"""Story2Proposal 应用层 Agent 定义。"""

import sys

from src import Agent, Hook

from config import PACKAGE_ROOT, load_prompt


def workflow_server_config() -> dict[str, object]:
    """返回应用层 workflow MCP server 的启动配置。"""
    return {
        "command": sys.executable,
        "args": ["-m", "servers.workflow"],
        "cwd": str(PACKAGE_ROOT),
    }


def _make_agent(
    name: str,
    model: str,
    prompt_name: str,
    *,
    on_start: str | None = None,
    on_end: str | None = None,
) -> Agent:
    """按统一规则构造一个应用层 Agent。"""
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
    """构造 Story2Proposal 流程中所有静态 Agent 节点。"""
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
        "visual_repair": _make_agent(
            "visual_repair",
            model,
            "visual_repair.md",
            on_end="mcp__s2p_workflow__capture_visual_repair_output",
        ),
        "reasoning_evaluator": _make_agent(
            "reasoning_evaluator",
            model,
            "reasoning_evaluator.md",
            on_end="mcp__s2p_workflow__capture_reasoning_feedback",
        ),
        "data_fidelity_evaluator": _make_agent(
            "data_fidelity_evaluator",
            model,
            "data_fidelity_evaluator.md",
            on_end="mcp__s2p_workflow__capture_data_fidelity_feedback",
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
