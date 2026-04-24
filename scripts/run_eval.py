from __future__ import annotations

"""对已有 Story2Proposal run 目录执行评测与 benchmark 重算。"""

import argparse
import json
from pathlib import Path

from domain import evaluate_manuscript_bundle


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_context(run_dir: Path) -> dict:
    context = {
        "story": _read_json(run_dir / "input_story.json"),
        "contract": _read_json(run_dir / "contract_final.json"),
        "drafts": {},
        "artifacts": {},
    }

    for draft_path in sorted((run_dir / "drafts").glob("*_v*.md")):
        section_id = draft_path.stem.split("_v", maxsplit=1)[0]
        context["drafts"][section_id] = {
            "section_id": section_id,
            "title": section_id,
            "content": draft_path.read_text(encoding="utf-8"),
            "story_traces": [],
            "evidence_traces": [],
            "covered_claim_ids": [],
            "referenced_visual_ids": [],
            "referenced_citation_ids": [],
            "terminology_used": [],
            "unresolved_items": [],
        }

    rendered_path = run_dir / "rendered" / "final_manuscript.md"
    validation_path = run_dir / "logs" / "run_summary.json"
    if rendered_path.exists():
        context["artifacts"]["rendered"] = {
            "markdown": rendered_path.read_text(encoding="utf-8"),
            "finalized_sections": [],
            "validation": _read_json(validation_path).get("render_validation", {}) if validation_path.exists() else {},
        }

    return context


def _write_single_run_outputs(run_dir: Path) -> tuple[Path, Path, float]:
    context = _build_context(run_dir)
    evaluation, benchmark = evaluate_manuscript_bundle(context)

    evaluation_path = run_dir / "logs" / "evaluation_recomputed.json"
    benchmark_path = run_dir / "logs" / "benchmark_recomputed.json"
    evaluation_path.write_text(evaluation.model_dump_json(indent=2), encoding="utf-8")
    benchmark_path.write_text(benchmark.model_dump_json(indent=2), encoding="utf-8")
    return evaluation_path, benchmark_path, evaluation.overall_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", help="Path to an existing run output directory.")
    parser.add_argument("--runs-root", help="Path to a directory that contains multiple run output directories.")
    args = parser.parse_args()

    if bool(args.run_dir) == bool(args.runs_root):
        raise SystemExit("Provide exactly one of --run-dir or --runs-root.")

    if args.run_dir:
        evaluation_path, benchmark_path, _ = _write_single_run_outputs(Path(args.run_dir))
        print(evaluation_path)
        print(benchmark_path)
        return

    runs_root = Path(args.runs_root)
    leaderboard: list[dict[str, str | float]] = []
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        if not (run_dir / "input_story.json").exists():
            continue
        _, _, score = _write_single_run_outputs(run_dir)
        leaderboard.append({"run_id": run_dir.name, "overall_score": score})

    leaderboard.sort(key=lambda item: item["overall_score"], reverse=True)
    aggregate_path = runs_root / "benchmark_leaderboard.json"
    aggregate_path.write_text(json.dumps(leaderboard, ensure_ascii=False, indent=2), encoding="utf-8")
    print(aggregate_path)


if __name__ == "__main__":
    main()
