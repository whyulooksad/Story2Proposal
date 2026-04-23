from __future__ import annotations

"""Story2Proposal 应用层的路径与静态配置入口。"""

import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = PACKAGE_ROOT / "prompts"
DATA_DIR = PACKAGE_ROOT / "data"
STORIES_DIR = DATA_DIR / "stories"
OUTPUTS_DIR = DATA_DIR / "outputs"

# 统一在配置层加载 `.env`，避免模型名散落在不同入口里各自写死。
load_dotenv(PACKAGE_ROOT / ".env")

DEFAULT_MODEL = os.getenv("STORY2PROPOSAL_MODEL", "qwen-plus")


def load_prompt(name: str) -> str:
    """按文件名读取一个 prompt 模板。"""
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8").strip()
