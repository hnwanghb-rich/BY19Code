"""BY19Code 文件操作模块单元测试【T08】

测试覆盖
--------
1. 正常文件读写操作
2. 文件编辑（查找替换）
3. 目录列表（树形结构）
4. 文件内容搜索
5. 路径安全检查（防止路径穿越攻击）
6. Windows 平台特性（盘符大小写）
"""
import pytest
import tempfile
from pathlib import Path

from by19code.file_ops.operations import (
    read_file,
    write_file,
    edit_file,
    list_directory,
    search_files,
    PathSecurityError,
    FileNotFoundError,
    FileReadError,
    FileWriteError,
)


@pytest.fixture
def temp_project():
    """创建临时项目目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        yield project_root


class TestReadFile:
    """测试 read_file 函数"""

    def test_read_existing_file(self, temp_project):
        """测试读取存在的文件"""
        # 创建测试文件
        test_file = temp_project / "test.txt"
        test_content = "Hello, BY19Code!\n测试中文内容"
        test_file.write_text(test_content, encoding="utf-8")

        # 读取文件
        content = read_file(test_file, temp_project)
        assert content == test_content

    def test_read_nonexistent_file(self, temp_project):
        """测试读取不存在的文件"""
        with pytest.raises(FileNotFoundError):
            read_file(temp_project / "nonexistent.txt", temp_project)

    def test_read_directory(self, temp_project):
        """测试读取目录（应该失败）"""
        subdir = temp_project / "subdir"
        subdir.mkdir()

        with pytest.raises(FileReadError):
            read_file(subdir, temp_project)

    def test_read_with_relative_path(self, temp_project):
        """测试使用相对路径读取文件"""
        test_file = temp_project / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        # 使用相对路径
        content = read_file("test.txt", temp_project)
        assert content == "content"


class TestWriteFile:
    """测试 write_file 函数"""

    def test_write_new_file(self, temp_project):
        """测试创建新文件"""
        test_file = temp_project / "new.txt"
        test_content = "新文件内容\nLine 2"

        result = write_file(test_file, test_content, temp_project)
        assert "成功" in result

        # 验证文件内容
        assert test_file.read_text(encoding="utf-8") == test_content

    def test_write_overwrite_file(self, temp_project):
        """测试覆盖已存在的文件"""
        test_file = temp_project / "existing.txt"
        test_file.write_text("old content", encoding="utf-8")

        new_content = "new content"
        write_file(test_file, new_content, temp_project)

        assert test_file.read_text(encoding="utf-8") == new_content

    def test_write_with_auto_create_parent(self, temp_project):
        """测试自动创建父目录"""
        test_file = temp_project / "subdir" / "nested" / "file.txt"
        content = "nested file"

        write_file(test_file, content, temp_project)

        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == content

    def test_write_utf8_encoding(self, temp_project):
        """测试 UTF-8 编码"""
        test_file = temp_project / "utf8.txt"
        content = "中文测试 🎉 Emoji"

        write_file(test_file, content, temp_project)

        assert test_file.read_text(encoding="utf-8") == content


class TestEditFile:
    """测试 edit_file 函数"""

    def test_edit_simple_replace(self, temp_project):
        """测试简单文本替换"""
        test_file = temp_project / "edit.txt"
        original = "Hello World\nHello Python"
        test_file.write_text(original, encoding="utf-8")

        result = edit_file(test_file, "Hello", "Hi", temp_project)
        assert "替换 2 处" in result

        content = test_file.read_text(encoding="utf-8")
        assert content == "Hi World\nHi Python"

    def test_edit_not_found(self, temp_project):
        """测试替换不存在的文本"""
        test_file = temp_project / "edit.txt"
        test_file.write_text("content", encoding="utf-8")

        result = edit_file(test_file, "notfound", "replacement", temp_project)
        assert "未找到" in result

    def test_edit_multiline(self, temp_project):
        """测试多行文本替换"""
        test_file = temp_project / "multiline.txt"
        original = "Line 1\nLine 2\nLine 3"
        test_file.write_text(original, encoding="utf-8")

        edit_file(test_file, "Line 2\nLine 3", "New Line", temp_project)

        content = test_file.read_text(encoding="utf-8")
        assert content == "Line 1\nNew Line"


class TestListDirectory:
    """测试 list_directory 函数"""

    def test_list_simple_directory(self, temp_project):
        """测试列出简单目录结构"""
        # 创建测试结构
        (temp_project / "file1.txt").touch()
        (temp_project / "file2.py").touch()
        (temp_project / "subdir").mkdir()
        (temp_project / "subdir" / "nested.txt").touch()

        result = list_directory(temp_project, temp_project, depth=2)

        assert "file1.txt" in result
        assert "file2.py" in result
        assert "subdir" in result
        assert "nested.txt" in result

    def test_list_with_ignored_dirs(self, temp_project):
        """测试忽略特定目录"""
        # 创建测试结构
        (temp_project / "normal.txt").touch()
        (temp_project / "__pycache__").mkdir()
        (temp_project / "__pycache__" / "cache.pyc").touch()
        (temp_project / ".git").mkdir()
        (temp_project / ".git" / "config").touch()

        result = list_directory(temp_project, temp_project, depth=2)

        assert "normal.txt" in result
        assert "__pycache__" not in result
        assert ".git" not in result

    def test_list_depth_limit(self, temp_project):
        """测试深度限制"""
        # 创建深层嵌套结构
        deep_dir = temp_project / "level1" / "level2" / "level3"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.txt").touch()

        # 深度为 1，不应该看到 level2
        result = list_directory(temp_project, temp_project, depth=1)
        assert "level1" in result
        assert "level2" not in result

    def test_list_nonexistent_directory(self, temp_project):
        """测试列出不存在的目录"""
        with pytest.raises(FileNotFoundError):
            list_directory(temp_project / "nonexistent", temp_project)


class TestSearchFiles:
    """测试 search_files 函数"""

    def test_search_simple_pattern(self, temp_project):
        """测试简单文本搜索"""
        # 创建测试文件
        (temp_project / "file1.txt").write_text("Hello World", encoding="utf-8")
        (temp_project / "file2.txt").write_text("Goodbye World", encoding="utf-8")
        (temp_project / "file3.txt").write_text("No match here", encoding="utf-8")

        result = search_files("World", temp_project, temp_project)

        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "file3.txt" not in result
        assert "2 个文件" in result

    def test_search_regex_pattern(self, temp_project):
        """测试正则表达式搜索"""
        (temp_project / "test.py").write_text("def hello():\n    pass", encoding="utf-8")
        (temp_project / "test.txt").write_text("hello world", encoding="utf-8")

        result = search_files(r"def\s+\w+", temp_project, temp_project)

        assert "test.py" in result
        assert "test.txt" not in result

    def test_search_case_insensitive(self, temp_project):
        """测试大小写不敏感搜索"""
        (temp_project / "test.txt").write_text("Hello WORLD", encoding="utf-8")

        result = search_files("hello", temp_project, temp_project)
        assert "test.txt" in result

    def test_search_no_matches(self, temp_project):
        """测试无匹配结果"""
        (temp_project / "test.txt").write_text("content", encoding="utf-8")

        result = search_files("notfound", temp_project, temp_project)
        assert "未找到" in result

    def test_search_ignores_binary_files(self, temp_project):
        """测试忽略二进制文件"""
        # 创建文本文件和二进制文件
        (temp_project / "text.txt").write_text("searchme", encoding="utf-8")
        (temp_project / "binary.pyc").write_bytes(b"\x00\x01\x02")

        result = search_files("searchme", temp_project, temp_project)

        assert "text.txt" in result
        assert "binary.pyc" not in result


class TestPathSecurity:
    """测试路径安全检查（防止路径穿越攻击）"""

    def test_path_traversal_parent_dir(self, temp_project):
        """测试路径穿越攻击：使用 ../"""
        with pytest.raises(PathSecurityError):
            read_file("../../../etc/passwd", temp_project)

    def test_path_traversal_absolute_path(self, temp_project):
        """测试路径穿越攻击：使用绝对路径"""
        with pytest.raises(PathSecurityError):
            read_file("C:\\Windows\\System32\\drivers\\etc\\hosts", temp_project)

    def test_path_traversal_windows_path(self, temp_project):
        """测试路径穿越攻击：Windows 路径"""
        with pytest.raises(PathSecurityError):
            read_file("C:\\Users\\Administrator\\Desktop\\secret.txt", temp_project)

    def test_path_traversal_mixed_separators(self, temp_project):
        """测试路径穿越攻击：混合路径分隔符"""
        with pytest.raises(PathSecurityError):
            read_file("..\\..\\..\\Windows\\System32", temp_project)

    def test_valid_relative_path(self, temp_project):
        """测试合法的相对路径"""
        # 创建子目录和文件
        subdir = temp_project / "subdir"
        subdir.mkdir()
        test_file = subdir / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        # 使用相对路径读取（应该成功）
        content = read_file("subdir/test.txt", temp_project)
        assert content == "content"

    def test_valid_absolute_path_in_project(self, temp_project):
        """测试项目内的绝对路径（应该允许）"""
        test_file = temp_project / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        # 使用绝对路径读取（在项目范围内）
        content = read_file(test_file, temp_project)
        assert content == "content"


class TestWindowsCompatibility:
    """测试 Windows 平台兼容性"""

    def test_path_with_backslashes(self, temp_project):
        """测试反斜杠路径"""
        subdir = temp_project / "subdir"
        subdir.mkdir()
        test_file = subdir / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        # 使用反斜杠路径（Windows 风格）
        content = read_file("subdir\\test.txt", temp_project)
        assert content == "content"

    def test_mixed_path_separators(self, temp_project):
        """测试混合路径分隔符"""
        deep_dir = temp_project / "level1" / "level2"
        deep_dir.mkdir(parents=True)
        test_file = deep_dir / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        # 混合使用 / 和 \
        content = read_file("level1/level2\\test.txt", temp_project)
        assert content == "content"

    def test_unicode_filename(self, temp_project):
        """测试 Unicode 文件名"""
        test_file = temp_project / "测试文件.txt"
        test_content = "中文内容"
        test_file.write_text(test_content, encoding="utf-8")

        content = read_file(test_file, temp_project)
        assert content == test_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
