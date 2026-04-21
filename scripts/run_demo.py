from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from config import STORIES_DIR
from runner import run_story_to_proposal
from schemas import ResearchStory


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--story",
        default=str(STORIES_DIR / "sample_story.json"),
        help="Path to a ResearchStory JSON file.",
    )
    parser.add_argument("--model", default="qwen-plus")
    args = parser.parse_args()

    story = ResearchStory.from_path(Path(args.story))
    result = await run_story_to_proposal(story, model=args.model)
    print(result["summary"])


if __name__ == "__main__":
    asyncio.run(main())
