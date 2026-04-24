from __future__ import annotations

"""Story2Proposal 的评审反馈模型。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class IssueItem(BaseModel):
    """一条具体问题项。"""

    issue_id: str
    description: str
    severity: Literal["low", "medium", "high"] = "medium"
    issue_type: str | None = None
    target_id: str | None = None


class SuggestedAction(BaseModel):
    """一条建议动作。"""

    action: str
    rationale: str | None = None
    target_id: str | None = None


class ContractPatch(BaseModel):
    """一条可直接应用到 contract 的结构化 patch。"""

    patch_type: Literal[
        "append_glossary",
        "set_section_status",
        "add_required_citation",
        "add_required_visual",
        "add_required_evidence",
        "mark_claim_verified",
        "update_visual_placement",
        "require_visual_explanation",
        "add_validation_rule",
        "tighten_validation_rule",
        "add_section_dependency",
        "register_revision_note",
        "ground_citation_to_claim",
    ]
    target_id: str
    value: Any = None


class EvaluationFeedback(BaseModel):
    """一次 evaluator 输出的完整结构化反馈。"""

    evaluator_type: Literal["reasoning", "data_fidelity", "visual", "structure"]
    status: Literal["pass", "revise", "fail"]
    score: float | None = None
    confidence: float | None = None
    issues: list[IssueItem] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    contract_patches: list[ContractPatch] = Field(default_factory=list)


class AggregatedFeedback(BaseModel):
    """review_controller 聚合后的反馈结果。"""

    status: Literal["pass", "revise", "fail"]
    issues: list[str] = Field(default_factory=list)
    patches: list[ContractPatch] = Field(default_factory=list)
    contributing_evaluators: list[str] = Field(default_factory=list)
    deterministic_checks: dict[str, list[str]] = Field(default_factory=dict)
