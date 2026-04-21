from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from llm_io import json_dumps
from schemas import (
    EvaluationFeedback,
    ManuscriptBlueprint,
    ManuscriptContract,
    RefinerOutput,
    RenderedManuscript,
    ResearchStory,
    RevisionRecord,
    SectionDraft,
)


DEFAULT_SECTION_ORDER = [
    "title",
    "abstract",
    "introduction",
    "method",
    "experiments",
    "results_discussion",
    "related_work",
    "limitations",
    "conclusion",
]


def build_initial_context(
    story: ResearchStory,
    output_dir: Path,
    *,
    max_rewrite_per_section: int = 2,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "run_id": output_dir.name,
        "story": story.model_dump(mode="json"),
        "blueprint": None,
        "contract": None,
        "drafts": {},
        "reviews": {},
        "artifacts": {"output_dir": str(output_dir)},
        "runtime": {
            "current_section_id": None,
            "pending_sections": [],
            "completed_sections": [],
            "rewrite_count": {},
            "max_rewrite_per_section": max_rewrite_per_section,
            "final_status": None,
            "current_draft_version": 0,
            "needs_manual_review": [],
            "next_node": None,
        },
    }
    refresh_prompt_views(context)
    return context


def persist_run_state(context: dict[str, Any]) -> None:
    output_dir_raw = context.get("artifacts", {}).get("output_dir")
    if not output_dir_raw:
        return
    output_dir = Path(output_dir_raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "drafts").mkdir(exist_ok=True)
    (output_dir / "reviews").mkdir(exist_ok=True)
    (output_dir / "rendered").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)

    def write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if context.get("blueprint") is not None:
        write_json(output_dir / "blueprint.json", context["blueprint"])
    if context.get("contract") is not None:
        write_json(output_dir / "contract_final.json", context["contract"])
    if context.get("artifacts", {}).get("contract_init") is not None:
        write_json(output_dir / "contract_init.json", context["artifacts"]["contract_init"])
    for section_id, draft in context.get("drafts", {}).items():
        version = draft.get("version", 1)
        (output_dir / "drafts" / f"{section_id}_v{version}.md").write_text(
            draft.get("content", ""),
            encoding="utf-8",
        )
    for section_id, reviews in context.get("reviews", {}).items():
        write_json(output_dir / "reviews" / f"{section_id}.json", reviews)
    rendered = context.get("artifacts", {}).get("rendered")
    if rendered is not None:
        (output_dir / "rendered" / "final_manuscript.md").write_text(
            rendered.get("markdown", ""),
            encoding="utf-8",
        )
        (output_dir / "rendered" / "final_manuscript.tex").write_text(
            rendered.get("latex", ""),
            encoding="utf-8",
        )
    write_json(
        output_dir / "logs" / "run_state.json",
        {
            "runtime": context.get("runtime", {}),
            "artifacts": {
                "last_aggregate_feedback": context.get("artifacts", {}).get("last_aggregate_feedback"),
                "next_action": context.get("artifacts", {}).get("next_action"),
            },
        },
    )


def build_run_summary(context: dict[str, Any]) -> dict[str, Any]:
    runtime = context.get("runtime", {})
    rendered = context.get("artifacts", {}).get("rendered", {})
    output_dir = context.get("artifacts", {}).get("output_dir")
    return {
        "run_id": context.get("run_id"),
        "final_status": runtime.get("final_status"),
        "completed_sections": runtime.get("completed_sections", []),
        "rewrite_count": runtime.get("rewrite_count", {}),
        "needs_manual_review": runtime.get("needs_manual_review", []),
        "render_warnings": rendered.get("warnings", []),
        "output_dir": output_dir,
    }


def persist_run_outputs(context: dict[str, Any]) -> dict[str, Any]:
    output_dir_raw = context.get("artifacts", {}).get("output_dir")
    if not output_dir_raw:
        return build_run_summary(context)

    output_dir = Path(output_dir_raw)

    def write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    story = context.get("story")
    if story is not None:
        write_json(output_dir / "input_story.json", story)

    summary = build_run_summary(context)
    write_json(output_dir / "logs" / "run_summary.json", summary)
    return summary


