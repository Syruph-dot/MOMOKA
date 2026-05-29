from agents import function_tool
from tools.path_utils import resolve_path


@function_tool
def read_file(path: str) -> str:
    """读取会话工作目录内的文本文件。参数 path: 文件的相对路径（基于会话工作目录）。"""
    try:
        p = resolve_path(path)
    except ValueError as e:
        return f"错误：{e}"
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
