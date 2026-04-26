from __future__ import annotations

"""Story2Proposal 的执行期 contract 模型。

这一层定义写作阶段真正围绕的约束对象。它不只描述章节要求，还显式维护
claim、evidence、citation、visual、validation rule 和 revision log
之间的可追踪关系。
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class StyleGuide(BaseModel):
    """整篇稿件共享的全局风格约束。"""

    tone: str = "scientific"
    citation_style: str = "author-year placeholder"
    section_style: str = "structured"
    figure_policy: str = "use explicit placeholders until real figures are available"
    output_language: Literal["en", "zh"] = "en"


class TerminologyItem(BaseModel):
    """全局术语表条目，用于 refiner 做术语统一。"""

    term: str
    preferred_form: str
    definition: str | None = None
    aliases: list[str] = Field(default_factory=list)


class ClaimRequirement(BaseModel):
    """章节必须覆盖的 claim 及其证据约束。"""

    claim_id: str
    claim_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    source_story_fields: list[str] = Field(default_factory=list)
    coverage_status: Literal["pending", "covered", "verified", "failed"] = "pending"


class SectionVisualObligation(BaseModel):
    """章节层面的 visual obligation。"""

    artifact_id: str
    required: bool = True
    explanation_required: bool = True
    placement_hint: str | None = None
    narrative_role: str | None = None


class SectionCitationObligation(BaseModel):
    """章节层面的 citation obligation。"""

    citation_id: str
    required: bool = True
    purpose: str | None = None
    grounded_claim_ids: list[str] = Field(default_factory=list)


class SectionContract(BaseModel):
    """执行期单个章节的写作 contract。"""

    section_id: str
    title: str
    purpose: str
    required_claims: list[str] = Field(default_factory=list)
    required_claim_ids: list[str] = Field(default_factory=list)
    claim_requirements: list[ClaimRequirement] = Field(default_factory=list)
    required_evidence_ids: list[str] = Field(default_factory=list)
    required_visual_ids: list[str] = Field(default_factory=list)
    required_citation_ids: list[str] = Field(default_factory=list)
    depends_on_sections: list[str] = Field(default_factory=list)
    source_story_fields: list[str] = Field(default_factory=list)
    visual_obligations: list[SectionVisualObligation] = Field(default_factory=list)
    citation_obligations: list[SectionCitationObligation] = Field(default_factory=list)
    status: Literal["pending", "drafted", "needs_revision", "approved", "failed"] = "pending"
    draft_path: str | None = None
    latest_draft_version: int = 0


class VisualArtifact(BaseModel):
    """执行期单个视觉资产的 contract 表达。"""

    artifact_id: str
    kind: Literal["figure", "table"]
    label: str
    canonical_label: str
    caption_brief: str
    semantic_role: str
    source_evidence_ids: list[str] = Field(default_factory=list)
    target_sections: list[str] = Field(default_factory=list)
    placement_hint: str | None = None
    placement_constraint: Literal["inline", "after_section", "before_section", "appendix", "unspecified"] = "unspecified"
    occurrence_policy: Literal["exactly_once", "at_least_once"] = "exactly_once"
    explanation_required: bool = True
    materialization_status: Literal["planned", "materialized", "missing"] = "planned"
    generator: str | None = None
    source_path: str | None = None
    rendered_path: str | None = None
    thumbnail_path: str | None = None
    object_map: list[dict[str, Any]] = Field(default_factory=list)
    resolved_references: list[str] = Field(default_factory=list)
    render_status: Literal["planned", "registered", "rendered", "missing", "duplicated"] = "planned"


class CitationSlot(BaseModel):
    """执行期单个引用槽位。"""

    citation_id: str
    citation_key: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    source_reference_id: str | None = None
    grounded_claim_ids: list[str] = Field(default_factory=list)
    required_sections: list[str] = Field(default_factory=list)
    status: Literal["planned", "used", "missing", "duplicate"] = "planned"


class ClaimEvidenceLink(BaseModel):
    """claim 与 supporting evidence 的绑定关系。"""

    claim_id: str
    claim_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    section_id: str
    source_story_fields: list[str] = Field(default_factory=list)
    verified: bool = False


class ValidationRule(BaseModel):
    """contract 内建的一条校验规则。"""

    rule_id: str
    rule_type: str
    description: str
    severity: Literal["low", "medium", "high"] = "medium"
    scope: Literal["document", "section", "visual", "citation", "claim"] = "document"
    target_id: str | None = None
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class RevisionRecord(BaseModel):
    """contract 在运行中的一条修订记录。"""

    revision_id: str
    stage: str
    agent: str
    summary: str
    affected_sections: list[str] = Field(default_factory=list)
    affected_artifacts: list[str] = Field(default_factory=list)
    patch_types: list[str] = Field(default_factory=list)
    contract_version: int = 1
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContractStatus(BaseModel):
    """整份 manuscript contract 的全局状态。"""

    state: str = "initialized"
    current_section_id: str | None = None
    completed_sections: list[str] = Field(default_factory=list)
    pending_sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ManuscriptContract(BaseModel):
    """整篇稿件在执行期的根 contract 对象。"""

    contract_id: str
    version: int = 1
    paper_title: str | None = None
    target_venue: str | None = None
    style_guide: StyleGuide = Field(default_factory=StyleGuide)
    sections: list[SectionContract] = Field(default_factory=list)
    visuals: list[VisualArtifact] = Field(default_factory=list)
    citations: list[CitationSlot] = Field(default_factory=list)
    glossary: list[TerminologyItem] = Field(default_factory=list)
    claim_evidence_links: list[ClaimEvidenceLink] = Field(default_factory=list)
    validation_rules: list[ValidationRule] = Field(default_factory=list)
    revision_log: list[RevisionRecord] = Field(default_factory=list)
    global_status: ContractStatus = Field(default_factory=ContractStatus)
