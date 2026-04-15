"""核心引擎模块

提供对话引擎、上下文管理、工具执行、命令沙箱等核心功能。
"""

from by19code.core.sandbox import (
    run_command,
    run_command_sync,
    CommandResult,
    CommandExecutionError,
    CommandBlockedError,
    CommandTimeoutError,
    CommandPathError,
)
from by19code.core.tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    get_tool_definitions,
    get_tool_by_name,
)

__all__ = [
    # 命令沙箱
    "run_command",
    "run_command_sync",
    "CommandResult",
    "CommandExecutionError",
    "CommandBlockedError",
    "CommandTimeoutError",
    "CommandPathError",
    # 工具系统
    "TOOL_DEFINITIONS",
    "execute_tool",
    "get_tool_definitions",
    "get_tool_by_name",
]

# TODO: T11 实现对话引擎
# TODO: T12 实现上下文管理器
