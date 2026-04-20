from __future__ import annotations

from pydantic import BaseModel, Field


class SectionPlan(BaseModel):
    section_id: str
    title: str
    goal: str
    must_cover: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    visual_refs: list[str] = Field(default_factory=list)
    citation_refs: list[str] = Field(default_factory=list)
    input_dependencies: list[str] = Field(default_factory=list)


class VisualPlan(BaseModel):
    artifact_id: str
    kind: str
    label: str
    caption_brief: str
    target_sections: list[str] = Field(default_factory=list)
    semantic_role: str


class ManuscriptBlueprint(BaseModel):
    title: str
    abstract_plan: str
    section_plans: list[SectionPlan]
    visual_plan: list[VisualPlan] = Field(default_factory=list)
    writing_order: list[str]
