from __future__ import annotations

"""Story2Proposal 应用层图构建。"""

from src import Agent, Edge

from config import load_prompt

from .agents import build_agents, workflow_server_config


def build_story2proposal_graph(model: str) -> Agent:
    """构造 Story2Proposal 的根图。"""
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
            Edge(source="section_writer", target="data_fidelity_evaluator"),
            Edge(source="section_writer", target="visual_evaluator"),
            Edge(
                source=("reasoning_evaluator", "data_fidelity_evaluator", "visual_evaluator"),
                target="review_controller",
            ),
            Edge(source="review_controller", target="runtime.next_node"),
            Edge(source="refiner", target="renderer"),
        },
    )
