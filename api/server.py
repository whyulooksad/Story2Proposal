from __future__ import annotations

"""Story2Proposal API 入口。

当前接口量很小，这一层直接在一个文件里定义路由就够了：
- `server.py`：应用入口 + 路由
- `repository.py`：文件读写和 run 管理
- `models.py`：run 相关请求/响应模型
"""

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from schemas import ResearchStory

from .models import RunCreateRequest, RunDetailResponse, RunItemResponse
from .repository import RunRepository, StoryRepository

router = APIRouter(prefix="/api")
stories = StoryRepository()
runs = RunRepository()


@router.get("/health")
def health() -> dict[str, str]:
    """最小健康检查接口。"""
    return {"status": "ok"}


@router.get("/stories", response_model=list[ResearchStory])
def list_stories() -> list[ResearchStory]:
    """返回 stories 目录中的全部 `ResearchStory`。"""
    return stories.list()


@router.post("/stories", response_model=ResearchStory)
def save_story(payload: ResearchStory) -> ResearchStory:
    """保存或覆盖一份 `ResearchStory`。"""
    return stories.save(payload)


@router.get("/runs", response_model=list[RunItemResponse])
def list_runs() -> list[RunItemResponse]:
    """返回当前可见的全部 run 摘要。"""
    return runs.list()


@router.post("/runs", response_model=RunDetailResponse)
def create_run(payload: RunCreateRequest) -> RunDetailResponse:
    """基于一份 `ResearchStory` 启动新的 run。"""
    return runs.create(payload.story, payload.model)


@router.post("/runs/{run_id}/stop", response_model=RunDetailResponse)
def stop_run(run_id: str) -> RunDetailResponse:
    """Request a cooperative stop for a running run."""
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
    """返回某个 run 的详情状态和聚合产物。"""
    try:
        return runs.get(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}") from exc


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

    uvicorn.run("api.server:app", host="127.0.0.1", port=8000, reload=False)
