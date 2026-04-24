from __future__ import annotations

"""Story2Proposal 的共享状态辅助函数。

这个模块负责定义应用层共享 `context` 的基本形状，刷新给 prompt
直接使用的投影视图，并把中间产物与最终产物落盘。
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from llm_io import json_dumps
from .contracts import apply_contract_patches
from .rendering import build_bibliography_block
from .validation import finalize_contract_after_render
from schemas import (
    BenchmarkSuiteReport,
    ContractPatch,
    EvaluationFeedback,
    ManuscriptEvaluationReport,
    ManuscriptBlueprint,
    ManuscriptContract,
    RefinerOutput,
    RenderedManuscript,
    ResearchStory,
    SectionDraft,
)
from .evaluation import evaluate_manuscript_bundle


def get_writing_language(context: dict[str, Any]) -> str:
    """返回当前 run 期望的论文输出语言。

    目前支持：
    - `en`: English
    - `zh`: 中文

    其余值统一回退到 `en`，避免 prompt 和渲染层拿到未知语言标签。
    """
    story = context.get("story") or {}
    metadata = story.get("metadata") or {}
    language = metadata.get("writing_language")
    return language if language in {"en", "zh"} else "en"


def build_initial_context(
    story: ResearchStory,
    output_dir: Path,
    *,
    max_rewrite_per_section: int = 3,
) -> dict[str, Any]:
    """为一次 Story2Proposal 运行创建初始共享 `context`。"""
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
    """把当前运行快照和中间产物持久化到输出目录。"""
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
    evaluation = context.get("artifacts", {}).get("evaluation")
    if evaluation is not None:
        write_json(output_dir / "logs" / "evaluation.json", evaluation)
    benchmark = context.get("artifacts", {}).get("benchmark")
    if benchmark is not None:
        write_json(output_dir / "logs" / "benchmark.json", benchmark)
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
    """构造一个适合 runner 最终返回的精简摘要。"""
    runtime = context.get("runtime", {})
    rendered = context.get("artifacts", {}).get("rendered", {})
    output_dir = context.get("artifacts", {}).get("output_dir")
    evaluation = context.get("artifacts", {}).get("evaluation", {})
    return {
        "run_id": context.get("run_id"),
        "final_status": runtime.get("final_status"),
        "completed_sections": runtime.get("completed_sections", []),
        "rewrite_count": runtime.get("rewrite_count", {}),
        "needs_manual_review": runtime.get("needs_manual_review", []),
        "render_warnings": rendered.get("warnings", []),
        "evaluation_overall_score": evaluation.get("overall_score"),
        "evaluation_risks": evaluation.get("risks", []),
        "output_dir": output_dir,
    }


def persist_run_outputs(context: dict[str, Any]) -> dict[str, Any]:
    """持久化最终运行元数据，并返回对应的摘要结果。"""
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
    """返回当前正在处理章节对应的 contract 条目。"""
    contract = context.get("contract") or {}
    current_section_id = context.get("runtime", {}).get("current_section_id")
    for section in contract.get("sections", []):
        if section["section_id"] == current_section_id:
            return section
    return None


def get_current_draft(context: dict[str, Any]) -> dict[str, Any] | None:
    """返回当前章节最新保存的 draft。"""
    current_section_id = context.get("runtime", {}).get("current_section_id")
    return context.get("drafts", {}).get(current_section_id)


def get_current_reviews(context: dict[str, Any]) -> list[dict[str, Any]]:
    """返回当前章节已经收集到的全部 evaluator 反馈。"""
    current_section_id = context.get("runtime", {}).get("current_section_id")
    if current_section_id is None:
        return []
    return list(context.get("reviews", {}).get(current_section_id, []))


def _build_section_obligation_summary(section: dict[str, Any] | None) -> dict[str, Any]:
    """为 writer/evaluator 构造更紧凑的 section obligation 摘要。"""
    if not section:
        return {}
    return {
        "section_id": section.get("section_id"),
        "purpose": section.get("purpose"),
        "required_claim_ids": section.get("required_claim_ids", []),
        "required_evidence_ids": section.get("required_evidence_ids", []),
        "required_visual_ids": section.get("required_visual_ids", []),
        "required_citation_ids": section.get("required_citation_ids", []),
        "source_story_fields": section.get("source_story_fields", []),
        "claim_requirements": [
            {
                "claim_id": item.get("claim_id"),
                "evidence_ids": item.get("evidence_ids", []),
                "citation_ids": item.get("citation_ids", []),
                "source_story_fields": item.get("source_story_fields", []),
            }
            for item in section.get("claim_requirements", [])
        ],
        "visual_obligations": section.get("visual_obligations", []),
        "citation_obligations": section.get("citation_obligations", []),
    }


def refresh_prompt_views(context: dict[str, Any]) -> dict[str, Any]:
    """刷新从共享状态投影出来的 prompt 视图。"""
    story = context.get("story")
    blueprint = context.get("blueprint")
    contract = context.get("contract")
    current_section = get_current_section_contract(context)
    current_draft = get_current_draft(context)
    current_reviews = get_current_reviews(context)
    writing_language = get_writing_language(context)
    # Prompt 模板直接消费这些预渲染好的 JSON 字符串，避免在多个地方
    # 重复做状态格式化。
    context["story_json"] = json_dumps(story or {})
    context["blueprint_json"] = json_dumps(blueprint or {})
    context["contract_json"] = json_dumps(contract or {})
    context["current_section_contract_json"] = json_dumps(current_section or {})
    context["current_section_obligation_summary_json"] = json_dumps(
        _build_section_obligation_summary(current_section)
    )
    context["current_draft_json"] = json_dumps(current_draft or {})
    context["current_reviews_json"] = json_dumps(current_reviews)
    context["writing_language"] = writing_language
    context["writing_language_instruction"] = (
        "Write all paper-facing content in Chinese."
        if writing_language == "zh"
        else "Write all paper-facing content in English."
    )
    context["completed_section_summaries_json"] = json_dumps(
        {
            section_id: draft.get("content", "")[:500]
            for section_id, draft in context.get("drafts", {}).items()
            if section_id in set(context.get("runtime", {}).get("completed_sections", []))
        }
    )
    context["completed_section_drafts_json"] = json_dumps(
        {
            section_id: draft
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
    """写入初始 blueprint/contract，并初始化写作阶段的运行状态。"""
    context["blueprint"] = blueprint.model_dump(mode="json")
    context["contract"] = contract.model_dump(mode="json")
    writing_order = list(blueprint.writing_order)
    context["runtime"]["pending_sections"] = writing_order
    context["runtime"]["completed_sections"] = []
    context["runtime"]["current_section_id"] = writing_order[0] if writing_order else None
    context["runtime"]["rewrite_count"] = {section_id: 0 for section_id in writing_order}
    context["contract"]["global_status"]["current_section_id"] = context["runtime"]["current_section_id"]
    context["contract"]["global_status"]["pending_sections"] = writing_order
    context["contract"]["global_status"]["completed_sections"] = []
    context["artifacts"]["contract_init"] = deepcopy(context["contract"])
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def save_section_draft(context: dict[str, Any], draft: SectionDraft) -> dict[str, Any]:
    """保存一个章节 draft，并同步更新对应的 contract section。"""
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
            for requirement in section.get("claim_requirements", []):
                if requirement["claim_id"] in draft.covered_claim_ids:
                    requirement["coverage_status"] = "covered"
            break
    for artifact in context.get("contract", {}).get("visuals", []):
        if artifact["artifact_id"] in draft.referenced_visual_ids:
            if section_id not in artifact["resolved_references"]:
                artifact["resolved_references"].append(section_id)
            artifact["render_status"] = "registered"
    for citation in context.get("contract", {}).get("citations", []):
        if citation["citation_id"] in draft.referenced_citation_ids:
            citation["status"] = "used"
            for trace in draft.evidence_traces:
                if citation["citation_id"] not in trace.citation_ids:
                    continue
                for claim_id in trace.supports_claim_ids:
                    if claim_id not in citation["grounded_claim_ids"]:
                        citation["grounded_claim_ids"].append(claim_id)
    context["contract"]["global_status"]["state"] = "drafted"
    context["contract"]["global_status"]["current_section_id"] = section_id
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def append_review(context: dict[str, Any], feedback: EvaluationFeedback) -> dict[str, Any]:
    """保存当前章节某个 evaluator 的最新反馈。"""
    section_id = context["runtime"]["current_section_id"]
    draft_version = context["runtime"]["current_draft_version"]
    payload = feedback.model_dump(mode="json") | {"draft_version": draft_version}
    bucket = context["reviews"].setdefault(section_id, [])
    # 对同一章节、同一 evaluator，只保留当前 draft 的最新意见。
    bucket = [item for item in bucket if item["evaluator_type"] != feedback.evaluator_type]
    bucket.append(payload)
    context["reviews"][section_id] = bucket
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def store_refiner_output(context: dict[str, Any], output: RefinerOutput) -> dict[str, Any]:
    """把 refiner 输出产物写回共享状态。"""
    context["artifacts"]["refiner_output"] = output.model_dump(mode="json")
    if output.abstract_override:
        context["artifacts"]["abstract_override"] = output.abstract_override
    for item in context.get("contract", {}).get("glossary", []):
        preferred = output.terminology_updates.get(item["term"])
        if preferred:
            item["preferred_form"] = preferred
    if output.contract_patches:
        context["contract"] = apply_contract_patches(
            context["contract"],
            [ContractPatch.model_validate(item).model_dump(mode="json") for item in output.contract_patches],
        )
    if output.section_rewrites or output.rewrite_goals:
        context["contract"]["revision_log"].append(
            {
                "revision_id": f"refiner_{len(context['contract']['revision_log']) + 1}",
                "stage": "global_refinement",
                "agent": "refiner",
                "summary": "; ".join(output.rewrite_goals) or "Applied global rewrite before final rendering.",
                "affected_sections": sorted(
                    rewrite.section_id
                    for rewrite in output.section_rewrites
                ),
                "affected_artifacts": [],
                "patch_types": ["section_rewrite"],
                "contract_version": context["contract"].get("version", 1),
            }
        )
    context["contract"]["global_status"]["state"] = "refined"
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def store_render_output(context: dict[str, Any], rendered: RenderedManuscript) -> dict[str, Any]:
    """保存最终渲染产物，并把运行状态标记为完成。"""
    context["artifacts"]["rendered"] = rendered.model_dump(mode="json")
    context["runtime"]["final_status"] = "rendered"
    validation = rendered.validation.model_dump(mode="json")
    context["contract"] = finalize_contract_after_render(
        context["contract"],
        [section.model_dump(mode="json") for section in rendered.finalized_sections],
        build_bibliography_block(context),
        rendered.validation,
    )
    context["contract"]["global_status"]["state"] = "rendered"
    context["contract"]["global_status"]["warnings"] = list(validation.get("warnings", []))
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def store_evaluation_output(context: dict[str, Any], evaluation: ManuscriptEvaluationReport) -> dict[str, Any]:
    """保存整篇稿件的结构化评测结果。"""
    context["artifacts"]["evaluation"] = evaluation.model_dump(mode="json")
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def store_benchmark_output(context: dict[str, Any], benchmark: BenchmarkSuiteReport) -> dict[str, Any]:
    """保存整篇稿件的 benchmark suite 结果。"""
    context["artifacts"]["benchmark"] = benchmark.model_dump(mode="json")
    refresh_prompt_views(context)
    persist_run_state(context)
    return context


def evaluate_and_store_manuscript(context: dict[str, Any]) -> dict[str, Any]:
    """在最终稿生成后执行整篇稿件评测。"""
    evaluation, benchmark = evaluate_manuscript_bundle(context)
    store_evaluation_output(context, evaluation)
    return store_benchmark_output(context, benchmark)
