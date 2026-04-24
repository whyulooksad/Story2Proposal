from __future__ import annotations

"""Story2Proposal 的确定性校验逻辑。"""

import re
from collections import Counter
from copy import deepcopy
from typing import Any

from schemas import AggregatedFeedback, ContractPatch, RenderValidationReport


def tokens_in_text(text: str, prefix: str) -> list[str]:
    """提取正文中的 `[FIG:id]` / `[CIT:id]` token。"""
    pattern = re.compile(rf"\[{prefix}:([A-Za-z0-9_]+)\]")
    return [match.group(1) for match in pattern.finditer(text or "")]


def validate_section_coverage(section: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    """检查 draft 是否覆盖了当前 section 的必需 claim。"""
    covered = set(draft.get("covered_claim_ids", []))
    required = set(section.get("required_claim_ids", []) or section.get("required_claims", []))
    missing = [claim_id for claim_id in required if claim_id not in covered]
    return [f"Missing required claim coverage: {claim_id}" for claim_id in missing]


def validate_visual_references(section: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    """检查必需的 visual 是否都被显式引用。"""
    content_ids = set(tokens_in_text(draft.get("content", ""), "FIG"))
    referenced_ids = set(draft.get("referenced_visual_ids", [])) | content_ids
    missing = set(section.get("required_visual_ids", [])) - referenced_ids
    return [f"Missing visual reference: {artifact_id}" for artifact_id in sorted(missing)]


def validate_citation_slots(section: dict[str, Any], draft: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """检查 citation 覆盖与 claim grounding。"""
    issues: list[str] = []
    patches: list[dict[str, Any]] = []
    content_ids = set(tokens_in_text(draft.get("content", ""), "CIT"))
    referenced_ids = set(draft.get("referenced_citation_ids", [])) | content_ids
    evidence_trace_citations = {
        citation_id
        for trace in draft.get("evidence_traces", [])
        for citation_id in trace.get("citation_ids", [])
        if citation_id
    }
    missing = set(section.get("required_citation_ids", [])) - referenced_ids
    issues.extend(f"Missing citation reference: {citation_id}" for citation_id in sorted(missing))

    covered_claims = set(draft.get("covered_claim_ids", []))
    for obligation in section.get("citation_obligations", []):
        citation_id = obligation.get("citation_id")
        grounded_claim_ids = set(obligation.get("grounded_claim_ids", []))
        if not citation_id or citation_id not in referenced_ids:
            continue
        if citation_id not in evidence_trace_citations:
            issues.append(f"Citation {citation_id} is referenced without evidence-trace grounding.")
        missing_groundings = grounded_claim_ids & covered_claims
        if not missing_groundings:
            continue
        for claim_id in sorted(missing_groundings):
            patches.append(
                ContractPatch(
                    patch_type="ground_citation_to_claim",
                    target_id=citation_id,
                    value={"claim_id": claim_id},
                ).model_dump(mode="json")
            )
    untraced_citations = referenced_ids - evidence_trace_citations
    issues.extend(
        f"Citation {citation_id} is not attached to any evidence trace."
        for citation_id in sorted(untraced_citations)
    )
    return issues, patches


def validate_data_fidelity(section: dict[str, Any], draft: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """检查 claim、evidence、story trace 之间是否存在断裂。"""
    issues: list[str] = []
    patches: list[dict[str, Any]] = []
    covered_claims = set(draft.get("covered_claim_ids", []))
    evidence_trace_ids = {
        trace["evidence_id"]
        for trace in draft.get("evidence_traces", [])
        if trace.get("evidence_id")
    }
    story_trace_fields = {
        trace["story_field"]
        for trace in draft.get("story_traces", [])
        if trace.get("story_field")
    }

    for requirement in section.get("claim_requirements", []):
        claim_id = requirement["claim_id"]
        if claim_id not in covered_claims:
            continue

        expected_evidence = set(requirement.get("evidence_ids", []))
        if expected_evidence and not (expected_evidence & evidence_trace_ids):
            issues.append(f"Claim {claim_id} is covered without matching evidence trace.")
            for evidence_id in sorted(expected_evidence):
                patches.append(
                    ContractPatch(
                        patch_type="add_required_evidence",
                        target_id=section["section_id"],
                        value=evidence_id,
                    ).model_dump(mode="json")
                )

        expected_story_fields = set(requirement.get("source_story_fields", []))
        if expected_story_fields and not (expected_story_fields & story_trace_fields):
            issues.append(f"Claim {claim_id} is covered without matching story trace.")

    if not story_trace_fields:
        issues.append(f"Section {section.get('section_id')} has no explicit story trace.")

    if covered_claims and not evidence_trace_ids and section.get("required_evidence_ids"):
        issues.append(f"Section {section.get('section_id')} covers claims without any evidence trace.")

    return issues, patches


def validate_traceability(section: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    """检查 section 级 traceability 是否足够。"""
    issues: list[str] = []
    declared_fields = set(section.get("source_story_fields", []))
    traced_fields = {
        trace["story_field"]
        for trace in draft.get("story_traces", [])
        if trace.get("story_field")
    }
    if declared_fields and not (declared_fields & traced_fields):
        issues.append(f"Section {section.get('section_id')} does not trace back to its declared story fields.")

    covered_claims = set(draft.get("covered_claim_ids", []))
    trace_supported_claims = {
        claim_id
        for trace in draft.get("evidence_traces", [])
        for claim_id in trace.get("supports_claim_ids", [])
    }
    uncovered = covered_claims - trace_supported_claims
    issues.extend(
        f"Covered claim lacks evidence trace support: {claim_id}"
        for claim_id in sorted(uncovered)
    )
    return issues


def aggregate_feedback(
    section: dict[str, Any],
    draft: dict[str, Any],
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    """聚合 evaluator 输出与确定性检查。"""
    status = "pass"
    issues: list[str] = []
    patches: list[dict[str, Any]] = []
    contributing_evaluators: list[str] = []

    for review in reviews:
        contributing_evaluators.append(review["evaluator_type"])
        if review["status"] == "fail":
            status = "fail"
        elif review["status"] == "revise" and status != "fail":
            status = "revise"
        issues.extend(item["description"] for item in review.get("issues", []))
        patches.extend(review.get("contract_patches", []))

    coverage_issues = validate_section_coverage(section, draft)
    visual_issues = validate_visual_references(section, draft)
    citation_issues, citation_patches = validate_citation_slots(section, draft)
    fidelity_issues, fidelity_patches = validate_data_fidelity(section, draft)
    traceability_issues = validate_traceability(section, draft)

    issues.extend(coverage_issues)
    issues.extend(visual_issues)
    issues.extend(citation_issues)
    issues.extend(fidelity_issues)
    issues.extend(traceability_issues)
    patches.extend(citation_patches)
    patches.extend(fidelity_patches)

    if issues and status == "pass":
        status = "revise"

    return AggregatedFeedback(
        status=status,
        issues=issues,
        patches=[ContractPatch.model_validate(item) for item in patches],
        contributing_evaluators=contributing_evaluators,
        deterministic_checks={
            "section_coverage": coverage_issues,
            "visual_references": visual_issues,
            "citation_hygiene": citation_issues,
            "data_fidelity": fidelity_issues,
            "traceability": traceability_issues,
        },
    ).model_dump(mode="json")


def has_visual_explanation(content: str, artifact: dict[str, Any]) -> bool:
    """检查 visual 引用周边是否有解释。"""
    lowered = (content or "").lower()
    keywords: list[str] = []
    keywords.extend(str(artifact.get("label", "")).lower().split())
    keywords.extend(str(artifact.get("semantic_role", "")).lower().split())
    keywords.extend(str(artifact.get("caption_brief", "")).lower().split())
    keywords = [keyword for keyword in keywords if len(keyword) > 3]
    if any(keyword in lowered for keyword in keywords):
        return True
    stripped = re.sub(r"\[FIG:[A-Za-z0-9_]+\]", "", content or "").strip()
    return len(stripped) >= 80


def validate_render_output(
    contract: dict[str, Any],
    rendered_sections: list[dict[str, str]],
    bibliography: str,
) -> RenderValidationReport:
    """执行最终稿的确定性结构校验。"""
    report = RenderValidationReport()
    combined_text = "\n\n".join(section["content"] for section in rendered_sections)
    fig_refs = tokens_in_text(combined_text, "FIG")
    cit_refs = tokens_in_text(combined_text, "CIT")
    fig_counter = Counter(fig_refs)
    label_counter = Counter(
        artifact.get("canonical_label") or artifact.get("label")
        for artifact in contract.get("visuals", [])
    )
    citation_key_counter = Counter(
        citation.get("citation_key")
        for citation in contract.get("citations", [])
    )
    allowed_visual_ids = {artifact["artifact_id"] for artifact in contract.get("visuals", [])}
    allowed_citation_ids = {citation["citation_id"] for citation in contract.get("citations", [])}
    glossary_terms = {item.get("preferred_form", "") for item in contract.get("glossary", [])}

    report.duplicate_labels.extend(
        sorted(label for label, count in label_counter.items() if label and count > 1)
    )
    report.duplicate_citation_keys.extend(
        sorted(key for key, count in citation_key_counter.items() if key and count > 1)
    )
    report.unresolved_visual_references.extend(
        sorted(ref for ref in fig_counter if ref not in allowed_visual_ids)
    )
    report.unresolved_citation_references.extend(
        sorted(ref for ref in cit_refs if ref not in allowed_citation_ids)
    )

    for artifact in contract.get("visuals", []):
        artifact_id = artifact["artifact_id"]
        occurrence_count = fig_counter.get(artifact_id, 0)
        if artifact.get("occurrence_policy") == "exactly_once" and occurrence_count != 1:
            report.duplicate_artifact_occurrences.append(f"{artifact_id}:{occurrence_count}")
        if artifact_id in fig_counter:
            for section in rendered_sections:
                if artifact_id in tokens_in_text(section["content"], "FIG") and artifact.get("explanation_required", True):
                    if not has_visual_explanation(section["content"], artifact):
                        report.missing_visual_explanations.append(artifact_id)
                        break

    if bibliography:
        for citation in contract.get("citations", []):
            if citation.get("status") == "used" and f"[{citation['citation_key']}]" not in bibliography:
                report.unresolved_citation_references.append(citation["citation_id"])

    for citation in contract.get("citations", []):
        if citation.get("status") == "used" and not citation.get("grounded_claim_ids"):
            report.citation_grounding_gaps.append(citation["citation_id"])

    for section in rendered_sections:
        content = section.get("content", "")
        if glossary_terms and not any(term and term in content for term in glossary_terms):
            report.terminology_drift.append(section["section_id"])

    report.duplicate_labels = sorted(set(report.duplicate_labels))
    report.duplicate_citation_keys = sorted(set(report.duplicate_citation_keys))
    report.unresolved_visual_references = sorted(set(report.unresolved_visual_references))
    report.unresolved_citation_references = sorted(set(report.unresolved_citation_references))
    report.missing_visual_explanations = sorted(set(report.missing_visual_explanations))
    report.citation_grounding_gaps = sorted(set(report.citation_grounding_gaps))
    report.terminology_drift = sorted(set(report.terminology_drift))
    report.duplicate_artifact_occurrences = sorted(set(report.duplicate_artifact_occurrences))

    report.warnings.extend(
        [f"Duplicate visual label: {label}" for label in report.duplicate_labels]
        + [f"Duplicate citation key: {key}" for key in report.duplicate_citation_keys]
        + [f"Unresolved visual reference: {ref}" for ref in report.unresolved_visual_references]
        + [f"Unresolved citation reference: {ref}" for ref in report.unresolved_citation_references]
        + [f"Missing visual explanation: {artifact_id}" for artifact_id in report.missing_visual_explanations]
        + [f"Citation grounding gap: {citation_id}" for citation_id in report.citation_grounding_gaps]
        + [f"Terminology drift: {section_id}" for section_id in report.terminology_drift]
        + [f"Artifact occurrence mismatch: {item}" for item in report.duplicate_artifact_occurrences]
    )
    report.passed = not report.warnings
    return report


def finalize_contract_after_render(
    contract: dict[str, Any],
    rendered_sections: list[dict[str, str]],
    bibliography: str,
    validation: RenderValidationReport,
) -> dict[str, Any]:
    """根据最终稿和校验结果，把 visual / citation 的最终状态回写进 contract。"""
    finalized = deepcopy(contract)
    combined_text = "\n\n".join(section["content"] for section in rendered_sections)
    fig_refs = tokens_in_text(combined_text, "FIG")
    cit_refs = tokens_in_text(combined_text, "CIT")
    fig_counter = Counter(fig_refs)
    cit_counter = Counter(cit_refs)
    duplicate_keys = set(validation.duplicate_citation_keys)
    unresolved_citations = set(validation.unresolved_citation_references)

    for artifact in finalized.get("visuals", []):
        artifact_id = artifact["artifact_id"]
        occurrence_count = fig_counter.get(artifact_id, 0)
        artifact["resolved_references"] = [
            section["section_id"]
            for section in rendered_sections
            if artifact_id in tokens_in_text(section["content"], "FIG")
        ]
        if occurrence_count == 0:
            artifact["render_status"] = "missing"
        elif occurrence_count == 1:
            artifact["render_status"] = "rendered"
        else:
            artifact["render_status"] = "duplicated"

    for citation in finalized.get("citations", []):
        citation_id = citation["citation_id"]
        citation_key = citation.get("citation_key")
        occurrence_count = cit_counter.get(citation_id, 0)
        bibliography_has_entry = bool(citation_key) and f"[{citation_key}]" in bibliography

        if citation_key in duplicate_keys:
            citation["status"] = "duplicate"
        elif occurrence_count > 0 and bibliography_has_entry and citation_id not in unresolved_citations:
            citation["status"] = "used"
        elif occurrence_count > 0 or citation.get("required_sections"):
            citation["status"] = "missing"
        else:
            citation["status"] = "planned"

    finalized.setdefault("global_status", {})["warnings"] = list(validation.warnings)
    return finalized
