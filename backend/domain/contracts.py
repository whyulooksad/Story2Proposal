from __future__ import annotations

"""Story2Proposal 的 contract 构建与更新逻辑。

这个模块负责把 blueprint 转成执行期 contract，并在运行过程中持续吸收 review 产生的结构化 patch。
"""

from copy import deepcopy
from typing import Any

from backend.schemas import (
    CitationSlot,
    ClaimEvidenceLink,
    ClaimRequirement,
    ContractPatch,
    ContractStatus,
    ManuscriptBlueprint,
    ManuscriptContract,
    ResearchStory,
    SectionCitationObligation,
    SectionContract,
    SectionVisualObligation,
    StyleGuide,
    TerminologyItem,
    ValidationRule,
    VisualArtifact,
)


def slugify(value: str) -> str:
    """把自由文本转成稳定的标识符风格 token。"""
    value = value.lower().strip()
    sanitized = "".join(char if char.isalnum() else "_" for char in value)
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_") or "item"


def _normalize_citation_key(raw_title: str, authors: list[str], year: int | None) -> str:
    """生成 citation key 的稳定基底。"""
    author_token = slugify(authors[0].split()[-1]) if authors else "ref"
    title_token = slugify(raw_title)[:24]
    year_token = str(year) if year is not None else "nd"
    return f"{author_token}_{year_token}_{title_token}".strip("_")


def _build_citation_keys(story: ResearchStory) -> dict[str, str]:
    """为输入 references 生成去重后的 citation key。"""
    assigned: dict[str, str] = {}
    seen: dict[str, int] = {}
    for ref in story.references:
        base = _normalize_citation_key(ref.title, ref.authors, ref.year)
        index = seen.get(base, 0)
        key = base if index == 0 else f"{base}_{index + 1}"
        seen[base] = index + 1
        assigned[ref.reference_id] = key
    return assigned


def _derive_output_language(story: ResearchStory) -> str:
    """从 story metadata 推导目标输出语言。"""
    language = story.metadata.get("writing_language")
    return language if language in {"en", "zh"} else "en"


def _build_terminology(story: ResearchStory) -> list[TerminologyItem]:
    """从 story 里初始化一版术语表。"""
    items = [
        TerminologyItem(
            term=story.topic,
            preferred_form=story.topic,
            definition=story.problem_statement or None,
        )
    ]
    for keyword in story.metadata.get("keywords", []):
        if isinstance(keyword, str) and keyword.strip():
            items.append(TerminologyItem(term=keyword, preferred_form=keyword))
    return items


def _default_story_fields() -> list[str]:
    """返回默认的 story provenance 字段集合。"""
    return ["topic", "problem_statement", "motivation", "core_idea", "method_summary", "findings"]


def _section_story_fields(section_id: str, plan_story_fields: list[str] | None) -> list[str]:
    """按 section 语义归一化 source story fields。"""
    if plan_story_fields:
        return list(dict.fromkeys(plan_story_fields))

    defaults: dict[str, list[str]] = {
        "title": ["topic", "core_idea"],
        "abstract": ["topic", "problem_statement", "core_idea", "method_summary", "findings"],
        "introduction": ["topic", "problem_statement", "motivation", "contributions"],
        "method": ["core_idea", "method_summary", "contributions", "assets"],
        "experiments": ["experiments", "baselines", "findings"],
        "results_discussion": ["findings", "experiments", "limitations"],
        "related_work": ["references", "topic", "problem_statement"],
        "limitations": ["limitations", "findings"],
        "conclusion": ["contributions", "findings", "limitations"],
    }
    return defaults.get(section_id, _default_story_fields())


def _resolve_visual_evidence_ids(
    visual_plan: Any,
    section_lookup: dict[str, Any],
) -> list[str]:
    """为 visual plan 归一化 source evidence ids。"""
    if getattr(visual_plan, "source_evidence_ids", None):
        return list(dict.fromkeys(visual_plan.source_evidence_ids))

    evidence_ids: list[str] = []
    for section_id in getattr(visual_plan, "target_sections", []) or []:
        plan = section_lookup.get(section_id)
        if plan is None:
            continue
        for evidence_id in getattr(plan, "evidence_refs", []) or []:
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
    return evidence_ids


