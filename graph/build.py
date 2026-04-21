from __future__ import annotations

from src import Agent, Edge

from config import load_prompt

from .agents import build_agents, workflow_server_config


def build_story2proposal_graph(model: str) -> Agent:
    agents = build_agents(model)
    return Agent(
        name="orchestrator",
        model=model,
        instructions=load_prompt("orchestrator.md"),
        mcpServers={"s2p_workflow": workflow_server_config()},
        nodes=set(agents.values()),
        edges={
            Edge(source="orchestrator", target="architect"),
            Edge(source="architect", target="section_writer"),
            Edge(source="section_writer", target="reasoning_evaluator"),
            Edge(source="section_writer", target="structure_evaluator"),
            Edge(source="section_writer", target="visual_evaluator"),
            Edge(
                source=("reasoning_evaluator", "structure_evaluator", "visual_evaluator"),
                target="review_controller",
            ),
            Edge(source="review_controller", target="runtime.next_node"),
            Edge(source="refiner", target="renderer"),
        },
    )
