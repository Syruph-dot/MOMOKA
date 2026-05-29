from pathlib import Path
from agents import function_tool


@function_tool
def append_file(path: str, content: str) -> str:
    """向指定文本文件追加内容（不覆盖原有内容）。参数 path: 文件路径，content: 要追加的内容。"""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        action = "追加写入" if existed else "创建并写入"
        size = len(content.encode("utf-8"))
        return f"{action}成功：'{path}' (+{size} 字节)"
    except Exception as e:
        return f"错误：追加写入失败 — {e}"
