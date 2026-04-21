from __future__ import annotations

import re
from typing import Any

from schemas import RevisionRecord

from .contracts import apply_contract_patches


def _tokens_in_content(content: str, prefix: str) -> set[str]:
    pattern = re.compile(rf"\[{prefix}:([A-Za-z0-9_]+)\]")
    return {match.group(1) for match in pattern.finditer(content)}


def validate_section_coverage(section: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    covered = set(draft.get("covered_claim_ids", []))
    required = set(section.get("required_claims", []))
    missing = [claim for claim in required if claim not in covered]
    return [f"Missing required claim: {claim}" for claim in missing]


def validate_visual_references(section: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    content_ids = _tokens_in_content(draft.get("content", ""), "FIG")
    referenced_ids = set(draft.get("referenced_visual_ids", [])) | content_ids
    missing = set(section.get("required_visual_ids", [])) - referenced_ids
    return [f"Missing visual reference: {artifact_id}" for artifact_id in sorted(missing)]


def validate_citation_slots(section: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    content_ids = _tokens_in_content(draft.get("content", ""), "CIT")
    referenced_ids = set(draft.get("referenced_citation_ids", [])) | content_ids
    missing = set(section.get("required_citation_ids", [])) - referenced_ids
    return [f"Missing citation reference: {citation_id}" for citation_id in sorted(missing)]


def aggregate_current_feedback(context: dict[str, Any]) -> dict[str, Any]:
    runtime = context.get("runtime", {})
    section_id = runtime.get("current_section_id")
    section = None
    for item in (context.get("contract") or {}).get("sections", []):
        if item["section_id"] == section_id:
            section = item
            break
    draft = (context.get("drafts") or {}).get(section_id, {})
    reviews = list((context.get("reviews") or {}).get(section_id, []))
    status = "pass"
    issues: list[str] = []
    patches: list[dict[str, Any]] = []

    for review in reviews:
        status = (
            "fail"
            if review["status"] == "fail" or status == "fail"
            else "revise"
            if review["status"] == "revise" or status == "revise"
            else "pass"
        )
        issues.extend(item["description"] for item in review.get("issues", []))
        patches.extend(review.get("contract_patches", []))

    section = section or {}
    issues.extend(validate_section_coverage(section, draft))
    issues.extend(validate_visual_references(section, draft))
    issues.extend(validate_citation_slots(section, draft))
    if issues and status == "pass":
        status = "revise"
    return {"status": status, "issues": issues, "patches": patches}


def apply_review_cycle(context: dict[str, Any]) -> dict[str, Any]:
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

    contract = apply_contract_patches(contract, aggregate["patches"])
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
    context["contract"] = contract
    context["artifacts"]["last_aggregate_feedback"] = aggregate
    context["artifacts"]["next_action"] = next_action
    contract["revision_log"].append(
        RevisionRecord(
            stage="review_cycle",
            agent="review_controller",
            summary=f"{section_id}: {aggregate['status']} -> {next_action}",
            affected_sections=[section_id],
        ).model_dump(mode="json")
    )
    runtime["final_status"] = (
        "all_sections_completed"
        if runtime["current_section_id"] is None
        else runtime.get("final_status")
    )
    runtime["next_node"] = "refiner" if runtime["current_section_id"] is None else "section_writer"
    return context
