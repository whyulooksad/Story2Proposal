from __future__ import annotations

"""单次 Story2Proposal run 的子进程入口。

这个文件负责在独立子进程中执行一次完整 run，并在失败时写出错误日志。
"""

import argparse
import json
import traceback
from datetime import datetime
from pathlib import Path

from backend.runner import run_story_to_proposal_sync
from backend.schemas import ResearchStory


def _write_json(path: Path, payload: object) -> None:
    """把对象写成格式化 JSON 文件。"""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    """解析参数并执行一次单次 run。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--story", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    story = ResearchStory.from_path(Path(args.story))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)

    try:
        run_story_to_proposal_sync(story, output_dir=output_dir, model=args.model)
        return 0
    except Exception as exc:  # pragma: no cover
        _write_json(
            output_dir / "logs" / "error.json",
            {
                "message": str(exc),
                "traceback": traceback.format_exc(),
                "failed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
