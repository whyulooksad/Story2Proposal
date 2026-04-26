from __future__ import annotations

"""Story2Proposal 主 API 的请求与响应模型。"""

from pydantic import BaseModel, Field

from backend.config import DEFAULT_MODEL
from backend.schemas import ResearchStory


class RunCreateRequest(BaseModel):
    """创建 run 时使用的请求体。"""

    story: ResearchStory
    model: str = DEFAULT_MODEL


class RunArtifactResponse(BaseModel):
    """返回给前端的单个 run 产物。"""

    id: str
    label: str
    kind: str
    content: str


class SectionStateResponse(BaseModel):
    """run 详情页使用的章节状态摘要。"""

    id: str
    title: str
    status: str
    rewriteCount: int = 0


class RunOverviewResponse(BaseModel):
    """run 的高层概览信息。"""

    finalStatus: str
    contractState: str
    completedSections: int
    pendingSections: int
    manualReviewCount: int
    workflowWarningCount: int
    evaluationOverallScore: float | None = None


class RunReviewStateResponse(BaseModel):
    """最新一轮 review 的结构化状态。"""

    status: str | None = None
    nextAction: str | None = None
    issueCount: int = 0
    patchCount: int = 0
    deterministicChecks: dict[str, list[str]] = Field(default_factory=dict)


class RunItemResponse(BaseModel):
    """run 列表使用的轻量摘要。"""

    id: str
    storyId: str
    model: str
    status: str
    startedAt: str
    updatedAt: str
    error: str | None = None


class RunDetailResponse(RunItemResponse):
    """单个 run 的完整详情响应。"""

    currentNode: str
    currentSectionId: str | None = None
    nextNode: str | None = None
    sections: list[SectionStateResponse] = Field(default_factory=list)
    artifacts: list[RunArtifactResponse] = Field(default_factory=list)
    overview: RunOverviewResponse
    latestReview: RunReviewStateResponse = Field(default_factory=RunReviewStateResponse)
