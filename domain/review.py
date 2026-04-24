from __future__ import annotations

"""Story2Proposal 的章节评审循环辅助函数。"""

from typing import Any

from schemas import AggregatedFeedback, ContractPatch, RevisionRecord

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

    return aggregate_feedback(section, draft, reviews)


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
    if checks.get("visual_references"):
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


def apply_review_cycle(context: dict[str, Any]) -> dict[str, Any]:
    """根据聚合反馈决定当前章节是推进还是重写。"""
    aggregate = aggregate_current_feedback(context)
    runtime = context["runtime"]
    contract = context["contract"]
    section_id = runtime["current_section_id"]
    rewrite_count = runtime["rewrite_count"].get(section_id, 0)
    next_action = "advance"

    if aggregate["status"] in {"revise", "fail"}:
        if rewrite_count < runtime["max_rewrite_per_section"]:
            runtime["rewrite_count"][section_id] = rewrite_count + 1
            next_action = "rewrite"
            for section in contract["sections"]:
                if section["section_id"] == section_id:
                    section["status"] = "needs_revision"
                    break
        else:
            runtime["needs_manual_review"].append(section_id)
            next_action = "advance"

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
        for section in contract["sections"]:
            if section["section_id"] == section_id:
                section["status"] = "approved"
                break

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
    runtime["next_node"] = "refiner" if runtime["current_section_id"] is None else "section_writer"
    return context
