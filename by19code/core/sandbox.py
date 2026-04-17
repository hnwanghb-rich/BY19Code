"""BY19Code 命令执行沙箱【T09】

提供安全的命令执行功能，包括：
- 黑名单过滤（防止危险命令）
- 超时控制
- 路径限制
- 输出捕获

Windows 平台特性
----------------
- shell=True 默认通过 cmd.exe /c 执行
- 编码统一使用 UTF-8
- 支持 PowerShell 和 cmd.exe 命令
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from by19code.config.settings import SafetyConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class CommandResult:
    """命令执行结果"""

    command: str
    returncode: int
    stdout: str
    stderr: str
    success: bool
    error_message: Optional[str] = None

    @property
    def output(self) -> str:
        """合并 stdout 和 stderr"""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)


class CommandExecutionError(Exception):
    """命令执行异常基类"""
    pass


class CommandBlockedError(CommandExecutionError):
    """命令被黑名单拦截异常"""
    pass


class CommandTimeoutError(CommandExecutionError):
    """命令执行超时异常"""
    pass


class CommandPathError(CommandExecutionError):
    """命令路径不合法异常"""
    pass


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _is_command_blocked(command: str, blocked_commands: list[str]) -> tuple[bool, Optional[str]]:
    """检查命令是否在黑名单中。

    参数
    ----
    command          : 待执行的命令
    blocked_commands : 黑名单列表

    返回
    ----
    (is_blocked, matched_pattern) : 是否被拦截，匹配的黑名单模式
    """
    command_lower = command.lower().strip()

    for blocked in blocked_commands:
        blocked_lower = blocked.lower().strip()

        # 精确匹配或包含匹配
        if blocked_lower in command_lower:
            logger.warning("[沙箱] 命令被黑名单拦截: %s (匹配: %s)", command, blocked)
            return True, blocked

    return False, None


def _validate_cwd(cwd: str | Path, project_root: str | Path) -> Path:
    """验证工作目录是否在项目范围内。

    参数
    ----
    cwd          : 工作目录
    project_root : 项目根目录

    返回
    ----
    Path : 解析后的工作目录

    异常
    ----
    CommandPathError : 工作目录不在项目范围内
    """
    try:
        cwd_path = Path(cwd).resolve()
        root_path = Path(project_root).resolve()

        # 检查是否在项目范围内
        try:
            cwd_path.relative_to(root_path)
        except ValueError:
            raise CommandPathError(
                f"工作目录 '{cwd}' 不在项目根目录 '{project_root}' 范围内"
            )

        return cwd_path

    except CommandPathError:
        raise
    except Exception as e:
        raise CommandPathError(f"工作目录验证失败: {e}") from e


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


async def run_command(
    command: str,
    cwd: str | Path,
    config: SafetyConfig,
    project_root: Optional[str | Path] = None,
) -> CommandResult:
    """在沙箱环境中执行命令。

    参数
    ----
    command      : 要执行的命令
    cwd          : 工作目录
    config       : 安全配置（超时、黑名单等）
    project_root : 项目根目录（用于路径验证，可选）

    返回
    ----
    CommandResult : 命令执行结果

    异常
    ----
    CommandBlockedError  : 命令被黑名单拦截
    CommandTimeoutError  : 命令执行超时
    CommandPathError     : 工作目录不合法
    CommandExecutionError: 其他执行错误

    安全机制
    --------
    1. 黑名单过滤：拦截危险命令（format、shutdown 等）
    2. 超时控制：防止命令无限执行
    3. 路径限制：工作目录必须在项目范围内（如果指定 project_root）
    4. 输出捕获：捕获 stdout 和 stderr
    """
    # 1. 黑名单检查
    is_blocked, matched_pattern = _is_command_blocked(command, config.blocked_commands)
    if is_blocked:
        raise CommandBlockedError(
            f"命令被安全策略拦截: '{command}' (匹配黑名单: '{matched_pattern}')"
        )

    # 2. 路径验证（如果指定了 project_root）
    if project_root is not None:
        cwd_path = _validate_cwd(cwd, project_root)
    else:
        cwd_path = Path(cwd).resolve()

    # 确保工作目录存在
    if not cwd_path.exists():
        raise CommandPathError(f"工作目录不存在: {cwd_path}")

    logger.info("[沙箱] 执行命令: %s (工作目录: %s)", command, cwd_path)

    # 3. 执行命令
    try:
        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(
                command,
                shell=True,
                cwd=str(cwd_path),
                capture_output=True,
                encoding="utf-8",
                timeout=config.command_timeout_seconds,
                errors="replace",
            )

        try:
            proc = await asyncio.to_thread(_run)
        except asyncio.TimeoutError:
            raise CommandTimeoutError(
                f"命令执行超时（{config.command_timeout_seconds}秒）: {command}"
            )

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        returncode = proc.returncode
        success = (returncode == 0)
        error_message = None if success else f"命令返回非零退出码: {returncode}"

        result = CommandResult(
            command=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            success=success,
            error_message=error_message,
        )

        logger.info(
            "[沙箱] 命令执行完成: returncode=%d, stdout=%d字符, stderr=%d字符",
            returncode, len(stdout), len(stderr),
        )

        return result

    except (CommandBlockedError, CommandTimeoutError, CommandPathError):
        raise
    except Exception as e:
        logger.error("[沙箱] 命令执行失败: %s", e)
        raise CommandExecutionError(f"命令执行失败: {e}") from e


def run_command_sync(
    command: str,
    cwd: str | Path,
    config: SafetyConfig,
    project_root: Optional[str | Path] = None,
) -> CommandResult:
    """同步版本的 run_command（用于非异步上下文）。

    参数和返回值与 run_command 相同。
    """
    # 1. 黑名单检查
    is_blocked, matched_pattern = _is_command_blocked(command, config.blocked_commands)
    if is_blocked:
        raise CommandBlockedError(
            f"命令被安全策略拦截: '{command}' (匹配黑名单: '{matched_pattern}')"
        )

    # 2. 路径验证
    if project_root is not None:
        cwd_path = _validate_cwd(cwd, project_root)
    else:
        cwd_path = Path(cwd).resolve()

    if not cwd_path.exists():
        raise CommandPathError(f"工作目录不存在: {cwd_path}")

    logger.info("[沙箱] 执行命令（同步）: %s (工作目录: %s)", command, cwd_path)

    # 3. 执行命令（同步）
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd_path),
            capture_output=True,
            encoding="utf-8",
            timeout=config.command_timeout_seconds,
            errors="replace",  # 处理编码错误
        )

        success = (result.returncode == 0)
        error_message = None if success else f"命令返回非零退出码: {result.returncode}"

        cmd_result = CommandResult(
            command=command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            success=success,
            error_message=error_message,
        )

        logger.info(
            "[沙箱] 命令执行完成（同步）: returncode=%d, stdout=%d字符, stderr=%d字符",
            result.returncode, len(result.stdout), len(result.stderr),
        )

        return cmd_result

    except subprocess.TimeoutExpired:
        raise CommandTimeoutError(
            f"命令执行超时（{config.command_timeout_seconds}秒）: {command}"
        )
    except (CommandBlockedError, CommandPathError):
        raise
    except Exception as e:
        logger.error("[沙箱] 命令执行失败（同步）: %s", e)
        raise CommandExecutionError(f"命令执行失败: {e}") from e
