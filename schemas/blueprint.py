from __future__ import annotations

"""Story2Proposal 的论文蓝图模型。

这一层描述 architect 阶段产出的高层写作规划：有哪些章节、每个章节要完
成什么、需要哪些证据/引用/图表，以及整体写作顺序。
"""

from pydantic import BaseModel, Field


class SectionPlan(BaseModel):
    """蓝图中的单个章节规划。"""
    section_id: str
    title: str
    goal: str
    must_cover: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    visual_refs: list[str] = Field(default_factory=list)
    citation_refs: list[str] = Field(default_factory=list)
    input_dependencies: list[str] = Field(default_factory=list)
    source_story_fields: list[str] = Field(default_factory=list)


class VisualPlan(BaseModel):
    """蓝图中的单个视觉资产规划。"""
    artifact_id: str
    kind: str
    label: str
    caption_brief: str
    target_sections: list[str] = Field(default_factory=list)
    semantic_role: str
    source_evidence_ids: list[str] = Field(default_factory=list)


class ManuscriptBlueprint(BaseModel):
    """architect 产出的整篇论文蓝图。"""
    title: str
    abstract_plan: str
    section_plans: list[SectionPlan]
    visual_plan: list[VisualPlan] = Field(default_factory=list)
    writing_order: list[str]
