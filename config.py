from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = PACKAGE_ROOT / "prompts"
DATA_DIR = PACKAGE_ROOT / "data"
STORIES_DIR = DATA_DIR / "stories"
OUTPUTS_DIR = DATA_DIR / "outputs"


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8").strip()
