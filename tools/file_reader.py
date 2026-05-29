from pathlib import Path
from agents import function_tool
from momoka.config import current_work_dir


def _resolve_path(path: str) -> Path:
    """解析路径：相对路径基于会话工作目录，绝对路径直接使用。"""
    p = Path(path)
    if p.is_absolute():
        return p
    base = current_work_dir.get()
    if base:
        return Path(base) / p
    return p


@function_tool
def read_file(path: str) -> str:
    """读取指定文本文件的内容。参数 path: 文件路径（相对于工作目录或绝对路径）。"""
    p = _resolve_path(path)
    if not p.exists():
        return f"错误：文件 '{path}' 不存在。"
    if p.is_dir():
        return f"错误：'{path}' 是一个目录，请指定文件路径。"
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"错误：'{path}' 不是有效的文本文件，无法读取。"
    except Exception as e:
        return f"错误：读取文件失败 — {e}"
