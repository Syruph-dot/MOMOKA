"""
测试 tools/path_utils.py — 路径解析与容器检查。
"""

import os
import tempfile
from pathlib import Path
import pytest

from momoka.config import current_work_dir
from tools.path_utils import resolve_path


@pytest.fixture
def work_dir():
    """创建临时目录作为工作目录，并在测试前后设置/重置 ContextVar。"""
    with tempfile.TemporaryDirectory() as tmp:
        token = current_work_dir.set(tmp)
        yield Path(tmp).resolve()
        current_work_dir.reset(token)


class TestResolvePath:
    """resolve_path 的基础功能测试。"""

    def test_relative_path_allowed(self, work_dir):
        """相对路径应该被允许，解析为 work_dir + path。"""
        result = resolve_path("file.txt")
        assert result == work_dir / "file.txt"

    def test_relative_subdir_allowed(self, work_dir):
        """子目录相对路径应该被允许。"""
        result = resolve_path("sub/dir/file.txt")
        assert result == work_dir / "sub/dir/file.txt"

    def test_current_dir_resolves_to_workdir(self, work_dir):
        """'.' 应该解析为 work_dir 本身。"""
        result = resolve_path(".")
        assert result == work_dir

    def test_absolute_path_inside_workdir_allowed(self, work_dir):
        """工作目录内的绝对路径应该被允许。"""
        file_path = work_dir / "nested" / "file.txt"
        result = resolve_path(str(file_path))
        assert result == file_path

    def test_dotdot_traversal_denied(self, work_dir):
        """'..' 路径遍历应该被拒绝。"""
        with pytest.raises(ValueError, match="超出了工作目录"):
            resolve_path("../outside.txt")

    def test_deep_dotdot_traversal_denied(self, work_dir):
        """深层 '..' 路径遍历应该被拒绝。"""
        with pytest.raises(ValueError, match="超出了工作目录"):
            resolve_path("a/../../../../etc/passwd")

    def test_absolute_path_outside_workdir_denied(self, work_dir):
        """工作目录外的绝对路径应该被拒绝。"""
        # 使用系统临时目录（必定在工作目录外）
        outside = tempfile.gettempdir()
        outside_file = os.path.join(outside, "some_file.txt")
        with pytest.raises(ValueError, match="超出了工作目录"):
            resolve_path(outside_file)

    def test_no_workdir_raises_error(self):
        """未设置工作目录时应该报错。"""
        # 确保 ContextVar 是 None
        token = current_work_dir.set(None)
        try:
            with pytest.raises(ValueError, match="未设置会话工作目录"):
                resolve_path("file.txt")
        finally:
            current_work_dir.reset(token)

    def test_no_workdir_absolute_path_also_denied(self):
        """未设置工作目录时，绝对路径也应该报错。"""
        token = current_work_dir.set(None)
        try:
            with pytest.raises(ValueError, match="未设置会话工作目录"):
                resolve_path("C:\\Windows\\win.ini")
        finally:
            current_work_dir.reset(token)

    @pytest.mark.skipif(os.name != "nt", reason="仅 Windows 测试大小写不敏感")
    def test_case_insensitivity_windows(self, work_dir):
        """Windows 上大小写不同的路径应该被允许。"""
        # Create an actual file/dir so resolve() works
        target = work_dir / "TestDir"
        target.mkdir(exist_ok=True)
        # 大小写不同的路径
        result = resolve_path(str(work_dir / "testdir"))
        assert result == target

    def test_existing_subdirectory_inside(self, work_dir):
        """对 work_dir 内已存在于文件系统的目录做 resolve。"""
        sub = work_dir / "subdir"
        sub.mkdir(exist_ok=True)
        result = resolve_path(str(sub))
        assert result == sub

    def test_dotdot_via_subdirectory_escapes_denied(self, work_dir):
        """通过子目录后多层 '..' 跳出 work_dir 应该被拒绝。"""
        sub = work_dir / "subdir"
        sub.mkdir(exist_ok=True)
        with pytest.raises(ValueError, match="超出了工作目录"):
            resolve_path("subdir/../../etc/passwd")


class TestIsSubpath:
    """_is_subpath 内部函数的间接测试（通过 resolve_path 验证）。"""

    def test_symlink_outside_denied(self, work_dir):
        """work_dir 内的符号链接指向外部时，应该被拒绝。"""
        outside = Path(tempfile.mkdtemp())
        try:
            outside_file = outside / "target.txt"
            outside_file.write_text("secret")
            link = work_dir / "link_to_outside"
            try:
                link.symlink_to(outside_file, target_is_directory=False)
            except (OSError, AttributeError):
                pytest.skip("创建符号链接失败（可能需要管理员权限）")

            with pytest.raises(ValueError, match="超出了工作目录"):
                resolve_path("link_to_outside")
        finally:
            import shutil
            shutil.rmtree(outside, ignore_errors=True)
            if link.exists():
                link.unlink()
