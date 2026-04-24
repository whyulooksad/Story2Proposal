from __future__ import annotations

"""API 层请求/响应模型。

这里定义的是 HTTP 接口契约，不是领域层的完整业务实现。
其中 story 直接复用了领域模型 `ResearchStory`，run 相关的响应则在这里单独定义。
"""

from pydantic import BaseModel, Field

from config import DEFAULT_MODEL
from schemas import ResearchStory


class RunCreateRequest(BaseModel):
    """创建 run 的请求体。"""

    # 前端直接提交一份完整的 `ResearchStory`。
    story: ResearchStory
    # 当前版本整条图共享同一个 model 配置。
    model: str = DEFAULT_MODEL


class RunArtifactResponse(BaseModel):
    """返回给前端的单个 artifact 载荷。"""

    id: str
    label: str
    kind: str
    content: str


class SectionStateResponse(BaseModel):
    """run 详情页里每个 section 的状态摘要。"""

    id: str
    title: str
    status: str
    rewriteCount: int = 0


class RunOverviewResponse(BaseModel):
    """run 的核心运行概览。"""

    finalStatus: str
    contractState: str
    completedSections: int
    pendingSections: int
    manualReviewCount: int
    workflowWarningCount: int
    evaluationOverallScore: float | None = None


class RunReviewStateResponse(BaseModel):
    """最近一次 review cycle 的结构化状态。"""

    status: str | None = None
    nextAction: str | None = None
    issueCount: int = 0
    patchCount: int = 0
    deterministicChecks: dict[str, list[str]] = Field(default_factory=dict)


class RunItemResponse(BaseModel):
    """run 列表页使用的轻量摘要。"""

    id: str
    storyId: str
    model: str
    status: str
    startedAt: str
    updatedAt: str
    error: str | None = None


class RunDetailResponse(RunItemResponse):
    """run 详情页使用的完整响应。"""

    currentNode: str
    currentSectionId: str | None = None
    nextNode: str | None = None
    sections: list[SectionStateResponse] = Field(default_factory=list)
    artifacts: list[RunArtifactResponse] = Field(default_factory=list)
    overview: RunOverviewResponse
    latestReview: RunReviewStateResponse = Field(default_factory=RunReviewStateResponse)
