from pathlib import Path
from agents import function_tool


@function_tool
def write_file(path: str, content: str) -> str:
    """将内容写入指定文本文件（覆盖模式）。参数 path: 文件路径，content: 要写入的内容。"""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
        action = "覆盖写入" if existed else "创建写入"
        size = len(content.encode("utf-8"))
        return f"{action}成功：'{path}' ({size} 字节)"
    except Exception as e:
        return f"错误：写入文件失败 — {e}"
