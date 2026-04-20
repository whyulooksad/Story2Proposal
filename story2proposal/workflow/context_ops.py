from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from story2proposal.llm_io import json_dumps
from story2proposal.schemas import (
    CitationSlot,
    ClaimEvidenceLink,
    ContractPatch,
    EvaluationFeedback,
    ManuscriptBlueprint,
    ManuscriptContract,
    RefinerOutput,
    RenderedManuscript,
    ResearchStory,
    RevisionRecord,
    SectionContract,
    SectionDraft,
    ValidationRule,
    VisualArtifact,
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


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "item"


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
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
                "last_aggregate_feedback": context.get("artifacts", {}).get(
                    "last_aggregate_feedback"
                ),
                "next_action": context.get("artifacts", {}).get("next_action"),
            },
        },
    )


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


def initialize_contract(
    story: ResearchStory,
    blueprint: ManuscriptBlueprint,
) -> ManuscriptContract:
    section_lookup = {plan.section_id: plan for plan in blueprint.section_plans}
    sections = [
        SectionContract(
            section_id=plan.section_id,
            title=plan.title,
            purpose=plan.goal,
            required_claims=plan.must_cover,
            required_evidence_ids=plan.evidence_refs,
            required_visual_ids=plan.visual_refs,
            required_citation_ids=plan.citation_refs,
            depends_on_sections=plan.input_dependencies,
        )
        for plan in blueprint.section_plans
    ]
    visuals = [
        VisualArtifact(
            artifact_id=visual.artifact_id,
            kind=visual.kind,
            label=visual.label,
            caption_brief=visual.caption_brief,
            semantic_role=visual.semantic_role,
            source_evidence_ids=[
                evidence
                for evidence in section_lookup.get(
                    (visual.target_sections or [""])[0], None
                ).evidence_refs
            ]
            if visual.target_sections
            and section_lookup.get((visual.target_sections or [""])[0]) is not None
            else [],
            target_sections=visual.target_sections,
            placement_hint=", ".join(visual.target_sections) if visual.target_sections else None,
        )
        for visual in blueprint.visual_plan
    ]
    citations = [
        CitationSlot(
            citation_id=ref.reference_id,
            citation_key=slugify(ref.title)[:30],
            title=ref.title,
            authors=ref.authors,
            year=ref.year,
            venue=ref.venue,
        )
        for ref in story.references
    ]
    claim_links: list[ClaimEvidenceLink] = []
    for plan in blueprint.section_plans:
        for index, claim in enumerate(plan.must_cover, start=1):
            claim_links.append(
                ClaimEvidenceLink(
                    claim_id=f"{plan.section_id}_claim_{index}",
                    claim_text=claim,
                    evidence_ids=plan.evidence_refs,
                    section_id=plan.section_id,
                    verified=False,
                )
            )
    return ManuscriptContract(
        contract_id=f"{story.story_id}_contract",
        paper_title=blueprint.title or story.title_hint,
        target_venue=story.metadata.get("target_venue"),
        sections=sections,
        visuals=visuals,
        citations=citations,
        glossary=[story.topic],
        claim_evidence_links=claim_links,
        validation_rules=[
            ValidationRule(
                rule_id="coverage",
                rule_type="section_coverage",
                description="Every section must cover required claims.",
                severity="high",
            ),
            ValidationRule(
                rule_id="visual_refs",
                rule_type="visual_references",
                description="Required visuals must be referenced with [FIG:<id>] tokens.",
                severity="medium",
            ),
            ValidationRule(
                rule_id="citation_refs",
                rule_type="citation_slots",
                description="Required citations must be referenced with [CIT:<id>] tokens.",
                severity="medium",
            ),
        ],
        global_status={"state": "initialized"},
    )


def trim_blueprint_to_sections(
    blueprint: ManuscriptBlueprint,
    active_sections: list[str],
) -> ManuscriptBlueprint:
    allowed = set(active_sections)
    section_plans = [
        plan for plan in blueprint.section_plans if plan.section_id in allowed
    ]
    visuals = [
        visual
        for visual in blueprint.visual_plan
        if any(section in allowed for section in visual.target_sections)
    ]
    writing_order = [section_id for section_id in blueprint.writing_order if section_id in allowed]
    return ManuscriptBlueprint(
        title=blueprint.title,
        abstract_plan=blueprint.abstract_plan,
        section_plans=section_plans,
        visual_plan=visuals,
        writing_order=writing_order,
    )


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


def save_section_draft(
    context: dict[str, Any],
    draft: SectionDraft,
) -> dict[str, Any]:
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


