from __future__ import annotations

"""Story2Proposal FastAPI entrypoint."""

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from schemas import ResearchStory

from .models import RunCreateRequest, RunDetailResponse, RunItemResponse
from .repository import RunRepository, StoryRepository

router = APIRouter(prefix="/api")
stories = StoryRepository()
runs = RunRepository()


@router.get("/health")
def health() -> dict[str, str]:
    """Small health-check endpoint."""
    return {"status": "ok"}


@router.get("/stories", response_model=list[ResearchStory])
def list_stories() -> list[ResearchStory]:
    """Return all persisted stories."""
    return stories.list()


@router.post("/stories", response_model=ResearchStory)
def save_story(payload: ResearchStory) -> ResearchStory:
    """Persist a story."""
    return stories.save(payload)


@router.delete("/stories/{story_id}", status_code=204)
def delete_story(story_id: str) -> None:
    """Delete a persisted story by story id."""
    try:
        stories.delete(story_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Story not found: {story_id}") from exc


@router.get("/runs", response_model=list[RunItemResponse])
def list_runs() -> list[RunItemResponse]:
    """Return all visible runs."""
    return runs.list()


@router.post("/runs", response_model=RunDetailResponse)
def create_run(payload: RunCreateRequest) -> RunDetailResponse:
    """Create a new run from one story."""
    return runs.create(payload.story, payload.model)


@router.post("/runs/{run_id}/stop", response_model=RunDetailResponse)
def stop_run(run_id: str) -> RunDetailResponse:
    """Stop a running run."""
    try:
        return runs.stop(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str) -> None:
    """Delete a non-running run and its persisted artifacts."""
    try:
        runs.delete(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: str) -> RunDetailResponse:
    """Return one run detail payload."""
    try:
        return runs.get(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}") from exc


@router.get("/runs/{run_id}/file")
def get_run_file(
    run_id: str,
    path: str = Query(..., description="Relative or absolute file path within the run output directory."),
) -> FileResponse:
    """Serve one generated run artifact file."""
    try:
        resolved = runs.resolve_file(run_id, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run file not found: {path}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(resolved)


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    app = FastAPI(title="Story2Proposal API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.server:app", host="127.0.0.1", port=8000, reload=False)
