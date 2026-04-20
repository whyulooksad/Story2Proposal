from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ExperimentSpec(BaseModel):
    experiment_id: str
    name: str
    setup: str
    dataset: str
    metrics: list[str] = Field(default_factory=list)
    result_summary: str


class ReferenceSpec(BaseModel):
    reference_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    notes: str | None = None


class ArtifactSeed(BaseModel):
    artifact_id: str
    kind: str
    title: str
    description: str
    target_sections: list[str] = Field(default_factory=list)


class ResearchStory(BaseModel):
    story_id: str
    title_hint: str | None = None
    topic: str
    problem_statement: str
    motivation: str
    core_idea: str
    method_summary: str
    contributions: list[str]
    experiments: list[ExperimentSpec]
    baselines: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    references: list[ReferenceSpec] = Field(default_factory=list)
    assets: list[ArtifactSeed] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_path(cls, path: str | Path) -> "ResearchStory":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
