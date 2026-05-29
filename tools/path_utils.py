"""
MOMOKA 路径解析工具 — 共享的路径解析 + 容器检查。

所有文件工具通过此模块解析路径，确保操作不会超出会话工作目录。
"""

import os
from pathlib import Path

from momoka.config import current_work_dir


def _is_subpath(child: Path, parent: Path) -> bool:
    """检查 child 是否是 parent 的子路径（含相等），大小写不敏感。"""
    child_norm = os.path.normcase(str(child))
    parent_norm = os.path.normcase(str(parent))
    return child_norm == parent_norm or child_norm.startswith(parent_norm + os.sep)


def resolve_path(path: str) -> Path:
    """解析并验证路径是否在会话工作目录内。

    参数:
        path: 用户输入的路径字符串（相对或绝对）

    返回:
        Path: 已解析并验证通过的绝对路径

    抛出:
        ValueError: 如果没有设置工作目录，或路径超出工作目录范围
    """
    base = current_work_dir.get()
    if base is None:
        raise ValueError("未设置会话工作目录，文件操作已被禁用。")

    work_dir = Path(base).resolve(strict=True)  # 确保目录存在
    input_path = Path(path)

    # 相对路径拼接到 work_dir; 绝对路径直接用
    if input_path.is_absolute():
        resolved = input_path.resolve()
    else:
        resolved = (work_dir / input_path).resolve()

    # 容器检查
    if not _is_subpath(resolved, work_dir):
        raise ValueError(
            f"路径 '{path}' 超出了工作目录 '{work_dir}' 的范围，已拒绝访问。"
        )

    return resolved
