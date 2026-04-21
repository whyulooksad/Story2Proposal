from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StyleGuide(BaseModel):
    tone: str = "scientific"
    citation_style: str = "author-year placeholder"
    section_style: str = "structured"
    figure_policy: str = "use explicit placeholders until real figures are available"


class SectionContract(BaseModel):
    section_id: str
    title: str
    purpose: str
    required_claims: list[str] = Field(default_factory=list)
    required_evidence_ids: list[str] = Field(default_factory=list)
    required_visual_ids: list[str] = Field(default_factory=list)
    required_citation_ids: list[str] = Field(default_factory=list)
    depends_on_sections: list[str] = Field(default_factory=list)
    status: str = "pending"
    draft_path: str | None = None
    latest_draft_version: int = 0


class VisualArtifact(BaseModel):
    artifact_id: str
    kind: str
    label: str
    caption_brief: str
    semantic_role: str
    source_evidence_ids: list[str] = Field(default_factory=list)
    target_sections: list[str] = Field(default_factory=list)
    placement_hint: str | None = None
    render_status: str = "planned"


class CitationSlot(BaseModel):
    citation_id: str
    citation_key: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None


class ClaimEvidenceLink(BaseModel):
    claim_id: str
    claim_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    section_id: str
    verified: bool = False


class ValidationRule(BaseModel):
    rule_id: str
    rule_type: str
    description: str
    severity: str = "warning"
    enabled: bool = True


class RevisionRecord(BaseModel):
    stage: str
    agent: str
    summary: str
    affected_sections: list[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ManuscriptContract(BaseModel):
    contract_id: str
    version: int = 1
    paper_title: str | None = None
    target_venue: str | None = None
    style_guide: StyleGuide = Field(default_factory=StyleGuide)
    sections: list[SectionContract] = Field(default_factory=list)
    visuals: list[VisualArtifact] = Field(default_factory=list)
    citations: list[CitationSlot] = Field(default_factory=list)
    glossary: list[str] = Field(default_factory=list)
    claim_evidence_links: list[ClaimEvidenceLink] = Field(default_factory=list)
    validation_rules: list[ValidationRule] = Field(default_factory=list)
    revision_log: list[RevisionRecord] = Field(default_factory=list)
    global_status: dict[str, str] = Field(default_factory=dict)
