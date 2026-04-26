from __future__ import annotations

"""Story2Proposal 的视觉产物物化与完整性检查。

这个模块负责把章节草稿中登记的 visual artifact 规范化为输出目录里的真实文件，并在评审阶段检查这些产物是否完整可用。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend.schemas.draft import VisualArtifactMaterialization


@dataclass(frozen=True)
class VisualArtifactContext:
    """视觉产物处理阶段共享的上下文。"""
    output_dir: Path


@dataclass(frozen=True)
class VisualArtifactFiles:
    """一个视觉产物可能涉及的源文件与渲染文件集合。"""
    source_file: Path | None
    rendered_file: Path | None
    thumbnail_file: Path | None


Renderer = Callable[[VisualArtifactContext, VisualArtifactMaterialization, VisualArtifactFiles], VisualArtifactMaterialization]


def normalize_svg_markup(svg_text: str) -> str:
    """把 SVG 标记归一化为可直接展示的独立文档。"""
    normalized = svg_text.lstrip("\ufeff").strip()
    if not normalized.startswith("<svg"):
        return normalized
    head, sep, tail = normalized.partition(">")
    if sep and "xmlns=" not in head:
        head = f'{head} xmlns="http://www.w3.org/2000/svg"'
    if sep and "xmlns:xlink=" not in head:
        head = f'{head} xmlns:xlink="http://www.w3.org/1999/xlink"'
    return f"{head}{sep}{tail}" if sep else normalized


def _resolve_within_output_dir(context: VisualArtifactContext, path_value: str | None) -> Path | None:
    """把路径解析为 output_dir 内的绝对路径。"""
    if not path_value:
        return None
    candidate = Path(path_value)
    resolved = candidate.resolve() if candidate.is_absolute() else (context.output_dir / candidate).resolve()
    try:
        resolved.relative_to(context.output_dir)
    except ValueError as exc:
        raise ValueError(f"Artifact path escapes output_dir: {path_value}") from exc
    return resolved


def _to_relative_output_path(context: VisualArtifactContext, path: Path | None) -> str | None:
    """把绝对路径转换成相对 output_dir 的存储路径。"""
    if path is None:
        return None
    return path.resolve().relative_to(context.output_dir).as_posix()


def _resolve_files(context: VisualArtifactContext, artifact: VisualArtifactMaterialization) -> VisualArtifactFiles:
    """解析一个视觉产物关联的所有文件路径。"""
    return VisualArtifactFiles(
        source_file=_resolve_within_output_dir(context, artifact.source_path),
        rendered_file=_resolve_within_output_dir(context, artifact.rendered_path),
        thumbnail_file=_resolve_within_output_dir(context, artifact.thumbnail_path),
    )


def _require_existing_file(path: Path | None, *, label: str, artifact_id: str) -> Path:
    """确保指定文件存在，否则抛出带 artifact_id 的错误。"""
    if path is None:
        raise ValueError(f"{artifact_id}: missing {label} path")
    if not path.exists() or not path.is_file():
        raise ValueError(f"{artifact_id}: missing {label} file at {path}")
    return path


def _render_drawio_artifact(
    context: VisualArtifactContext,
    artifact: VisualArtifactMaterialization,
    files: VisualArtifactFiles,
) -> VisualArtifactMaterialization:
    """把 draw.io 产物规范化并写入最终渲染目录。"""
    source_candidate = files.source_file or files.rendered_file
    source_file = _require_existing_file(source_candidate, label="drawio source", artifact_id=artifact.artifact_id)

    rendered_dir = context.output_dir / "rendered" / "visuals"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    rendered_file = rendered_dir / f"{artifact.artifact_id}.svg"
    rendered_file.write_text(
        normalize_svg_markup(source_file.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    return artifact.model_copy(
        update={
            "source_path": _to_relative_output_path(context, source_file),
            "rendered_path": _to_relative_output_path(context, rendered_file),
            "thumbnail_path": _to_relative_output_path(context, rendered_file),
        },
        deep=True,
    )


def _passthrough_artifact(
    context: VisualArtifactContext,
    artifact: VisualArtifactMaterialization,
    files: VisualArtifactFiles,
) -> VisualArtifactMaterialization:
    """直接复用已有文件路径的通用物化逻辑。"""
    rendered_file = files.rendered_file or files.source_file
    rendered_file = _require_existing_file(rendered_file, label="rendered", artifact_id=artifact.artifact_id)
    source_file = files.source_file if files.source_file and files.source_file.exists() else rendered_file
    thumbnail_file = files.thumbnail_file if files.thumbnail_file and files.thumbnail_file.exists() else rendered_file
    return artifact.model_copy(
        update={
            "source_path": _to_relative_output_path(context, source_file),
            "rendered_path": _to_relative_output_path(context, rendered_file),
            "thumbnail_path": _to_relative_output_path(context, thumbnail_file),
        },
        deep=True,
    )


RENDERERS: dict[str, Renderer] = {
    "drawio": _render_drawio_artifact,
}


def materialize_visual_artifact(output_dir: Path, artifact: VisualArtifactMaterialization) -> VisualArtifactMaterialization:
    """物化单个视觉产物。"""
    context = VisualArtifactContext(output_dir=output_dir.resolve())
    files = _resolve_files(context, artifact)
    renderer = RENDERERS.get(artifact.generator.lower(), _passthrough_artifact)
    return renderer(context, artifact, files)


def materialize_visual_artifacts(
    output_dir: Path,
    artifacts: list[VisualArtifactMaterialization],
) -> list[VisualArtifactMaterialization]:
    """批量物化多个视觉产物。"""
    return [materialize_visual_artifact(output_dir, artifact) for artifact in artifacts]


def validate_visual_artifact_integrity(output_dir: Path, artifacts: list[dict[str, object]]) -> list[str]:
    """检查视觉产物 payload 和关联文件是否完整。"""
    context = VisualArtifactContext(output_dir=output_dir.resolve())
    issues: list[str] = []
    for payload in artifacts:
        artifact_id = str(payload.get("artifact_id") or "unknown_artifact")
        try:
            artifact = VisualArtifactMaterialization.model_validate(payload)
            files = _resolve_files(context, artifact)
            rendered_file = files.rendered_file or files.source_file
            _require_existing_file(rendered_file, label="rendered", artifact_id=artifact_id)
        except Exception as exc:
            issues.append(f"Invalid visual artifact payload for {artifact_id}: {exc}")
    return issues
