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
def write_file(path: str, content: str) -> str:
    """将内容写入指定文本文件（覆盖模式）。参数 path: 文件路径，content: 要写入的内容。"""
    p = _resolve_path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
        action = "覆盖写入" if existed else "创建写入"
        size = len(content.encode("utf-8"))
        return f"{action}成功：'{path}' ({size} 字节)"
    except Exception as e:
        return f"错误：写入文件失败 — {e}"
