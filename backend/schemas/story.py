from __future__ import annotations

"""Story2Proposal 的输入故事模型。

这一层定义系统的原始研究素材，包括研究问题、方法、实验、参考文献和潜在视觉资产。
后续的 blueprint、contract 和 drafts 都以这里的对象为事实来源。
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ExperimentSpec(BaseModel):
    """一条实验信息，供 blueprint 和写作阶段引用。"""
    experiment_id: str
    name: str
    setup: str
    dataset: str
    metrics: list[str] = Field(default_factory=list)
    result_summary: str


class ReferenceSpec(BaseModel):
    """一条原始参考文献输入。"""
    reference_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    notes: str | None = None


class ArtifactSeed(BaseModel):
    """用户预先提供的图表/工件种子信息。"""
    artifact_id: str
    kind: str
    title: str
    description: str
    target_sections: list[str] = Field(default_factory=list)


class ResearchStory(BaseModel):
    """一次 Story2Proposal 运行的根输入对象。"""
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
        """从 JSON 文件加载一份 `ResearchStory`。"""
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
