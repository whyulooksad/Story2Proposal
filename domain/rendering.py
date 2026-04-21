from __future__ import annotations

from typing import Any

from schemas import RenderedManuscript


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


def render_markdown_manuscript(context: dict[str, Any]) -> RenderedManuscript:
    contract = context.get("contract") or {}
    drafts = context.get("drafts") or {}
    sections = []
    warnings: list[str] = []
    title = (
        contract.get("paper_title")
        or context.get("story", {}).get("title_hint")
        or "Untitled Manuscript"
    )
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
            content = (
                f"{content}\n\n> Refiner note: "
                f"{refiner_output['section_notes'][section['section_id']]}"
            )
        sections.append(f"## {draft['title']}\n\n{content}")
    bibliography = build_bibliography_block(context)
    if bibliography:
        sections.append("## References\n\n" + bibliography)
    markdown = "\n\n".join(sections).strip() + "\n"
    latex = render_latex_from_markdown(
        title,
        contract.get("sections", []),
        drafts,
        bibliography,
        abstract_override,
    )
    return RenderedManuscript(markdown=markdown, latex=latex, warnings=warnings)
