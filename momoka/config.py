"""
MOMOKA 全局配置 — 项目路径与常量定义。
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("MOMOKA_ROOT", Path(__file__).resolve().parent.parent))

PROMPTS_DIR = PROJECT_ROOT / "prompts"
SKILLS_DIR = PROJECT_ROOT / "skills"
MEMORY_DIR = PROJECT_ROOT / "memory"
STATIC_DIR = PROJECT_ROOT / "static"
LOGS_DIR = PROJECT_ROOT / "logs"

# 批注式判断量表
LIKERT_LABELS = {
    1: "强烈反对",
    2: "反对",
    3: "不太赞同",
    4: "中立",
    5: "有点赞同",
    6: "赞同",
    7: "强烈赞同",
}
