from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IssueItem(BaseModel):
    issue_id: str
    description: str
    severity: Literal["low", "medium", "high"] = "medium"


class SuggestedAction(BaseModel):
    action: str
    rationale: str | None = None


class ContractPatch(BaseModel):
    patch_type: Literal[
        "append_glossary",
        "set_section_status",
        "add_required_citation",
        "add_required_visual",
        "mark_claim_verified",
    ]
    target_id: str
    value: str


class EvaluationFeedback(BaseModel):
    evaluator_type: str
    status: Literal["pass", "revise", "fail"]
    score: float | None = None
    issues: list[IssueItem] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    contract_patches: list[ContractPatch] = Field(default_factory=list)
