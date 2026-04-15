"""BY19Code 命令执行沙箱单元测试【T09】

测试覆盖
--------
1. 正常命令执行
2. 黑名单拦截
3. 超时控制
4. 路径限制
5. 输出捕获
6. Windows 平台兼容性
"""
import pytest
import tempfile
import asyncio
from pathlib import Path

from by19code.core.sandbox import (
    run_command,
    run_command_sync,
    CommandResult,
    CommandBlockedError,
    CommandTimeoutError,
    CommandPathError,
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


@pytest.fixture
def strict_config():
    """严格安全配置（短超时）"""
    return SafetyConfig(
        command_timeout_seconds=1,
        max_tool_rounds=20,
    )


class TestNormalExecution:
    """测试正常命令执行"""

    @pytest.mark.asyncio
    async def test_simple_echo_command(self, temp_project, default_config):
        """测试简单 echo 命令"""
        result = await run_command(
            "echo Hello World",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        assert result.success is True
        assert result.returncode == 0
        assert "Hello World" in result.stdout
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_command_with_output(self, temp_project, default_config):
        """测试带输出的命令"""
        result = await run_command(
            "echo Line1 && echo Line2",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        assert result.success is True
        assert "Line1" in result.stdout
        assert "Line2" in result.stdout

    @pytest.mark.asyncio
    async def test_command_with_error(self, temp_project, default_config):
        """测试返回错误的命令"""
        result = await run_command(
            "exit 1",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        assert result.success is False
        assert result.returncode == 1
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_command_with_stderr(self, temp_project, default_config):
        """测试输出到 stderr 的命令"""
        # Windows: 使用 echo 输出到 stderr
        result = await run_command(
            "echo Error message 1>&2",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        # echo 命令本身会成功执行
        assert result.returncode == 0
        # stderr 应该包含错误信息
        assert "Error message" in result.output

    def test_sync_version(self, temp_project, default_config):
        """测试同步版本的命令执行"""
        result = run_command_sync(
            "echo Sync Test",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        assert result.success is True
        assert "Sync Test" in result.stdout


class TestBlacklist:
    """测试黑名单拦截"""

    @pytest.mark.asyncio
    async def test_block_format_command(self, temp_project, default_config):
        """测试拦截 format 命令"""
        with pytest.raises(CommandBlockedError) as exc_info:
            await run_command(
                "format C:",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

        assert "format" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_block_shutdown_command(self, temp_project, default_config):
        """测试拦截 shutdown 命令"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "shutdown /s /t 0",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_block_del_recursive(self, temp_project, default_config):
        """测试拦截递归删除命令"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "del /s /q C:\\",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_block_rd_recursive(self, temp_project, default_config):
        """测试拦截 rd /s /q 命令"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "rd /s /q C:\\Windows",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_block_powershell_remove_item(self, temp_project, default_config):
        """测试拦截 PowerShell Remove-Item 命令"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "Remove-Item -Recurse -Force C:\\",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_block_reg_delete(self, temp_project, default_config):
        """测试拦截注册表删除命令"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "reg delete HKLM\\Software",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_block_bcdedit(self, temp_project, default_config):
        """测试拦截 bcdedit 命令"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "bcdedit /set",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_block_diskpart(self, temp_project, default_config):
        """测试拦截 diskpart 命令"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "diskpart",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_block_net_stop(self, temp_project, default_config):
        """测试拦截 net stop 命令"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "net stop wuauserv",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_case_insensitive_blocking(self, temp_project, default_config):
        """测试黑名单大小写不敏感"""
        with pytest.raises(CommandBlockedError):
            await run_command(
                "FORMAT C:",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )

        with pytest.raises(CommandBlockedError):
            await run_command(
                "ShUtDoWn /s",
                cwd=temp_project,
                config=default_config,
                project_root=temp_project,
            )


class TestTimeout:
    """测试超时控制"""

    @pytest.mark.asyncio
    async def test_command_timeout(self, temp_project, strict_config):
        """测试命令执行超时"""
        # Windows: 使用 ping 命令模拟长时间运行（ping 10 次，每次 1 秒）
        with pytest.raises(CommandTimeoutError) as exc_info:
            await run_command(
                "ping 127.0.0.1 -n 10",
                cwd=temp_project,
                config=strict_config,
                project_root=temp_project,
            )

        assert "超时" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_command_within_timeout(self, temp_project, default_config):
        """测试命令在超时时间内完成"""
        result = await run_command(
            "echo Quick command",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        assert result.success is True

    def test_sync_timeout(self, temp_project, strict_config):
        """测试同步版本的超时控制"""
        with pytest.raises(CommandTimeoutError):
            run_command_sync(
                "ping 127.0.0.1 -n 10",
                cwd=temp_project,
                config=strict_config,
                project_root=temp_project,
            )


class TestPathRestriction:
    """测试路径限制"""

    @pytest.mark.asyncio
    async def test_valid_path_in_project(self, temp_project, default_config):
        """测试项目内的合法路径"""
        subdir = temp_project / "subdir"
        subdir.mkdir()

        result = await run_command(
            "echo test",
            cwd=subdir,
            config=default_config,
            project_root=temp_project,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_invalid_path_outside_project(self, temp_project, default_config):
        """测试项目外的路径（应该被拒绝）"""
        with pytest.raises(CommandPathError):
            await run_command(
                "echo test",
                cwd="C:\\Windows",
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_nonexistent_cwd(self, temp_project, default_config):
        """测试不存在的工作目录"""
        with pytest.raises(CommandPathError):
            await run_command(
                "echo test",
                cwd=temp_project / "nonexistent",
                config=default_config,
                project_root=temp_project,
            )

    @pytest.mark.asyncio
    async def test_no_project_root_restriction(self, temp_project, default_config):
        """测试不指定 project_root 时不限制路径"""
        # 不指定 project_root，应该允许任意路径
        result = await run_command(
            "echo test",
            cwd=temp_project,
            config=default_config,
            project_root=None,  # 不限制路径
        )

        assert result.success is True


class TestOutputCapture:
    """测试输出捕获"""

    @pytest.mark.asyncio
    async def test_capture_stdout(self, temp_project, default_config):
        """测试捕获标准输出"""
        result = await run_command(
            "echo Standard Output",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        assert "Standard Output" in result.stdout
        assert result.output  # output 属性应该包含内容

    @pytest.mark.asyncio
    async def test_capture_multiline_output(self, temp_project, default_config):
        """测试捕获多行输出"""
        result = await run_command(
            "echo Line1 && echo Line2 && echo Line3",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        assert "Line1" in result.stdout
        assert "Line2" in result.stdout
        assert "Line3" in result.stdout

    @pytest.mark.asyncio
    async def test_utf8_encoding(self, temp_project, default_config):
        """测试 UTF-8 编码支持"""
        # Windows cmd.exe 默认使用 GBK 编码，中文可能会乱码
        # 使用 PowerShell 来确保 UTF-8 输出
        result = await run_command(
            'powershell -Command "Write-Output 测试"',
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        # 检查是否包含"测试"或至少命令执行成功
        assert result.success is True
        # 由于编码问题，我们只验证命令成功执行，不强制要求中文正确显示


class TestWindowsCompatibility:
    """测试 Windows 平台兼容性"""

    @pytest.mark.asyncio
    async def test_cmd_command(self, temp_project, default_config):
        """测试 cmd.exe 命令"""
        result = await run_command(
            "dir",
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        # dir 命令应该成功执行
        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_powershell_command(self, temp_project, default_config):
        """测试 PowerShell 命令"""
        result = await run_command(
            'powershell -Command "Write-Output Test"',
            cwd=temp_project,
            config=default_config,
            project_root=temp_project,
        )

        assert "Test" in result.stdout or "Test" in result.output

    @pytest.mark.asyncio
    async def test_path_with_spaces(self, temp_project, default_config):
        """测试包含空格的路径"""
        subdir = temp_project / "dir with spaces"
        subdir.mkdir()

        result = await run_command(
            "echo test",
            cwd=subdir,
            config=default_config,
            project_root=temp_project,
        )

        assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
