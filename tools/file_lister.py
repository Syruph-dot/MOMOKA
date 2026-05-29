from agents import function_tool
from tools.path_utils import resolve_path


@function_tool
def list_files(directory: str = ".") -> str:
    """列出会话工作目录内指定子目录中的文件和子目录。
    参数 directory: 目录的相对路径（基于会话工作目录），默认为当前目录。"""
    try:
        p = resolve_path(directory)
    except ValueError as e:
        return f"错误：{e}"
    if not p.exists():
        return f"错误：目录 '{directory}' 不存在。"
    if not p.is_dir():
        return f"错误：'{directory}' 不是目录。"
    try:
        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = []
        for item in items:
            suffix = "/" if item.is_dir() else ""
            size = ""
            if item.is_file():
                try:
                    size = f" ({item.stat().st_size} B)"
                except OSError:
                    pass
            lines.append(f"  {item.name}{suffix}{size}")
        header = f"目录 '{directory}' 包含 {len(lines)} 个项目："
        return header + "\n" + "\n".join(lines)
    except Exception as e:
        return f"错误：列出目录失败 — {e}"
