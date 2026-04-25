from __future__ import annotations

"""HTTP request and response models for the main Story2Proposal API."""

from pydantic import BaseModel, Field

from config import DEFAULT_MODEL
from schemas import ResearchStory


class RunCreateRequest(BaseModel):
    """Request body for creating a run."""

    story: ResearchStory
    model: str = DEFAULT_MODEL


class RunArtifactResponse(BaseModel):
    """One run artifact returned to the frontend."""

    id: str
    label: str
    kind: str
    content: str


class SectionStateResponse(BaseModel):
    """Section status summary used by the run detail page."""

    id: str
    title: str
    status: str
    rewriteCount: int = 0


class RunOverviewResponse(BaseModel):
    """High-level run overview."""

    finalStatus: str
    contractState: str
    completedSections: int
    pendingSections: int
    manualReviewCount: int
    workflowWarningCount: int
    evaluationOverallScore: float | None = None


class RunReviewStateResponse(BaseModel):
    """Structured state from the latest review cycle."""

    status: str | None = None
    nextAction: str | None = None
    issueCount: int = 0
    patchCount: int = 0
    deterministicChecks: dict[str, list[str]] = Field(default_factory=dict)


class RunItemResponse(BaseModel):
    """Lightweight run summary used in the run list."""

    id: str
    storyId: str
    model: str
    status: str
    startedAt: str
    updatedAt: str
    error: str | None = None


class RunDetailResponse(RunItemResponse):
    """Full run detail response."""

    currentNode: str
    currentSectionId: str | None = None
    nextNode: str | None = None
    sections: list[SectionStateResponse] = Field(default_factory=list)
    artifacts: list[RunArtifactResponse] = Field(default_factory=list)
    overview: RunOverviewResponse
    latestReview: RunReviewStateResponse = Field(default_factory=RunReviewStateResponse)
