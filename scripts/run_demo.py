from __future__ import annotations

"""Story2Proposal 的命令行 demo 入口。

这个文件只负责命令行参数解析、加载输入 story，并把运行委托给
`runner.py`。它是 CLI 外壳，不承载应用本体逻辑。
"""

import argparse
import asyncio
from pathlib import Path

from config import DEFAULT_MODEL, STORIES_DIR
from runner import run_story_to_proposal
from schemas import ResearchStory


async def main() -> None:
    """解析命令行参数并运行一次 demo。"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--story",
        default=str(STORIES_DIR / "sample_story.json"),
        help="Path to a ResearchStory JSON file.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    story = ResearchStory.from_path(Path(args.story))
    # 具体的 graph 构建、context 初始化和产物落盘都在 runner 里完成。
    result = await run_story_to_proposal(story, model=args.model)
    print(result["summary"])


if __name__ == "__main__":
    """直接从命令行启动 demo。"""
    asyncio.run(main())