def initialize_contract(
    story: ResearchStory,
    blueprint: ManuscriptBlueprint,
) -> ManuscriptContract:
    """根据 story 和 blueprint 构造初始 manuscript contract。"""
    section_lookup = {plan.section_id: plan for plan in blueprint.section_plans}
    citation_keys = _build_citation_keys(story)
    citation_section_map: dict[str, list[str]] = {}
    sections: list[SectionContract] = []
    claim_links: list[ClaimEvidenceLink] = []

    for plan in blueprint.section_plans:
        claim_requirements: list[ClaimRequirement] = []
        claim_ids: list[str] = []
        source_story_fields = _section_story_fields(plan.section_id, list(plan.source_story_fields))
        for index, claim in enumerate(plan.must_cover, start=1):
            claim_id = f"{plan.section_id}_claim_{index}"
            claim_ids.append(claim_id)
            claim_requirements.append(
                ClaimRequirement(
                    claim_id=claim_id,
                    claim_text=claim,
                    evidence_ids=list(plan.evidence_refs),
                    citation_ids=list(plan.citation_refs),
                    source_story_fields=source_story_fields,
                )
            )
            claim_links.append(
                ClaimEvidenceLink(
                    claim_id=claim_id,
                    claim_text=claim,
                    evidence_ids=list(plan.evidence_refs),
                    citation_ids=list(plan.citation_refs),
                    section_id=plan.section_id,
                    source_story_fields=source_story_fields,
                )
            )

        for citation_id in plan.citation_refs:
            citation_section_map.setdefault(citation_id, []).append(plan.section_id)

        sections.append(
            SectionContract(
                section_id=plan.section_id,
                title=plan.title,
                purpose=plan.goal,
                required_claims=list(plan.must_cover),
                required_claim_ids=claim_ids,
                claim_requirements=claim_requirements,
                required_evidence_ids=list(plan.evidence_refs),
                required_visual_ids=list(plan.visual_refs),
                required_citation_ids=list(plan.citation_refs),
                depends_on_sections=list(plan.input_dependencies),
                source_story_fields=source_story_fields,
                visual_obligations=[
                    SectionVisualObligation(
                        artifact_id=artifact_id,
                        placement_hint=plan.section_id,
                        narrative_role=f"Support section {plan.section_id} claims",
                    )
                    for artifact_id in plan.visual_refs
                ],
                citation_obligations=[
                    SectionCitationObligation(
                        citation_id=citation_id,
                        purpose=f"Ground section {plan.section_id}",
                        grounded_claim_ids=claim_ids,
                    )
                    for citation_id in plan.citation_refs
                ],
            )
        )

    visuals = [
        VisualArtifact(
            artifact_id=visual.artifact_id,
            kind=visual.kind,
            label=visual.label,
            canonical_label=visual.label,
            caption_brief=visual.caption_brief,
            semantic_role=visual.semantic_role,
            source_evidence_ids=_resolve_visual_evidence_ids(visual, section_lookup),
            target_sections=list(visual.target_sections),
            placement_hint=", ".join(visual.target_sections) if visual.target_sections else None,
            placement_constraint="after_section",
            materialization_status="planned",
            render_status="planned",
        )
        for visual in blueprint.visual_plan
    ]

    citations = [
        CitationSlot(
            citation_id=ref.reference_id,
            citation_key=citation_keys[ref.reference_id],
            title=ref.title,
            authors=ref.authors,
            year=ref.year,
            venue=ref.venue,
            source_reference_id=ref.reference_id,
            grounded_claim_ids=[
                requirement.claim_id
                for section in sections
                for requirement in section.claim_requirements
                if ref.reference_id in requirement.citation_ids
            ],
            required_sections=citation_section_map.get(ref.reference_id, []),
        )
        for ref in story.references
    ]

    return ManuscriptContract(
        contract_id=f"{story.story_id}_contract",
        paper_title=blueprint.title or story.title_hint,
        target_venue=story.metadata.get("target_venue"),
        style_guide=StyleGuide(output_language=_derive_output_language(story)),
        sections=sections,
        visuals=visuals,
        citations=citations,
        glossary=_build_terminology(story),
        claim_evidence_links=claim_links,
        validation_rules=[
            ValidationRule(
                rule_id="section_coverage",
                rule_type="section_coverage",
                description="Every section must cover all required claims.",
                severity="high",
                scope="section",
            ),
            ValidationRule(
                rule_id="claim_evidence_alignment",
                rule_type="claim_evidence_alignment",
                description="Claims must be grounded in evidence traces.",
                severity="high",
                scope="claim",
            ),
            ValidationRule(
                rule_id="visual_reference_resolution",
                rule_type="visual_reference_resolution",
                description="All required visuals must be referenced with valid [FIG:<id>] tokens.",
                severity="high",
                scope="visual",
            ),
            ValidationRule(
                rule_id="artifact_occurrence_exactly_once",
                rule_type="artifact_occurrence",
                description="Each registered visual artifact must appear exactly once in the final manuscript.",
                severity="high",
                scope="visual",
            ),
            ValidationRule(
                rule_id="citation_resolution",
                rule_type="citation_resolution",
                description="All required citations must be referenced with valid [CIT:<id>] tokens.",
                severity="high",
                scope="citation",
            ),
            ValidationRule(
                rule_id="citation_grounding",
                rule_type="citation_grounding",
                description="Used citations must remain grounded to the claims they support.",
                severity="high",
                scope="citation",
            ),
            ValidationRule(
                rule_id="label_uniqueness",
                rule_type="label_uniqueness",
                description="Visual labels must be unique and resolvable.",
                severity="high",
                scope="document",
            ),
            ValidationRule(
                rule_id="bibliography_consistency",
                rule_type="bibliography_consistency",
                description="Used citations must resolve to exactly one bibliography entry.",
                severity="high",
                scope="document",
            ),
            ValidationRule(
                rule_id="narrative_visual_alignment",
                rule_type="narrative_visual_alignment",
                description="Every referenced visual must have local explanatory context.",
                severity="medium",
                scope="visual",
            ),
            ValidationRule(
                rule_id="terminology_consistency",
                rule_type="terminology_consistency",
                description="Core terminology should remain consistent across sections.",
                severity="medium",
                scope="document",
            ),
            ValidationRule(
                rule_id="revision_traceability",
                rule_type="revision_traceability",
                description="Revision history must preserve section-level provenance and patch traces.",
                severity="medium",
                scope="document",
            ),
        ],
        global_status=ContractStatus(
            state="initialized",
            current_section_id=blueprint.writing_order[0] if blueprint.writing_order else None,
            pending_sections=list(blueprint.writing_order),
        ),
    )


