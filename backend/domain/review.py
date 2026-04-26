from __future__ import annotations

"""Story2Proposal 的章节评审循环辅助函数。

这个模块负责聚合章节评审结果，并据此推进或回退章节循环。
"""

from pathlib import Path
from typing import Any

from backend.schemas import AggregatedFeedback, ContractPatch, RevisionRecord

from .contracts import apply_contract_patches
from .validation import aggregate_feedback


def aggregate_current_feedback(context: dict[str, Any]) -> dict[str, Any]:
    """聚合当前章节的 evaluator 输出和确定性检查结果。"""
    runtime = context.get("runtime", {})
    section_id = runtime.get("current_section_id")
    section = next(
        (item for item in (context.get("contract") or {}).get("sections", []) if item["section_id"] == section_id),
        {},
    )
    draft = (context.get("drafts") or {}).get(section_id, {})
    reviews = list((context.get("reviews") or {}).get(section_id, []))

    output_dir = Path((context.get("artifacts") or {}).get("output_dir", ".")).resolve()
    return aggregate_feedback(section, draft, reviews, output_dir=output_dir)


def _rule_patch(rule_id: str, *, severity: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造一条 tighten_validation_rule patch。"""
    return ContractPatch(
        patch_type="tighten_validation_rule",
        target_id=rule_id,
        value={"severity": severity, "params": params or {}},
    ).model_dump(mode="json")


def _derive_contract_evolution_patches(
    aggregate: dict[str, Any],
    section_id: str,
    rewrite_count: int,
) -> list[dict[str, Any]]:
    """把重复出现的确定性问题提升为更强的 contract 约束。"""
    checks = aggregate.get("deterministic_checks", {})
    patches: list[dict[str, Any]] = []

    if checks.get("citation_hygiene"):
        patches.append(
            _rule_patch(
                "citation_grounding",
                severity="high",
                params={"last_trigger_section": section_id, "rewrite_count": rewrite_count},
            )
        )
    if checks.get("visual_references") or checks.get("visual_artifact_integrity"):
        patches.append(
            _rule_patch(
                "visual_reference_resolution",
                severity="high",
                params={"last_trigger_section": section_id},
            )
        )
    if checks.get("traceability"):
        patches.append(
            _rule_patch(
                "revision_traceability",
                severity="high" if rewrite_count >= 1 else "medium",
                params={"last_trigger_section": section_id},
            )
        )
    if checks.get("data_fidelity"):
        patches.append(
            _rule_patch(
                "claim_evidence_alignment",
                severity="high",
                params={"last_trigger_section": section_id},
            )
        )
    if rewrite_count >= 1 and any(checks.values()):
        patches.append(
            ContractPatch(
                patch_type="register_revision_note",
                target_id=section_id,
                value=f"Deterministic checks kept firing in {section_id}; contract rules were tightened.",
            ).model_dump(mode="json")
        )
    return patches


def _should_use_visual_repair(
    context: dict[str, Any],
    aggregate: dict[str, Any],
    section_id: str,
) -> bool:
    """判断当前 revise 是否属于可由局部 visual repair 解决的问题。"""
    deterministic_checks = aggregate.get("deterministic_checks", {})
    visual_only_checks = bool(
        deterministic_checks.get("visual_references") or deterministic_checks.get("visual_artifact_integrity")
    ) and not any(
        deterministic_checks.get(name)
        for name in ("section_coverage", "citation_hygiene", "data_fidelity", "traceability")
    )
    if not visual_only_checks:
        return False

    reviews = list((context.get("reviews") or {}).get(section_id, []))
    if not reviews:
        return False

    visual_status = None
    for review in reviews:
        evaluator_type = review.get("evaluator_type")
        status = review.get("status")
        if evaluator_type == "visual":
            visual_status = status
            continue
        if status in {"revise", "fail"}:
            return False

    return visual_status in {"revise", "fail"}


def _build_section_writer_plan(context: dict[str, Any], aggregate: dict[str, Any], section_id: str) -> dict[str, Any]:
    """为 section_writer 构造下一步的执行计划。"""
    mode = "compose"
    issues = aggregate.get("issues", [])
    actions: list[dict[str, Any]] = []
    target_visual_ids: list[str] = []

    if _should_use_visual_repair(context, aggregate, section_id):
        mode = "repair"
        reviews = list((context.get("reviews") or {}).get(section_id, []))
        for review in reviews:
            if review.get("evaluator_type") != "visual":
                continue
            actions = list(review.get("suggested_actions", []))
            target_visual_ids = [
                item.get("target_id")
                for item in review.get("issues", [])
                if item.get("target_id")
            ]
            break

    return {
        "mode": mode,
        "section_id": section_id,
        "issues": issues,
        "suggested_actions": actions,
        "target_visual_ids": list(dict.fromkeys(target_visual_ids)),
    }


def apply_review_cycle(context: dict[str, Any]) -> dict[str, Any]:
    """根据聚合反馈决定当前章节是推进还是重写。"""
    aggregate = aggregate_current_feedback(context)
    runtime = context["runtime"]
    contract = context["contract"]
    section_id = runtime["current_section_id"]
    rewrite_count = runtime["rewrite_count"].get(section_id, 0)
    next_action = "advance"
    section_final_status = "approved"
    section_writer_plan = _build_section_writer_plan(context, aggregate, section_id)

    if aggregate["status"] in {"revise", "fail"}:
        if rewrite_count < runtime["max_rewrite_per_section"]:
            runtime["rewrite_count"][section_id] = rewrite_count + 1
            next_action = "repair_visual" if section_writer_plan["mode"] == "repair" else "rewrite_section"
            for section in contract["sections"]:
                if section["section_id"] == section_id:
                    section["status"] = "needs_revision"
                    break
        else:
            if section_id not in runtime["needs_manual_review"]:
                runtime["needs_manual_review"].append(section_id)
            next_action = "advance"
            section_final_status = "manual_review"

    evolution_patches = _derive_contract_evolution_patches(
        aggregate,
        section_id=section_id,
        rewrite_count=rewrite_count,
    )
    contract = apply_contract_patches(
        contract,
        [
            ContractPatch.model_validate(item).model_dump(mode="json")
            for item in [*aggregate["patches"], *evolution_patches]
        ],
    )

    if next_action == "advance":
        if section_id in runtime["pending_sections"]:
            runtime["pending_sections"].remove(section_id)
        if section_id not in runtime["completed_sections"]:
            runtime["completed_sections"].append(section_id)
        remaining = list(runtime["pending_sections"])
        runtime["current_section_id"] = remaining[0] if remaining else None
        runtime["current_draft_version"] = 0
        runtime["section_writer_mode"] = "compose"
        runtime["section_writer_plan"] = {}
        for section in contract["sections"]:
            if section["section_id"] == section_id:
                section["status"] = section_final_status
                break
    else:
        runtime["section_writer_mode"] = section_writer_plan["mode"]
        runtime["section_writer_plan"] = section_writer_plan

    contract["global_status"]["state"] = "all_sections_completed" if runtime["current_section_id"] is None else "section_reviewed"
    contract["global_status"]["current_section_id"] = runtime["current_section_id"]
    contract["global_status"]["completed_sections"] = list(runtime["completed_sections"])
    contract["global_status"]["pending_sections"] = list(runtime["pending_sections"])

    context["contract"] = contract
    context["artifacts"]["last_aggregate_feedback"] = aggregate
    context["artifacts"]["next_action"] = next_action
    contract["revision_log"].append(
        RevisionRecord(
            revision_id=f"review_{section_id}_{len(contract['revision_log']) + 1}",
            stage="review_cycle",
            agent="review_controller",
            summary=f"{section_id}: {aggregate['status']} -> {next_action}",
            affected_sections=[section_id],
            patch_types=[patch["patch_type"] for patch in [*aggregate["patches"], *evolution_patches]],
            contract_version=contract.get("version", 1),
        ).model_dump(mode="json")
    )

    runtime["final_status"] = "all_sections_completed" if runtime["current_section_id"] is None else runtime.get("final_status")
    if runtime["current_section_id"] is None:
        runtime["next_node"] = "refiner"
    else:
        runtime["next_node"] = "section_writer"
    return context
