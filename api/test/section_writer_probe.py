from __future__ import annotations

"""Standalone section_writer probe endpoint under api/test."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import DEFAULT_MODEL, load_prompt, load_mcp_server
from domain import build_initial_context, persist_run_state, refresh_prompt_views, save_section_draft
from llm_io import parse_model
from schemas import (
    ManuscriptContract,
    ResearchStory,
    SectionContract,
    SectionDraft,
    StyleGuide,
    VisualArtifact,
)
from src import Agent

router = APIRouter(prefix="/api/debug")


class SectionWriterProbeRequest(BaseModel):
    story: ResearchStory
    section: SectionContract
    visuals: list[VisualArtifact] = Field(default_factory=list)
    model: str = DEFAULT_MODEL
    mode: Literal["compose", "repair"] = "compose"
    plan: dict[str, Any] = Field(default_factory=dict)


class SectionWriterProbeResponse(BaseModel):
    outputDir: str
    draft: SectionDraft
    contract: ManuscriptContract
    rawOutput: str


def _build_probe_contract(payload: SectionWriterProbeRequest, output_dir: Path) -> ManuscriptContract:
    language = payload.story.metadata.get("writing_language")
    output_language = language if language in {"en", "zh"} else "en"
    contract = ManuscriptContract(
        contract_id=f"probe_{output_dir.name}",
        paper_title=payload.story.title_hint or payload.story.topic,
        style_guide=StyleGuide(output_language=output_language),
        sections=[payload.section],
        visuals=payload.visuals,
    )
    contract.global_status.state = "initialized"
    contract.global_status.current_section_id = payload.section.section_id
    contract.global_status.pending_sections = [payload.section.section_id]
    contract.global_status.completed_sections = []
    return contract


def _latest_assistant_message(messages: list[dict[str, object]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
    raise ValueError("Section writer did not return an assistant message.")


def _build_section_writer_agent(model: str) -> Agent:
    drawio_config = load_mcp_server("drawio")
    return Agent(
        name="section_writer",
        model=model,
        instructions=load_prompt("section_writer.md"),
        mcpServers=({"drawio": drawio_config} if drawio_config is not None else {}),
    )


async def _run_probe(payload: SectionWriterProbeRequest) -> SectionWriterProbeResponse:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("data") / "outputs" / f"{payload.story.story_id}_section_writer_probe_{timestamp}"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rendered").mkdir(exist_ok=True)
    (output_dir / "drafts").mkdir(exist_ok=True)
    (output_dir / "reviews").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)

    context = build_initial_context(payload.story, output_dir)
    contract = _build_probe_contract(payload, output_dir)
    context["contract"] = contract.model_dump(mode="json")
    context["runtime"]["current_section_id"] = payload.section.section_id
    context["runtime"]["pending_sections"] = [payload.section.section_id]
    context["runtime"]["completed_sections"] = []
    context["runtime"]["rewrite_count"] = {payload.section.section_id: 0}
    context["runtime"]["current_draft_version"] = 0
    context["runtime"]["section_writer_mode"] = payload.mode
    context["runtime"]["section_writer_plan"] = payload.plan
    refresh_prompt_views(context)
    persist_run_state(context)

    agent = _build_section_writer_agent(payload.model)
    try:
        result = await agent(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Write the current section and return JSON only.",
                    }
                ],
                "temperature": 0.2,
            },
            context=context,
        )
    finally:
        await agent._mcp_manager.close()

    raw_output = _latest_assistant_message(result["messages"])
    draft = parse_model(raw_output, SectionDraft)
    save_section_draft(context, draft)
    persist_run_state(context)
    return SectionWriterProbeResponse(
        outputDir=str(output_dir),
        draft=draft,
        contract=ManuscriptContract.model_validate(context["contract"]),
        rawOutput=raw_output,
    )


@router.post("/section-writer/probe", response_model=SectionWriterProbeResponse)
def section_writer_probe(payload: SectionWriterProbeRequest) -> SectionWriterProbeResponse:
    try:
        return asyncio.run(_run_probe(payload))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def create_app() -> FastAPI:
    app = FastAPI(title="Story2Proposal Test API")
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

    uvicorn.run("api.test.section_writer_probe:app", host="127.0.0.1", port=8010, reload=False)