def trim_blueprint_to_sections(
    blueprint: ManuscriptBlueprint,
    active_sections: list[str],
) -> ManuscriptBlueprint:
    """把 blueprint 裁剪到更小的 active section 子集。"""
    allowed = set(active_sections)
    section_plans = [plan for plan in blueprint.section_plans if plan.section_id in allowed]
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


def _append_glossary(contract: dict[str, Any], value: Any) -> None:
    """向 glossary 追加术语。"""
    if not isinstance(value, dict):
        item = {"term": str(value), "preferred_form": str(value), "aliases": []}
    else:
        item = {
            "term": str(value.get("term") or value.get("preferred_form") or "term"),
            "preferred_form": str(value.get("preferred_form") or value.get("term") or "term"),
            "definition": value.get("definition"),
            "aliases": list(value.get("aliases", [])),
        }
    if not any(existing.get("term") == item["term"] for existing in contract["glossary"]):
        contract["glossary"].append(item)


def apply_contract_patches(contract: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    """把结构化 review patch 直接应用到 contract payload 上。"""
    if not patches:
        return contract

    contract["version"] = int(contract.get("version", 1)) + 1

    for patch in [ContractPatch.model_validate(item) for item in patches]:
        if patch.patch_type == "append_glossary":
            _append_glossary(contract, patch.value)

        elif patch.patch_type == "set_section_status":
            for section in contract["sections"]:
                if section["section_id"] == patch.target_id:
                    section["status"] = str(patch.value)
                    break

        elif patch.patch_type == "add_required_citation":
            for section in contract["sections"]:
                if section["section_id"] == patch.target_id:
                    citation_id = str(patch.value)
                    if citation_id not in section["required_citation_ids"]:
                        section["required_citation_ids"].append(citation_id)
                        section["citation_obligations"].append(
                            {
                                "citation_id": citation_id,
                                "required": True,
                                "purpose": "Added by review feedback",
                                "grounded_claim_ids": list(section.get("required_claim_ids", [])),
                            }
                        )
                    break

        elif patch.patch_type == "add_required_visual":
            for section in contract["sections"]:
                if section["section_id"] == patch.target_id:
                    artifact_id = str(patch.value)
                    if artifact_id not in section["required_visual_ids"]:
                        section["required_visual_ids"].append(artifact_id)
                        section["visual_obligations"].append(
                            {
                                "artifact_id": artifact_id,
                                "required": True,
                                "explanation_required": True,
                                "placement_hint": section["section_id"],
                            }
                        )
                    break

        elif patch.patch_type == "add_required_evidence":
            for section in contract["sections"]:
                if section["section_id"] == patch.target_id:
                    evidence_id = str(patch.value)
                    if evidence_id not in section["required_evidence_ids"]:
                        section["required_evidence_ids"].append(evidence_id)
                    break

        elif patch.patch_type == "mark_claim_verified":
            for claim in contract["claim_evidence_links"]:
                if claim["claim_id"] == patch.target_id or claim["claim_text"] == patch.target_id:
                    claim["verified"] = bool(patch.value) if isinstance(patch.value, bool) else str(patch.value).lower() in {"true", "verified"}
                    break
            for section in contract["sections"]:
                for requirement in section.get("claim_requirements", []):
                    if requirement["claim_id"] == patch.target_id or requirement["claim_text"] == patch.target_id:
                        requirement["coverage_status"] = "verified"

        elif patch.patch_type == "update_visual_placement":
            for artifact in contract["visuals"]:
                if artifact["artifact_id"] == patch.target_id and isinstance(patch.value, dict):
                    if patch.value.get("placement_hint") is not None:
                        artifact["placement_hint"] = patch.value["placement_hint"]
                    if patch.value.get("placement_constraint") is not None:
                        artifact["placement_constraint"] = patch.value["placement_constraint"]
                    break

        elif patch.patch_type == "require_visual_explanation":
            for artifact in contract["visuals"]:
                if artifact["artifact_id"] == patch.target_id:
                    artifact["explanation_required"] = True
                    break

        elif patch.patch_type == "add_validation_rule":
            if isinstance(patch.value, dict):
                contract["validation_rules"].append(
                    ValidationRule.model_validate(patch.value).model_dump(mode="json")
                )

        elif patch.patch_type == "tighten_validation_rule":
            for rule in contract["validation_rules"]:
                if rule["rule_id"] == patch.target_id and isinstance(patch.value, dict):
                    rule["severity"] = patch.value.get("severity", rule["severity"])
                    rule["params"] = {**rule.get("params", {}), **patch.value.get("params", {})}
                    break

        elif patch.patch_type == "add_section_dependency":
            for section in contract["sections"]:
                if section["section_id"] == patch.target_id:
                    dependency = str(patch.value)
                    if dependency not in section["depends_on_sections"]:
                        section["depends_on_sections"].append(dependency)
                    break

        elif patch.patch_type == "register_revision_note":
            contract.setdefault("global_status", {}).setdefault("warnings", []).append(str(patch.value))

        elif patch.patch_type == "ground_citation_to_claim":
            if isinstance(patch.value, dict):
                claim_id = str(patch.value.get("claim_id", ""))
                for citation in contract["citations"]:
                    if citation["citation_id"] == patch.target_id and claim_id and claim_id not in citation["grounded_claim_ids"]:
                        citation["grounded_claim_ids"].append(claim_id)
                        break

    return contract


def snapshot_contract(context: dict[str, Any]) -> dict[str, Any] | None:
    """返回当前 contract 的一份脱离引用的拷贝。"""
    contract = context.get("contract")
    if contract is None:
        return None
    return deepcopy(contract)