def get_current_section_contract(context: dict[str, Any]) -> dict[str, Any] | None:
    contract = context.get("contract") or {}
    current_section_id = context.get("runtime", {}).get("current_section_id")
    for section in contract.get("sections", []):
        if section["section_id"] == current_section_id:
            return section
    return None


def get_current_draft(context: dict[str, Any]) -> dict[str, Any] | None:
    current_section_id = context.get("runtime", {}).get("current_section_id")
    return context.get("drafts", {}).get(current_section_id)


def get_current_reviews(context: dict[str, Any]) -> list[dict[str, Any]]:
    current_section_id = context.get("runtime", {}).get("current_section_id")
    if current_section_id is None:
        return []
    return list(context.get("reviews", {}).get(current_section_id, []))


def refresh_prompt_views(context: dict[str, Any]) -> dict[str, Any]:
    story = context.get("story")
    blueprint = context.get("blueprint")
    contract = context.get("contract")
    current_section = get_current_section_contract(context)
    current_draft = get_current_draft(context)
    current_reviews = get_current_reviews(context)
    context["story_json"] = json_dumps(story or {})
    context["blueprint_json"] = json_dumps(blueprint or {})
    context["contract_json"] = json_dumps(contract or {})
    context["current_section_contract_json"] = json_dumps(current_section or {})
    context["current_draft_json"] = json_dumps(current_draft or {})
    context["current_reviews_json"] = json_dumps(current_reviews)
    context["completed_section_summaries_json"] = json_dumps(
        {
            section_id: draft.get("content", "")[:500]
            for section_id, draft in context.get("drafts", {}).items()
            if section_id in set(context.get("runtime", {}).get("completed_sections", []))
        }
    )
    return context


def set_blueprint_and_contract(
    context: dict[str, Any],
    blueprint: ManuscriptBlueprint,
    contract: ManuscriptContract,
) -> dict[str, Any]:
    context["blueprint"] = blueprint.model_dump(mode="json")
    context["contract"] = contract.model_dump(mode="json")
    writing_order = list(blueprint.writing_order)
    context["runtime"]["pending_sections"] = writing_order
    context["runtime"]["completed_sections"] = []
    context["runtime"]["current_section_id"] = writing_order[0] if writing_order else None
    context["runtime"]["rewrite_count"] = {section_id: 0 for section_id in writing_order}
    context["artifacts"]["contract_init"] = deepcopy(context["contract"])
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def save_section_draft(context: dict[str, Any], draft: SectionDraft) -> dict[str, Any]:
    section_id = draft.section_id
    runtime = context["runtime"]
    runtime["current_draft_version"] = runtime.get("current_draft_version", 0) + 1
    version = runtime["current_draft_version"]
    draft_payload = draft.model_dump(mode="json") | {"version": version}
    context["drafts"][section_id] = draft_payload
    for section in context.get("contract", {}).get("sections", []):
        if section["section_id"] == section_id:
            section["latest_draft_version"] = version
            section["status"] = "drafted"
            section["draft_path"] = f"drafts/{section_id}_v{version}.md"
            break
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def append_review(context: dict[str, Any], feedback: EvaluationFeedback) -> dict[str, Any]:
    section_id = context["runtime"]["current_section_id"]
    draft_version = context["runtime"]["current_draft_version"]
    payload = feedback.model_dump(mode="json") | {"draft_version": draft_version}
    bucket = context["reviews"].setdefault(section_id, [])
    bucket = [item for item in bucket if item["evaluator_type"] != feedback.evaluator_type]
    bucket.append(payload)
    context["reviews"][section_id] = bucket
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def store_refiner_output(context: dict[str, Any], output: RefinerOutput) -> dict[str, Any]:
    context["artifacts"]["refiner_output"] = output.model_dump(mode="json")
    if output.abstract_override:
        context["artifacts"]["abstract_override"] = output.abstract_override
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def store_render_output(context: dict[str, Any], rendered: RenderedManuscript) -> dict[str, Any]:
    context["artifacts"]["rendered"] = rendered.model_dump(mode="json")
    context["runtime"]["final_status"] = "rendered"
    refresh_prompt_views(context)
    persist_run_state(context)
    return context
