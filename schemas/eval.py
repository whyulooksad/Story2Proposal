from __future__ import annotations

"""Story2Proposal 的评测与 benchmark 协议模型。"""

from typing import Literal

from pydantic import BaseModel, Field


DimensionName = Literal[
    "structural_integrity",
    "writing_clarity",
    "methodological_rigor",
    "experimental_substance",
    "citation_hygiene",
    "reproducibility",
    "formatting_stability",
    "visual_communication",
]


class EvaluationCriterion(BaseModel):
    """单条评测准则及其通过情况。"""

    criterion_id: str
    label: str
    passed: bool
    evidence: list[str] = Field(default_factory=list)


class EvaluationDimension(BaseModel):
    """一个评测维度的打分与依据。"""

    name: DimensionName
    score: float
    passed: bool
    criteria: list[EvaluationCriterion] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class ManuscriptEvaluationReport(BaseModel):
    """整篇稿件的结构化评测结果。"""

    protocol_version: str = "story2proposal-rubric-v3"
    overall_score: float
    dimensions: list[EvaluationDimension] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class BenchmarkCandidate(BaseModel):
    """benchmark 中的一个候选稿件。"""

    candidate_id: str
    label: str
    source: str
    report: ManuscriptEvaluationReport


class DimensionDelta(BaseModel):
    """某个维度相对 baseline 的分数变化。"""

    name: DimensionName
    baseline_score: float
    candidate_score: float
    delta: float


class BenchmarkComparison(BaseModel):
    """候选稿件相对 baseline 的对比结果。"""

    candidate_id: str
    baseline_id: str
    overall_delta: float
    dimension_deltas: list[DimensionDelta] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)


class BenchmarkSuiteReport(BaseModel):
    """面向论文实验复现风格的 benchmark suite。"""

    protocol_version: str = "story2proposal-benchmark-v1"
    benchmark_name: str
    primary_candidate_id: str
    winner_candidate_id: str
    candidates: list[BenchmarkCandidate] = Field(default_factory=list)
    comparisons: list[BenchmarkComparison] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
