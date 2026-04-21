from __future__ import annotations

from copy import deepcopy
from typing import Any

from schemas import (
    CitationSlot,
    ClaimEvidenceLink,
    ContractPatch,
    ManuscriptBlueprint,
    ManuscriptContract,
    ResearchStory,
    SectionContract,
    ValidationRule,
    VisualArtifact,
)


def slugify(value: str) -> str:
    value = value.lower().strip()
    sanitized = "".join(char if char.isalnum() else "_" for char in value)
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_") or "item"


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
    writing_order = [
        section_id for section_id in blueprint.writing_order if section_id in allowed
    ]
    return ManuscriptBlueprint(
        title=blueprint.title,
        abstract_plan=blueprint.abstract_plan,
        section_plans=section_plans,
        visual_plan=visuals,
        writing_order=writing_order,
    )


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
                    claim["verified"] = patch.value.lower() in {
                        "true",
                        "verified",
                        "method",
                        "introduction",
                        "abstract",
                        "title",
                    }
                    break
    return contract


def snapshot_contract(context: dict[str, Any]) -> dict[str, Any] | None:
    contract = context.get("contract")
    if contract is None:
        return None
    return deepcopy(contract)
