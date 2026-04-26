from __future__ import annotations

"""Story2Proposal 的稿件评测与 benchmark suite。

这个模块负责对最终稿件进行结构化评测，并构造 baseline 对比结果。
"""

import re
from copy import deepcopy
from typing import Any

from backend.schemas import (
    BenchmarkCandidate,
    BenchmarkComparison,
    BenchmarkSuiteReport,
    DimensionDelta,
    EvaluationCriterion,
    EvaluationDimension,
    FinalizedSection,
    ManuscriptEvaluationReport,
)

from .rendering import build_bibliography_block
from .validation import validate_render_output


def _normalize_text(text: str) -> str:
    """把文本归一化，便于做弱匹配比较。"""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _contains_phrase(text: str, phrase: str) -> bool:
    """判断归一化后的文本中是否包含目标短语。"""
    return bool(phrase and _normalize_text(phrase) in _normalize_text(text))


def _paragraphs(text: str) -> list[str]:
    """按空行切分段落。"""
    return [item.strip() for item in re.split(r"\n\s*\n", text or "") if item.strip()]


def _sentences(text: str) -> list[str]:
    """按常见句末符号切分句子。"""
    return [item.strip() for item in re.split(r"[.!?。！？\n]+", text or "") if item.strip()]


def _criterion(criterion_id: str, label: str, passed: bool, evidence: list[str]) -> EvaluationCriterion:
    """构造一条评测准则对象。"""
    return EvaluationCriterion(
        criterion_id=criterion_id,
        label=label,
        passed=passed,
        evidence=evidence,
    )


def _dimension(name: str, criteria: list[EvaluationCriterion], summary_evidence: list[str]) -> EvaluationDimension:
    """根据多条准则结果构造一个评测维度。"""
    passed_count = sum(1 for criterion in criteria if criterion.passed)
    score = round(5.0 * passed_count / max(1, len(criteria)), 2)
    return EvaluationDimension(
        name=name,  # type: ignore[arg-type]
        score=score,
        passed=score >= 3.5,
        criteria=criteria,
        evidence=summary_evidence,
    )


def _finalized_sections_from_context(context: dict[str, Any]) -> list[dict[str, Any]]:
    """优先从 rendered 产物中读取 finalized sections。"""
    rendered = context.get("artifacts", {}).get("rendered", {})
    sections = rendered.get("finalized_sections") or []
    if sections:
        return list(sections)

    contract = context.get("contract") or {}
    drafts = context.get("drafts") or {}
    fallback: list[dict[str, Any]] = []
    for section in contract.get("sections", []):
        draft = drafts.get(section["section_id"])
        if not draft:
            continue
        fallback.append(
            FinalizedSection(
                section_id=section["section_id"],
                title=draft.get("title", section["title"]),
                content=draft.get("content", ""),
                notes_applied=[],
            ).model_dump(mode="json")
        )
    return fallback


def _draft_baseline_sections(context: dict[str, Any]) -> list[dict[str, Any]]:
    """把原始章节 drafts 直接拼成一个 baseline section 集合。"""
    contract = context.get("contract") or {}
    drafts = context.get("drafts") or {}
    sections: list[dict[str, Any]] = []
    for section in contract.get("sections", []):
        draft = drafts.get(section["section_id"])
        if not draft:
            continue
        sections.append(
            FinalizedSection(
                section_id=section["section_id"],
                title=draft.get("title", section["title"]),
                content=draft.get("content", ""),
                notes_applied=[],
            ).model_dump(mode="json")
        )
    return sections


