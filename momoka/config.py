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


def load_local_env(project_root: Path = PROJECT_ROOT) -> bool:
    """Load `.env` from the project root without overriding existing variables."""
    env_path = Path(project_root) / ".env"
    if not env_path.exists():
        return False

    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    load_dotenv(env_path, override=False)
    return True

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
