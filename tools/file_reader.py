from pathlib import Path
from agents import function_tool


@function_tool
def read_file(path: str) -> str:
    """读取指定文本文件的内容。参数 path: 文件路径（相对于当前目录或绝对路径）。"""
    p = Path(path)
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