def _section_map_from_sections(sections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """把 section 列表按 section_id 建成查找表。"""
    return {section["section_id"]: section for section in sections}


def _content_of(section_map: dict[str, dict[str, Any]], section_ids: list[str]) -> str:
    """按给定 section_id 顺序拼接正文内容。"""
    return "\n\n".join(section_map.get(section_id, {}).get("content", "") for section_id in section_ids)


def _evaluate_protocol(
    context: dict[str, Any],
    sections: list[dict[str, Any]],
    validation: dict[str, Any],
    *,
    protocol_version: str,
) -> ManuscriptEvaluationReport:
    """按统一 rubric 评测一组 sections。"""
    story = context.get("story") or {}
    contract = context.get("contract") or {}
    drafts = context.get("drafts") or {}
    section_map = _section_map_from_sections(sections)
    contract_sections = contract.get("sections", [])
    citations = contract.get("citations", [])
    visuals = contract.get("visuals", [])
    revision_log = contract.get("revision_log", [])
    claim_links = contract.get("claim_evidence_links", [])
    all_rendered_text = "\n\n".join(section.get("content", "") for section in section_map.values())

    approved_sections = [section for section in contract_sections if section.get("status") == "approved"]
    required_section_ids = [section["section_id"] for section in contract_sections]
    rendered_required_ids = [section_id for section_id in required_section_ids if section_id in section_map]
    unresolved_structure = (
        len(validation.get("duplicate_artifact_occurrences", []))
        + len(validation.get("unresolved_visual_references", []))
        + len(validation.get("unresolved_citation_references", []))
    )
    structural_integrity = _dimension(
        "structural_integrity",
        [
            _criterion(
                "approved_sections",
                "All planned sections are approved.",
                len(approved_sections) == len(contract_sections),
                [f"approved_sections={len(approved_sections)}/{len(contract_sections)}"],
            ),
            _criterion(
                "rendered_sections",
                "All planned sections appear in the manuscript.",
                len(rendered_required_ids) == len(required_section_ids),
                [f"rendered_sections={len(rendered_required_ids)}/{len(required_section_ids)}"],
            ),
            _criterion(
                "no_structural_validation_errors",
                "The render stage reports no unresolved structural references.",
                unresolved_structure == 0,
                [f"structural_reference_errors={unresolved_structure}"],
            ),
        ],
        [
            f"approved_sections={len(approved_sections)}/{len(contract_sections)}",
            f"rendered_sections={len(rendered_required_ids)}/{len(required_section_ids)}",
            f"structural_reference_errors={unresolved_structure}",
        ],
    )

    paragraphs = _paragraphs(all_rendered_text)
    paragraph_lengths = [len(_sentences(paragraph)) for paragraph in paragraphs]
    coherent_paragraphs = sum(1 for size in paragraph_lengths if 1 <= size <= 6)
    unresolved_items = sum(len(draft.get("unresolved_items", [])) for draft in drafts.values())
    terminology_drift = len(validation.get("terminology_drift", []))
    writing_clarity = _dimension(
        "writing_clarity",
        [
            _criterion(
                "paragraph_coherence",
                "Most paragraphs stay within a readable sentence span.",
                coherent_paragraphs >= max(1, int(0.7 * max(1, len(paragraphs)))),
                [f"coherent_paragraphs={coherent_paragraphs}/{len(paragraphs)}"],
            ),
            _criterion(
                "no_unresolved_items",
                "Final drafts do not carry unresolved placeholders.",
                unresolved_items == 0,
                [f"unresolved_items={unresolved_items}"],
            ),
            _criterion(
                "terminology_stable",
                "Terminology remains stable across the manuscript.",
                terminology_drift == 0,
                [f"terminology_drift={terminology_drift}"],
            ),
        ],
        [
            f"coherent_paragraphs={coherent_paragraphs}/{len(paragraphs)}",
            f"unresolved_items={unresolved_items}",
            f"terminology_drift={terminology_drift}",
        ],
    )

    method_text = _content_of(section_map, ["method"])
    experiment_text = _content_of(section_map, ["experiments", "results_discussion"])
    verified_claims = sum(1 for claim in claim_links if claim.get("verified"))
    dataset_mentions = sum(
        1
        for experiment in story.get("experiments", [])
        if _contains_phrase(method_text + "\n" + experiment_text, experiment.get("dataset", ""))
    )
    metric_mentions = sum(
        1
        for experiment in story.get("experiments", [])
        for metric in experiment.get("metrics", [])
        if _contains_phrase(method_text + "\n" + experiment_text, metric)
    )
    methodological_rigor = _dimension(
        "methodological_rigor",
        [
            _criterion(
                "verified_claims",
                "Claims are verified against evidence links.",
                verified_claims == len(claim_links) and bool(claim_links),
                [f"verified_claims={verified_claims}/{len(claim_links)}"],
            ),
            _criterion(
                "dataset_coverage",
                "Story experiments are reflected in the manuscript.",
                dataset_mentions == len(story.get("experiments", [])),
                [f"dataset_mentions={dataset_mentions}/{len(story.get('experiments', []))}"],
            ),
            _criterion(
                "metric_coverage",
                "Evaluation metrics appear in the method/results discussion.",
                metric_mentions >= sum(len(exp.get("metrics", [])) for exp in story.get("experiments", [])),
                [f"metric_mentions={metric_mentions}"],
            ),
        ],
        [
            f"verified_claims={verified_claims}/{len(claim_links)}",
            f"dataset_mentions={dataset_mentions}/{len(story.get('experiments', []))}",
            f"metric_mentions={metric_mentions}",
        ],
    )

    finding_mentions = sum(1 for finding in story.get("findings", []) if _contains_phrase(all_rendered_text, finding))
    evidence_trace_count = sum(len(draft.get("evidence_traces", [])) for draft in drafts.values())
    experimental_substance = _dimension(
        "experimental_substance",
        [
            _criterion(
                "findings_realized",
                "Key findings from the story are realized in the manuscript.",
                finding_mentions >= len(story.get("findings", [])),
                [f"finding_mentions={finding_mentions}/{len(story.get('findings', []))}"],
            ),
            _criterion(
                "evidence_trace_density",
                "Experimental claims are backed by explicit evidence traces.",
                evidence_trace_count >= max(1, len(claim_links)),
                [f"evidence_traces={evidence_trace_count}", f"claims={len(claim_links)}"],
            ),
            _criterion(
                "experiment_sections_present",
                "Experiment-oriented sections exist in the manuscript.",
                "experiments" in section_map and "results_discussion" in section_map,
                [f"present_sections={sorted(section_map)}"],
            ),
        ],
        [
            f"finding_mentions={finding_mentions}/{len(story.get('findings', []))}",
            f"evidence_traces={evidence_trace_count}",
            f"present_sections={sorted(section_map)}",
        ],
    )

    used_citations = [citation for citation in citations if citation.get("status") == "used"]
    grounded_citations = [citation for citation in used_citations if citation.get("grounded_claim_ids")]
    duplicate_keys = len(validation.get("duplicate_citation_keys", []))
    unresolved_citations = len(validation.get("unresolved_citation_references", []))
    grounding_gaps = len(validation.get("citation_grounding_gaps", []))
    citation_hygiene = _dimension(
        "citation_hygiene",
        [
            _criterion(
                "unique_citation_keys",
                "Citation keys are unique.",
                duplicate_keys == 0,
                [f"duplicate_citation_keys={duplicate_keys}"],
            ),
            _criterion(
                "resolved_citations",
                "All used citations resolve to the bibliography.",
                unresolved_citations == 0,
                [f"unresolved_citation_references={unresolved_citations}"],
            ),
            _criterion(
                "grounded_citations",
                "Used citations are grounded to explicit claims.",
                len(grounded_citations) == len(used_citations),
                [
                    f"grounded_citations={len(grounded_citations)}/{len(used_citations)}",
                    f"citation_grounding_gaps={grounding_gaps}",
                ],
            ),
        ],
        [
            f"duplicate_citation_keys={duplicate_keys}",
            f"unresolved_citation_references={unresolved_citations}",
            f"grounded_citations={len(grounded_citations)}/{len(used_citations)}",
        ],
    )

    traceable_sections = sum(
        1 for draft in drafts.values() if draft.get("story_traces") and draft.get("evidence_traces")
    )
    setup_mentions = sum(
        1
        for experiment in story.get("experiments", [])
        if _contains_phrase(method_text + "\n" + experiment_text, experiment.get("setup", ""))
    )
    reproducibility = _dimension(
        "reproducibility",
        [
            _criterion(
                "traceable_sections",
                "Sections preserve both story traces and evidence traces.",
                traceable_sections == len(drafts) and bool(drafts),
                [f"traceable_sections={traceable_sections}/{len(drafts)}"],
            ),
            _criterion(
                "setup_coverage",
                "Experiment setup details appear in the manuscript.",
                setup_mentions == len(story.get("experiments", [])),
                [f"setup_mentions={setup_mentions}/{len(story.get('experiments', []))}"],
            ),
            _criterion(
                "revision_memory",
                "Contract revision history is populated.",
                len(revision_log) >= len(contract_sections),
                [f"revision_records={len(revision_log)}", f"sections={len(contract_sections)}"],
            ),
        ],
        [
            f"traceable_sections={traceable_sections}/{len(drafts)}",
            f"setup_mentions={setup_mentions}/{len(story.get('experiments', []))}",
            f"revision_records={len(revision_log)}",
        ],
    )

    render_warnings = len(validation.get("warnings", []))
    formatting_stability = _dimension(
        "formatting_stability",
        [
            _criterion(
                "render_validation_passed",
                "Deterministic render validation passes.",
                bool(validation.get("passed", False)),
                [f"render_validation_passed={validation.get('passed', False)}"],
            ),
            _criterion(
                "no_duplicate_artifacts",
                "Visual artifacts satisfy exact-once occurrence policy.",
                len(validation.get("duplicate_artifact_occurrences", [])) == 0,
                [f"duplicate_artifact_occurrences={len(validation.get('duplicate_artifact_occurrences', []))}"],
            ),
            _criterion(
                "warning_budget",
                "Render warning count stays low.",
                render_warnings <= 1,
                [f"render_warnings={render_warnings}"],
            ),
        ],
        [
            f"render_validation_passed={validation.get('passed', False)}",
            f"duplicate_artifact_occurrences={len(validation.get('duplicate_artifact_occurrences', []))}",
            f"render_warnings={render_warnings}",
        ],
    )

    rendered_visuals = [visual for visual in visuals if visual.get("render_status") == "rendered"]
    target_section_hits = 0
    for visual in visuals:
        target_sections = visual.get("target_sections", [])
        if not target_sections:
            continue
        visual_token = f"[FIG:{visual['artifact_id']}]"
        if any(visual_token in section_map.get(section_id, {}).get("content", "") for section_id in target_sections):
            target_section_hits += 1
    visual_communication = _dimension(
        "visual_communication",
        [
            _criterion(
                "visuals_rendered",
                "Planned visuals are actually rendered.",
                len(rendered_visuals) == len(visuals),
                [f"rendered_visuals={len(rendered_visuals)}/{len(visuals)}"],
            ),
            _criterion(
                "visual_explanations_present",
                "Referenced visuals have local explanatory context.",
                len(validation.get("missing_visual_explanations", [])) == 0,
                [f"missing_visual_explanations={len(validation.get('missing_visual_explanations', []))}"],
            ),
            _criterion(
                "visual_section_alignment",
                "Visuals appear in their intended target sections.",
                target_section_hits == len(visuals),
                [f"target_section_hits={target_section_hits}/{len(visuals)}"],
            ),
        ],
        [
            f"rendered_visuals={len(rendered_visuals)}/{len(visuals)}",
            f"missing_visual_explanations={len(validation.get('missing_visual_explanations', []))}",
            f"target_section_hits={target_section_hits}/{len(visuals)}",
        ],
    )

    dimensions = [
        structural_integrity,
        writing_clarity,
        methodological_rigor,
        experimental_substance,
        citation_hygiene,
        reproducibility,
        formatting_stability,
        visual_communication,
    ]
    overall_score = round(sum(item.score for item in dimensions) / len(dimensions), 2)

    strengths = [f"{item.name}: passed" for item in dimensions if item.passed]
    risks = [f"{item.name}: needs attention" for item in dimensions if not item.passed]

    recommended_actions: list[str] = []
    if not formatting_stability.passed:
        recommended_actions.append("Resolve deterministic render issues before treating the manuscript as stable.")
    if not citation_hygiene.passed:
        recommended_actions.append("Tighten citation grounding and bibliography resolution.")
    if not visual_communication.passed:
        recommended_actions.append("Strengthen visual explanation and section placement alignment.")
    if not methodological_rigor.passed or not experimental_substance.passed:
        recommended_actions.append("Revisit method/results sections to improve experiment-grounded support.")
    if not recommended_actions:
        recommended_actions.append("Current manuscript satisfies the protocol; continue with human review or downstream polishing.")

    return ManuscriptEvaluationReport(
        protocol_version=protocol_version,
        overall_score=overall_score,
        dimensions=dimensions,
        strengths=strengths,
        risks=risks,
        recommended_actions=recommended_actions,
    )


def evaluate_primary_report(context: dict[str, Any]) -> ManuscriptEvaluationReport:
    """评测最终稿件本身。"""
    rendered = context.get("artifacts", {}).get("rendered", {})
    sections = _finalized_sections_from_context(context)
    validation = rendered.get("validation") or {}
    return _evaluate_protocol(
        context,
        sections,
        validation,
        protocol_version="story2proposal-rubric-v3",
    )


def _build_candidate_report(
    context: dict[str, Any],
    *,
    candidate_id: str,
    label: str,
    source: str,
    sections: list[dict[str, Any]],
) -> BenchmarkCandidate:
    """为一份候选稿件构造 benchmark 条目。"""
    candidate_context = deepcopy(context)
    candidate_context.setdefault("artifacts", {})
    bibliography = build_bibliography_block(candidate_context)
    validation = validate_render_output(candidate_context.get("contract") or {}, sections, bibliography).model_dump(mode="json")
    report = _evaluate_protocol(
        candidate_context,
        sections,
        validation,
        protocol_version="story2proposal-rubric-v3",
    )
    return BenchmarkCandidate(
        candidate_id=candidate_id,
        label=label,
        source=source,
        report=report,
    )


def _compare_candidates(candidate: BenchmarkCandidate, baseline: BenchmarkCandidate) -> BenchmarkComparison:
    """比较候选稿件与 baseline 的维度分数差异。"""
    baseline_dimensions = {dimension.name: dimension for dimension in baseline.report.dimensions}
    candidate_dimensions = {dimension.name: dimension for dimension in candidate.report.dimensions}
    deltas: list[DimensionDelta] = []
    summary: list[str] = []

    for name, candidate_dimension in candidate_dimensions.items():
        baseline_dimension = baseline_dimensions[name]
        delta = round(candidate_dimension.score - baseline_dimension.score, 2)
        deltas.append(
            DimensionDelta(
                name=name,
                baseline_score=baseline_dimension.score,
                candidate_score=candidate_dimension.score,
                delta=delta,
            )
        )
        if delta > 0:
            summary.append(f"{name}: +{delta}")
        elif delta < 0:
            summary.append(f"{name}: {delta}")

    return BenchmarkComparison(
        candidate_id=candidate.candidate_id,
        baseline_id=baseline.candidate_id,
        overall_delta=round(candidate.report.overall_score - baseline.report.overall_score, 2),
        dimension_deltas=deltas,
        summary=summary,
    )


def evaluate_manuscript_bundle(context: dict[str, Any]) -> tuple[ManuscriptEvaluationReport, BenchmarkSuiteReport]:
    """同时产出主评测报告与 benchmark suite。"""
    primary_report = evaluate_primary_report(context)

    final_sections = _finalized_sections_from_context(context)
    draft_baseline_sections = _draft_baseline_sections(context)

    primary_candidate = _build_candidate_report(
        context,
        candidate_id="finalized_manuscript",
        label="Finalized Manuscript",
        source="rendered.finalized_sections",
        sections=final_sections,
    )
    baseline_candidate = _build_candidate_report(
        context,
        candidate_id="draft_stitch_baseline",
        label="Draft Stitch Baseline",
        source="raw section drafts",
        sections=draft_baseline_sections,
    )

    candidates = [primary_candidate, baseline_candidate]
    winner = max(candidates, key=lambda item: item.report.overall_score)
    comparison = _compare_candidates(primary_candidate, baseline_candidate)

    benchmark = BenchmarkSuiteReport(
        benchmark_name="story2proposal-single-run-benchmark",
        primary_candidate_id=primary_candidate.candidate_id,
        winner_candidate_id=winner.candidate_id,
        candidates=candidates,
        comparisons=[comparison],
        summary=[
            f"winner={winner.candidate_id}",
            f"primary_overall_score={primary_candidate.report.overall_score}",
            f"baseline_overall_score={baseline_candidate.report.overall_score}",
            f"overall_delta={comparison.overall_delta}",
        ],
    )
    return primary_report, benchmark
