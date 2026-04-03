from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

class Skill(BaseModel):
    """One goal-level skill spec that defines execution instructions and tool visibility."""

    name: str
    domain: str | None = None
    description: str | None = None
    instructions: str | None = None
    visible_mcp_servers: list[str] = Field(
        default_factory=list, alias="visibleMcpServers"
    )
    tool_names: list[str] = Field(default_factory=list, alias="toolNames")
    inherit_domain_to_children: bool = True
    inherit_visible_mcp_servers_to_children: bool = True
    inherit_tool_scope_to_children: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    def for_child(self) -> "Skill":
        """Return the boundary-only skill view inherited by a dynamic child agent."""
        return Skill(
            name=self.name,
            domain=self.domain if self.inherit_domain_to_children else None,
            description=self.description,
            instructions=None,
            visible_mcp_servers=(
                self.visible_mcp_servers
                if self.inherit_visible_mcp_servers_to_children
                else []
            ),
            tool_names=self.tool_names if self.inherit_tool_scope_to_children else [],
            inherit_domain_to_children=self.inherit_domain_to_children,
            inherit_visible_mcp_servers_to_children=self.inherit_visible_mcp_servers_to_children,
            inherit_tool_scope_to_children=self.inherit_tool_scope_to_children,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_dir(cls, path: str | Path) -> "Skill":
        skill_dir = Path(path)
        tool_policy_path = skill_dir / "tool_policy.json"
        if not tool_policy_path.exists():
            raise FileNotFoundError(
                f"Missing required skill policy file: {tool_policy_path}"
            )
        payload: dict[str, Any] = json.loads(tool_policy_path.read_text(encoding="utf-8"))

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"Missing required skill spec file: {skill_md}")
        payload["instructions"] = skill_md.read_text(encoding="utf-8")

        payload.setdefault("name", skill_dir.name)
        return cls.model_validate(payload)


class SkillManifest(BaseModel):
    """One catalog entry that introduces an available skill to an agent."""

    name: str
    purpose: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillCatalog(BaseModel):
    """Catalog of skills available to one capability-domain agent."""

    agent_name: str
    overview: str = ""
    skills: list[SkillManifest] = Field(default_factory=list)

    @property
    def skill_names(self) -> list[str]:
        return [skill.name for skill in self.skills]


class SkillLoader:
    """Filesystem skill loader with per-agent skill catalogs."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def _resolve_agent_dir(self, agent_name: str | None = None) -> Path:
        """Resolve either a skills root or an already-scoped agent skill directory."""
        if agent_name is None:
            return self.base_dir
        return self.base_dir / agent_name

    def load_catalog(self, agent_name: str | None = None) -> SkillCatalog:
        agent_dir = self._resolve_agent_dir(agent_name)
        resolved_agent_name = agent_name or agent_dir.name
        overview_path = agent_dir / "skill.md"
        overview = (
            overview_path.read_text(encoding="utf-8") if overview_path.exists() else ""
        )
        catalog_path = agent_dir / "catalog.json"
        manifests: list[SkillManifest] = []

        if catalog_path.exists():
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            manifests = [
                SkillManifest.model_validate(item)
                for item in payload.get("skills", [])
            ]
        elif overview.strip():
            manifests = self._parse_catalog_from_markdown(overview)
        else:
            raise FileNotFoundError(
                f"Missing required skill catalog for agent `{resolved_agent_name}`. "
                f"Expected `{overview_path.name}` or `{catalog_path.name}` in {agent_dir}."
            )

        return SkillCatalog(
            agent_name=resolved_agent_name,
            overview=overview,
            skills=manifests,
        )

    def load(self, skill_name: str, agent_name: str | None = None) -> Skill:
        return Skill.from_dir(self._resolve_agent_dir(agent_name) / skill_name)

    def _parse_catalog_from_markdown(self, content: str) -> list[SkillManifest]:
        manifests: list[SkillManifest] = []
        for line in content.splitlines():
            match = re.match(
                r"^\s*[-*]\s+([A-Za-z][A-Za-z0-9_/-]*)\s*:\s*(.+?)\s*$",
                line,
            )
            if not match:
                continue
            manifests.append(
                SkillManifest(
                    name=match.group(1).strip(),
                    purpose=match.group(2).strip(),
                )
            )
        return manifests
