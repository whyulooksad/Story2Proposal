from __future__ import annotations

import sys

from src import Agent, Edge, Hook

from story2proposal.config import load_prompt


def build_story2proposal_graph(model: str) -> Agent:
    workflow_server = {
        "command": sys.executable,
        "args": ["-m", "story2proposal.tools.workflow_server"],
    }

    architect = Agent(
        name="architect",
        model=model,
        instructions=load_prompt("architect.md"),
        mcpServers={"s2p_workflow": workflow_server},
        hooks=[Hook(on_end="mcp__s2p_workflow__capture_architect_output")],
    )
    section_writer = Agent(
        name="section_writer",
        model=model,
        instructions=load_prompt("section_writer.md"),
        mcpServers={"s2p_workflow": workflow_server},
        hooks=[Hook(on_end="mcp__s2p_workflow__capture_section_writer_output")],
    )
    reasoning_evaluator = Agent(
        name="reasoning_evaluator",
        model=model,
        instructions=load_prompt("reasoning_evaluator.md"),
        mcpServers={"s2p_workflow": workflow_server},
        hooks=[Hook(on_end="mcp__s2p_workflow__capture_reasoning_feedback")],
    )
    structure_evaluator = Agent(
        name="structure_evaluator",
        model=model,
        instructions=load_prompt("structure_evaluator.md"),
        mcpServers={"s2p_workflow": workflow_server},
        hooks=[Hook(on_end="mcp__s2p_workflow__capture_structure_feedback")],
    )
    visual_evaluator = Agent(
        name="visual_evaluator",
        model=model,
        instructions=load_prompt("visual_evaluator.md"),
        mcpServers={"s2p_workflow": workflow_server},
        hooks=[Hook(on_end="mcp__s2p_workflow__capture_visual_feedback")],
    )
    review_controller = Agent(
        name="review_controller",
        model=model,
        instructions=load_prompt("review_controller.md"),
        mcpServers={"s2p_workflow": workflow_server},
        hooks=[Hook(on_start="mcp__s2p_workflow__apply_review_cycle")],
    )
    refiner = Agent(
        name="refiner",
        model=model,
        instructions=load_prompt("refiner.md"),
        mcpServers={"s2p_workflow": workflow_server},
        hooks=[Hook(on_end="mcp__s2p_workflow__capture_refiner_output")],
    )
    renderer = Agent(
        name="renderer",
        model=model,
        instructions=load_prompt("renderer.md"),
        mcpServers={"s2p_workflow": workflow_server},
        hooks=[Hook(on_start="mcp__s2p_workflow__render_and_finalize")],
    )

    return Agent(
        name="orchestrator",
        model=model,
        instructions=load_prompt("orchestrator.md"),
        mcpServers={"s2p_workflow": workflow_server},
        nodes={
            architect,
            section_writer,
            reasoning_evaluator,
            structure_evaluator,
            visual_evaluator,
            review_controller,
            refiner,
            renderer,
        },
        edges={
            Edge(source="orchestrator", target="architect"),
            Edge(source="architect", target="mcp__s2p_workflow__route_after_architect"),
            Edge(source="section_writer", target="reasoning_evaluator"),
            Edge(source="section_writer", target="structure_evaluator"),
            Edge(source="section_writer", target="visual_evaluator"),
            Edge(
                source=("reasoning_evaluator", "structure_evaluator", "visual_evaluator"),
                target="review_controller",
            ),
            Edge(
                source="review_controller",
                target="mcp__s2p_workflow__route_after_review_cycle",
            ),
            Edge(source="refiner", target="renderer"),
        },
    )
