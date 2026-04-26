from __future__ import annotations

"""Story2Proposal 的最终渲染与确定性校验。

这个模块把前面阶段收敛好的结构化产物装配成最终 manuscript。
"""

import re
from typing import Any

from backend.schemas import FinalizedSection, RenderedManuscript

from .validation import validate_render_output


def _get_writing_language(context: dict[str, Any]) -> str:
    """读取最终稿件的目标语言。"""
    story = context.get("story") or {}
    metadata = story.get("metadata") or {}
    language = metadata.get("writing_language")
    return language if language in {"en", "zh"} else "en"


def _references_heading(language: str) -> str:
    """返回参考文献章节标题。"""
    return "参考文献" if language == "zh" else "References"


def _unknown_authors_label(language: str) -> str:
    """返回作者缺失时的兜底文案。"""
    return "未知作者" if language == "zh" else "Unknown"


def _unknown_year_label(language: str) -> str:
    """返回年份缺失时的兜底文案。"""
    return "未知年份" if language == "zh" else "n.d."


def build_bibliography_block(context: dict[str, Any]) -> str:
    """把 contract 里的 citation slot 渲染成 markdown 参考文献列表。"""
    contract = context.get("contract") or {}
    language = _get_writing_language(context)
    lines = []
    for item in contract.get("citations", []):
        authors = ", ".join(item.get("authors", [])) or _unknown_authors_label(language)
        year = item.get("year") or _unknown_year_label(language)
        venue = f". {item['venue']}" if item.get("venue") else ""
        lines.append(f"- [{item['citation_key']}] {authors} ({year}). {item['title']}{venue}.")
    return "\n".join(lines)


def _apply_terminology_updates(content: str, terminology_updates: dict[str, str]) -> tuple[str, bool]:
    """把 refiner 给出的术语统一映射应用到 section 文本。"""
    normalized = content
    changed = False
    replacements = sorted(
        (
            (source, target)
            for source, target in terminology_updates.items()
            if source and target and source != target
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for source, target in replacements:
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", re.IGNORECASE)
        updated = pattern.sub(target, normalized)
        updated = updated.replace(source, target)
        if updated != normalized:
            changed = True
            normalized = updated
    return normalized, changed


def _rewrite_lookup(refiner_output: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按 section_id 建立 refiner 全局重写索引。"""
    rewrites = refiner_output.get("section_rewrites", [])
    return {
        item["section_id"]: item
        for item in rewrites
        if item.get("section_id") and item.get("rewritten_content")
    }


def build_finalized_sections(context: dict[str, Any]) -> tuple[list[FinalizedSection], list[str]]:
    """构造 markdown / LaTeX 共享的最终 section 真相源。"""
    contract = context.get("contract") or {}
    drafts = context.get("drafts") or {}
    refiner_output = context.get("artifacts", {}).get("refiner_output", {})
    abstract_override = context.get("artifacts", {}).get("abstract_override")
    warnings: list[str] = []
    finalized_sections: list[FinalizedSection] = []

    terminology_updates = refiner_output.get("terminology_updates", {})
    rewrite_map = _rewrite_lookup(refiner_output)

    for section in contract.get("sections", []):
        draft = drafts.get(section["section_id"])
        if draft is None:
            warnings.append(f"Missing draft for section {section['section_id']}")
            continue

        notes_applied: list[str] = []
        title = draft["title"]
        content = draft["content"]

        if section["section_id"] == "abstract" and abstract_override:
            content = abstract_override
            notes_applied.append("abstract_override")

        rewrite = rewrite_map.get(section["section_id"])
        if rewrite:
            title = rewrite.get("title") or title
            content = rewrite["rewritten_content"]
            notes_applied.append("section_rewrite")

        content, terminology_changed = _apply_terminology_updates(content, terminology_updates)
        if terminology_changed:
            notes_applied.append("terminology_update")

        finalized_sections.append(
            FinalizedSection(
                section_id=section["section_id"],
                title=title,
                content=content,
                notes_applied=notes_applied,
            )
        )

    return finalized_sections, warnings


def render_latex_from_sections(
    title: str,
    sections: list[FinalizedSection],
    bibliography: str,
    writing_language: str,
) -> str:
    """根据最终 section 真相源构造稳定的 LaTeX scaffold。"""
    body: list[str] = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\begin{document}",
        rf"\title{{{title}}}",
        r"\maketitle",
    ]
    for section in sections:
        body.append(rf"\section{{{section.title}}}")
        body.append(section.content.replace("_", r"\_"))
    if bibliography:
        body.append(rf"\section{{{_references_heading(writing_language)}}}")
        body.append(bibliography.replace("_", r"\_"))
    body.append(r"\end{document}")
    return "\n".join(body) + "\n"


def render_markdown_manuscript(context: dict[str, Any]) -> RenderedManuscript:
    """组装最终 markdown 稿件及其对应的 LaTeX 版本。"""
    contract = context.get("contract") or {}
    writing_language = _get_writing_language(context)
    title = contract.get("paper_title") or context.get("story", {}).get("title_hint") or "Untitled Manuscript"
    finalized_sections, warnings = build_finalized_sections(context)

    markdown_blocks = [f"# {title}"]
    for section in finalized_sections:
        markdown_blocks.append(f"## {section.title}\n\n{section.content}")

    bibliography = build_bibliography_block(context)
    if bibliography:
        markdown_blocks.append(f"## {_references_heading(writing_language)}\n\n{bibliography}")

    markdown = "\n\n".join(markdown_blocks).strip() + "\n"
    latex = render_latex_from_sections(title, finalized_sections, bibliography, writing_language)
    rendered_sections = [section.model_dump(mode="json") for section in finalized_sections]
    validation = validate_render_output(contract, rendered_sections, bibliography)
    warnings.extend(validation.warnings)
    return RenderedManuscript(
        markdown=markdown,
        latex=latex,
        finalized_sections=finalized_sections,
        validation=validation,
        warnings=warnings,
    )
