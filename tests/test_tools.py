"""BY19Code 工具定义与执行单元测试【T10】

测试覆盖
--------
1. 工具定义完整性
2. 工具执行分发
3. 格式转换（Claude/OpenAI）
4. 参数验证
5. 错误处理
"""
import pytest
import tempfile
from pathlib import Path

from by19code.core.tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    get_tool_definitions,
    get_tool_by_name,
)
from by19code.config.settings import SafetyConfig


@pytest.fixture
def temp_project():
    """创建临时项目目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        yield project_root


@pytest.fixture
def default_config():
    """默认安全配置"""
    return SafetyConfig(
        command_timeout_seconds=5,
        max_tool_rounds=20,
    )


class TestToolDefinitions:
    """测试工具定义"""

    def test_tool_definitions_exist(self):
        """测试工具定义列表存在"""
        assert len(TOOL_DEFINITIONS) > 0

    def test_all_tools_have_required_fields(self):
        """测试所有工具都有必需字段"""
        for tool in TOOL_DEFINITIONS:
            assert tool.name
            assert tool.description
            assert tool.parameters
            assert "type" in tool.parameters
            assert "properties" in tool.parameters

    def test_file_operation_tools_defined(self):
        """测试文件操作工具已定义"""
        tool_names = [t.name for t in TOOL_DEFINITIONS]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "edit_file" in tool_names
        assert "list_directory" in tool_names

    def test_command_tool_defined(self):
        """测试命令执行工具已定义"""
        tool_names = [t.name for t in TOOL_DEFINITIONS]
        assert "run_command" in tool_names

    def test_git_tools_defined(self):
        """测试 Git 工具已定义（占位）"""
        tool_names = [t.name for t in TOOL_DEFINITIONS]
        assert "git_commit" in tool_names
        assert "git_diff" in tool_names
        assert "git_log" in tool_names
        assert "git_status" in tool_names
        assert "git_create_branch" in tool_names

    def test_tool_parameters_valid_json_schema(self):
        """测试工具参数是有效的 JSON Schema"""
        for tool in TOOL_DEFINITIONS:
            params = tool.parameters
            assert params["type"] == "object"
            assert isinstance(params["properties"], dict)
            assert isinstance(params.get("required", []), list)


class TestGetToolByName:
    """测试根据名称获取工具"""

    def test_get_existing_tool(self):
        """测试获取存在的工具"""
        tool = get_tool_by_name("read_file")
        assert tool is not None
        assert tool.name == "read_file"

    def test_get_nonexistent_tool(self):
        """测试获取不存在的工具"""
        tool = get_tool_by_name("nonexistent_tool")
        assert tool is None


class TestGetToolDefinitions:
    """测试工具定义格式转换"""

    def test_claude_format(self):
        """测试 Claude 格式"""
        tools = get_tool_definitions(format="claude")

        assert len(tools) > 0
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "type" not in tool  # Claude 格式没有 type 字段

    def test_openai_format(self):
        """测试 OpenAI 格式"""
        tools = get_tool_definitions(format="openai")

        assert len(tools) > 0
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_invalid_format(self):
        """测试无效格式"""
        with pytest.raises(ValueError):
            get_tool_definitions(format="invalid")


class TestExecuteToolReadFile:
    """测试 read_file 工具执行"""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, temp_project, default_config):
        """测试读取存在的文件"""
        # 创建测试文件
        test_file = temp_project / "test.txt"
        test_file.write_text("Hello World", encoding="utf-8")

        result = await execute_tool(
            tool_name="read_file",
            arguments={"path": "test.txt"},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[文件] 读取成功" in result
        assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, temp_project, default_config):
        """测试读取不存在的文件"""
        result = await execute_tool(
            tool_name="read_file",
            arguments={"path": "nonexistent.txt"},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[错误]" in result

    @pytest.mark.asyncio
    async def test_read_file_missing_path(self, temp_project, default_config):
        """测试缺少 path 参数"""
        result = await execute_tool(
            tool_name="read_file",
            arguments={},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[错误]" in result
        assert "path" in result


class TestExecuteToolWriteFile:
    """测试 write_file 工具执行"""

    @pytest.mark.asyncio
    async def test_write_new_file(self, temp_project, default_config):
        """测试创建新文件"""
        result = await execute_tool(
            tool_name="write_file",
            arguments={"path": "new.txt", "content": "New content"},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[文件]" in result
        assert "成功" in result

        # 验证文件已创建
        test_file = temp_project / "new.txt"
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "New content"

    @pytest.mark.asyncio
    async def test_write_file_missing_params(self, temp_project, default_config):
        """测试缺少必需参数"""
        # 缺少 path
        result = await execute_tool(
            tool_name="write_file",
            arguments={"content": "test"},
            project_root=str(temp_project),
            config=default_config,
        )
        assert "[错误]" in result

        # 缺少 content
        result = await execute_tool(
            tool_name="write_file",
            arguments={"path": "test.txt"},
            project_root=str(temp_project),
            config=default_config,
        )
        assert "[错误]" in result


class TestExecuteToolEditFile:
    """测试 edit_file 工具执行"""

    @pytest.mark.asyncio
    async def test_edit_file_success(self, temp_project, default_config):
        """测试成功编辑文件"""
        # 创建测试文件
        test_file = temp_project / "edit.txt"
        test_file.write_text("Hello World", encoding="utf-8")

        result = await execute_tool(
            tool_name="edit_file",
            arguments={"path": "edit.txt", "old_text": "World", "new_text": "Python"},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[文件]" in result
        assert "成功" in result

        # 验证文件已修改
        assert test_file.read_text(encoding="utf-8") == "Hello Python"

    @pytest.mark.asyncio
    async def test_edit_file_missing_params(self, temp_project, default_config):
        """测试缺少必需参数"""
        result = await execute_tool(
            tool_name="edit_file",
            arguments={"path": "test.txt"},
            project_root=str(temp_project),
            config=default_config,
        )
        assert "[错误]" in result


class TestExecuteToolListDirectory:
    """测试 list_directory 工具执行"""

    @pytest.mark.asyncio
    async def test_list_directory_default(self, temp_project, default_config):
        """测试列出目录（默认参数）"""
        # 创建测试文件
        (temp_project / "file1.txt").touch()
        (temp_project / "file2.py").touch()

        result = await execute_tool(
            tool_name="list_directory",
            arguments={},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[文件] 目录结构" in result
        assert "file1.txt" in result
        assert "file2.py" in result

    @pytest.mark.asyncio
    async def test_list_directory_with_depth(self, temp_project, default_config):
        """测试指定深度"""
        result = await execute_tool(
            tool_name="list_directory",
            arguments={"path": ".", "depth": 1},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[文件] 目录结构" in result


class TestExecuteToolRunCommand:
    """测试 run_command 工具执行"""

    @pytest.mark.asyncio
    async def test_run_simple_command(self, temp_project, default_config):
        """测试执行简单命令"""
        result = await execute_tool(
            tool_name="run_command",
            arguments={"command": "echo Hello"},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[命令] 执行" in result
        assert "Hello" in result

    @pytest.mark.asyncio
    async def test_run_command_missing_param(self, temp_project, default_config):
        """测试缺少 command 参数"""
        result = await execute_tool(
            tool_name="run_command",
            arguments={},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[错误]" in result
        assert "command" in result


class TestExecuteToolGitPlaceholder:
    """测试 Git 工具占位"""

    @pytest.mark.asyncio
    async def test_git_tools_return_todo(self, temp_project, default_config):
        """测试 Git 工具返回 TODO 提示"""
        git_tools = ["git_commit", "git_diff", "git_log", "git_status", "git_create_branch"]

        for tool_name in git_tools:
            result = await execute_tool(
                tool_name=tool_name,
                arguments={},
                project_root=str(temp_project),
                config=default_config,
            )

            assert "[提示]" in result
            assert "T14" in result


class TestExecuteToolUnknown:
    """测试未知工具"""

    @pytest.mark.asyncio
    async def test_unknown_tool(self, temp_project, default_config):
        """测试执行未知工具"""
        result = await execute_tool(
            tool_name="unknown_tool",
            arguments={},
            project_root=str(temp_project),
            config=default_config,
        )

        assert "[错误]" in result
        assert "未知工具" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