def apply_contract_patches(contract: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    for patch in [ContractPatch.model_validate(item) for item in patches]:
        if patch.patch_type == "append_glossary":
            if patch.value not in contract["glossary"]:
                contract["glossary"].append(patch.value)
        elif patch.patch_type == "set_section_status":
            for section in contract["sections"]:
                if section["section_id"] == patch.target_id:
                    section["status"] = patch.value
                    break
        elif patch.patch_type == "add_required_citation":
            for section in contract["sections"]:
                if section["section_id"] == patch.target_id and patch.value not in section["required_citation_ids"]:
                    section["required_citation_ids"].append(patch.value)
                    break
        elif patch.patch_type == "add_required_visual":
            for section in contract["sections"]:
                if section["section_id"] == patch.target_id and patch.value not in section["required_visual_ids"]:
                    section["required_visual_ids"].append(patch.value)
                    break
        elif patch.patch_type == "mark_claim_verified":
            for claim in contract["claim_evidence_links"]:
                if claim["claim_id"] == patch.target_id or claim["claim_text"] == patch.target_id:
                    claim["verified"] = patch.value.lower() in {"true", "verified", "method", "introduction", "abstract", "title"}
                    break
    return contract


def _tokens_in_content(content: str, prefix: str) -> set[str]:
    pattern = re.compile(rf"\[{prefix}:([A-Za-z0-9_]+)\]")
    return {match.group(1) for match in pattern.finditer(content)}


def validate_section_coverage(
    section: dict[str, Any],
    draft: dict[str, Any],
) -> list[str]:
    covered = set(draft.get("covered_claim_ids", []))
    required = set(section.get("required_claims", []))
    missing = [claim for claim in required if claim not in covered]
    return [f"Missing required claim: {claim}" for claim in missing]


def validate_visual_references(
    section: dict[str, Any],
    draft: dict[str, Any],
) -> list[str]:
    content_ids = _tokens_in_content(draft.get("content", ""), "FIG")
    referenced_ids = set(draft.get("referenced_visual_ids", [])) | content_ids
    missing = set(section.get("required_visual_ids", [])) - referenced_ids
    return [f"Missing visual reference: {artifact_id}" for artifact_id in sorted(missing)]


def validate_citation_slots(
    section: dict[str, Any],
    draft: dict[str, Any],
) -> list[str]:
    content_ids = _tokens_in_content(draft.get("content", ""), "CIT")
    referenced_ids = set(draft.get("referenced_citation_ids", [])) | content_ids
    missing = set(section.get("required_citation_ids", [])) - referenced_ids
    return [f"Missing citation reference: {citation_id}" for citation_id in sorted(missing)]


def aggregate_current_feedback(context: dict[str, Any]) -> dict[str, Any]:
    section = get_current_section_contract(context) or {}
    draft = get_current_draft(context) or {}
    reviews = get_current_reviews(context)
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
    if runtime["current_section_id"] is None:
        runtime["final_status"] = "all_sections_completed"
        runtime["next_node"] = "refiner"
    else:
        runtime["next_node"] = "section_writer"
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


def render_markdown_manuscript(context: dict[str, Any]) -> RenderedManuscript:
    contract = context.get("contract") or {}
    drafts = context.get("drafts") or {}
    sections = []
    warnings: list[str] = []
    title = contract.get("paper_title") or context.get("story", {}).get("title_hint") or "Untitled Manuscript"
    sections.append(f"# {title}")
    refiner_output = context.get("artifacts", {}).get("refiner_output", {})
    abstract_override = context.get("artifacts", {}).get("abstract_override")
    for section in contract.get("sections", []):
        draft = drafts.get(section["section_id"])
        if draft is None:
            warnings.append(f"Missing draft for section {section['section_id']}")
            continue
        content = draft["content"]
        if section["section_id"] == "abstract" and abstract_override:
            content = abstract_override
        if section["section_id"] in refiner_output.get("section_notes", {}):
            content = f"{content}\n\n> Refiner note: {refiner_output['section_notes'][section['section_id']]}"
        sections.append(f"## {draft['title']}\n\n{content}")
    bibliography = build_bibliography_block(context)
    if bibliography:
        sections.append("## References\n\n" + bibliography)
    markdown = "\n\n".join(sections).strip() + "\n"
    latex = render_latex_from_markdown(title, contract.get("sections", []), drafts, bibliography, abstract_override)
    return RenderedManuscript(markdown=markdown, latex=latex, warnings=warnings)


def render_latex_from_markdown(
    title: str,
    sections: list[dict[str, Any]],
    drafts: dict[str, Any],
    bibliography: str,
    abstract_override: str | None,
) -> str:
    body: list[str] = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\begin{document}",
        rf"\title{{{title}}}",
        r"\maketitle",
    ]
    for section in sections:
        draft = drafts.get(section["section_id"])
        if draft is None:
            continue
        content = draft["content"]
        if section["section_id"] == "abstract" and abstract_override:
            content = abstract_override
        body.append(rf"\section{{{draft['title']}}}")
        body.append(content.replace("_", r"\_"))
    if bibliography:
        body.append(r"\section{References}")
        body.append(bibliography.replace("_", r"\_"))
    body.append(r"\end{document}")
    return "\n".join(body) + "\n"


def build_bibliography_block(context: dict[str, Any]) -> str:
    contract = context.get("contract") or {}
    lines = []
    for item in contract.get("citations", []):
        authors = ", ".join(item.get("authors", [])) or "Unknown"
        year = item.get("year") or "n.d."
        venue = f". {item['venue']}" if item.get("venue") else ""
        lines.append(
            f"- [{item['citation_key']}] {authors} ({year}). {item['title']}{venue}."
        )
    return "\n".join(lines)


def store_render_output(context: dict[str, Any], rendered: RenderedManuscript) -> dict[str, Any]:
    context["artifacts"]["rendered"] = rendered.model_dump(mode="json")
    context["runtime"]["final_status"] = "rendered"
    refresh_prompt_views(context)
    persist_run_state(context)
    return context
