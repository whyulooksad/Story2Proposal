from __future__ import annotations

"""Story2Proposal 的写作产物模型。

这一层承载 section writer、refiner 和 renderer 的结构化输出，
让 review、render 和持久化逻辑都围绕同一套对象工作。
"""

from typing import Any

from pydantic import BaseModel, Field


class StoryTrace(BaseModel):
    """正文片段与 story 字段之间的追踪关系。"""

    story_field: str
    summary: str


class EvidenceTrace(BaseModel):
    """正文使用的 evidence trace。"""

    evidence_id: str
    usage: str
    supports_claim_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)


class SectionDraft(BaseModel):
    """section writer 产出的单个章节草稿。"""

    section_id: str
    title: str
    content: str
    referenced_visual_ids: list[str] = Field(default_factory=list)
    referenced_citation_ids: list[str] = Field(default_factory=list)
    covered_claim_ids: list[str] = Field(default_factory=list)
    story_traces: list[StoryTrace] = Field(default_factory=list)
    evidence_traces: list[EvidenceTrace] = Field(default_factory=list)
    terminology_used: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)


class FinalizedSection(BaseModel):
    """进入最终 renderer 之前已经收敛好的 section 视图。"""

    section_id: str
    title: str
    content: str
    notes_applied: list[str] = Field(default_factory=list)


class SectionRewrite(BaseModel):
    """refiner 在全局阶段执行的整段级 section 重写。"""

    section_id: str
    title: str
    rewritten_content: str
    rationale: str
    preserved_claim_ids: list[str] = Field(default_factory=list)
    preserved_visual_ids: list[str] = Field(default_factory=list)
    preserved_citation_ids: list[str] = Field(default_factory=list)


class RefinerOutput(BaseModel):
    """refiner 产出的全局重写与收敛结果。"""

    abstract_override: str | None = None
    rewrite_goals: list[str] = Field(default_factory=list)
    section_rewrites: list[SectionRewrite] = Field(default_factory=list)
    terminology_updates: dict[str, str] = Field(default_factory=dict)
    contract_patches: list[dict[str, Any]] = Field(default_factory=list)


class RenderValidationReport(BaseModel):
    """renderer 的确定性校验报告。"""

    passed: bool = True
    duplicate_labels: list[str] = Field(default_factory=list)
    duplicate_citation_keys: list[str] = Field(default_factory=list)
    unresolved_visual_references: list[str] = Field(default_factory=list)
    unresolved_citation_references: list[str] = Field(default_factory=list)
    missing_visual_explanations: list[str] = Field(default_factory=list)
    citation_grounding_gaps: list[str] = Field(default_factory=list)
    terminology_drift: list[str] = Field(default_factory=list)
    duplicate_artifact_occurrences: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RenderedManuscript(BaseModel):
    """renderer 产出的最终稿件。"""

    markdown: str
    latex: str
    finalized_sections: list[FinalizedSection] = Field(default_factory=list)
    validation: RenderValidationReport = Field(default_factory=RenderValidationReport)
    warnings: list[str] = Field(default_factory=list)
