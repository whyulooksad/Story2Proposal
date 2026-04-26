from __future__ import annotations

"""Story2Proposal 的 FastAPI 服务入口。

这个文件负责暴露 story 和 run 相关的 HTTP 接口。
"""

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.schemas import ResearchStory

from .models import RunCreateRequest, RunDetailResponse, RunItemResponse
from .repository import RunRepository, StoryRepository

router = APIRouter(prefix="/api")
stories = StoryRepository()
runs = RunRepository()


@router.get("/health")
def health() -> dict[str, str]:
    """返回一个最小健康检查结果。"""
    return {"status": "ok"}


@router.get("/stories", response_model=list[ResearchStory])
def list_stories() -> list[ResearchStory]:
    """返回全部已持久化的 stories。"""
    return stories.list()


@router.post("/stories", response_model=ResearchStory)
def save_story(payload: ResearchStory) -> ResearchStory:
    """保存一份 story。"""
    return stories.save(payload)


@router.delete("/stories/{story_id}", status_code=204)
def delete_story(story_id: str) -> None:
    """按 story_id 删除一份已持久化的 story。"""
    try:
        stories.delete(story_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Story not found: {story_id}") from exc


@router.get("/runs", response_model=list[RunItemResponse])
def list_runs() -> list[RunItemResponse]:
    """返回全部可见 runs。"""
    return runs.list()


@router.post("/runs", response_model=RunDetailResponse)
def create_run(payload: RunCreateRequest) -> RunDetailResponse:
    """基于一份 story 创建新的 run。"""
    return runs.create(payload.story, payload.model)


@router.post("/runs/{run_id}/stop", response_model=RunDetailResponse)
def stop_run(run_id: str) -> RunDetailResponse:
    """停止一个正在运行的 run。"""
    try:
        return runs.stop(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str) -> None:
    """删除一个未运行中的 run 及其持久化产物。"""
    try:
        runs.delete(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: str) -> RunDetailResponse:
    """返回单个 run 的详情。"""
    try:
        return runs.get(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}") from exc


@router.get("/runs/{run_id}/file")
def get_run_file(
    run_id: str,
    path: str = Query(..., description="Relative or absolute file path within the run output directory."),
) -> FileResponse:
    """返回单个 run 产物文件。"""
    try:
        resolved = runs.resolve_file(run_id, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run file not found: {path}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(resolved)


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
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

    uvicorn.run("backend.api.server:app", host="127.0.0.1", port=8000, reload=False)
