from __future__ import annotations

from pydantic import BaseModel, Field


class SectionDraft(BaseModel):
    section_id: str
    title: str
    content: str
    referenced_visual_ids: list[str] = Field(default_factory=list)
    referenced_citation_ids: list[str] = Field(default_factory=list)
    covered_claim_ids: list[str] = Field(default_factory=list)


class RefinerOutput(BaseModel):
    abstract_override: str | None = None
    section_notes: dict[str, str] = Field(default_factory=dict)
    global_notes: list[str] = Field(default_factory=list)


class RenderedManuscript(BaseModel):
    markdown: str
    latex: str
    warnings: list[str] = Field(default_factory=list)
