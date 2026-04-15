"""BY19Code 工具定义与执行【T10】

提供工具注册表和执行分发功能。

工具类型
--------
1. 文件操作：read_file, write_file, edit_file, list_directory
2. 命令执行：run_command
3. Git 操作：git_commit, git_diff, git_log, git_status, git_create_branch（T14 实现）

工具格式
--------
- Claude 格式：{ "name", "description", "input_schema" }
- OpenAI 格式：{ "type": "function", "function": { "name", "description", "parameters" } }
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from by19code.llm.base import ToolDefinition
from by19code.file_ops.operations import (
    read_file,
    write_file,
    edit_file,
    list_directory,
)
from by19code.core.sandbox import run_command
from by19code.config.settings import SafetyConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具注册表
# ---------------------------------------------------------------------------


TOOL_DEFINITIONS: list[ToolDefinition] = [
    # ===== 文件操作工具 =====
    ToolDefinition(
        name="read_file",
        description="读取指定文件的内容。用于查看文件内容、检查代码等。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）",
                }
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="write_file",
        description="创建或覆盖写入文件。用于创建新文件或完全替换文件内容。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）",
                },
                "content": {
                    "type": "string",
                    "description": "文件内容",
                },
            },
            "required": ["path", "content"],
        },
    ),
    ToolDefinition(
        name="edit_file",
        description="查找并替换文件中的指定文本。用于修改文件的部分内容。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）",
                },
                "old_text": {
                    "type": "string",
                    "description": "要替换的文本",
                },
                "new_text": {
                    "type": "string",
                    "description": "替换后的文本",
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    ),
    ToolDefinition(
        name="list_directory",
        description="列出目录结构（树形格式）。用于查看项目文件组织。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径（相对于项目根目录，默认为当前目录）",
                    "default": ".",
                },
                "depth": {
                    "type": "integer",
                    "description": "递归深度（默认 2）",
                    "default": 2,
                },
            },
            "required": [],
        },
    ),
    # ===== 命令执行工具 =====
    ToolDefinition(
        name="run_command",
        description="在项目目录下执行 shell 命令（Windows cmd.exe 或 PowerShell）。用于运行测试、安装依赖、执行脚本等。",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令",
                }
            },
            "required": ["command"],
        },
    ),
    # ===== Git 操作工具（T14 实现）=====
    ToolDefinition(
        name="git_commit",
        description="提交当前更改到 Git 仓库。用于保存代码修改。",
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "提交信息",
                }
            },
            "required": ["message"],
        },
    ),
    ToolDefinition(
        name="git_diff",
        description="查看当前工作区的修改内容。用于检查未提交的更改。",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    ToolDefinition(
        name="git_log",
        description="查看 Git 提交历史。用于了解项目的修改记录。",
        parameters={
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "显示的提交数量（默认 10）",
                    "default": 10,
                }
            },
            "required": [],
        },
    ),
    ToolDefinition(
        name="git_status",
        description="查看 Git 仓库状态。用于了解哪些文件被修改、添加或删除。",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    ToolDefinition(
        name="git_create_branch",
        description="创建新的 Git 分支。用于开始新功能开发或修复 bug。",
        parameters={
            "type": "object",
            "properties": {
                "branch_name": {
                    "type": "string",
                    "description": "分支名称",
                }
            },
            "required": ["branch_name"],
        },
    ),
]


# ---------------------------------------------------------------------------
# 工具执行分发
# ---------------------------------------------------------------------------


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    project_root: str,
    config: SafetyConfig,
) -> str:
    """执行指定的工具。

    参数
    ----
    tool_name    : 工具名称
    arguments    : 工具参数（字典）
    project_root : 项目根目录
    config       : 安全配置

    返回
    ----
    str : 工具执行结果（成功消息或错误信息）

    异常处理
    --------
    所有异常都会被捕获并转换为友好的错误信息字符串返回。
    """
    logger.info("[工具] 执行: %s, 参数: %s", tool_name, arguments)

    try:
        # ===== 文件操作工具 =====
        if tool_name == "read_file":
            path = arguments.get("path")
            if not path:
                return "[错误] 缺少必需参数: path"

            try:
                content = read_file(path, project_root)
                logger.info("[工具] read_file 成功: %s (%d 字符)", path, len(content))
                return f"[文件] 读取成功: {path}\n\n{content}"
            except Exception as e:
                return f"[错误] 读取文件失败: {e}"

        elif tool_name == "write_file":
            path = arguments.get("path")
            content = arguments.get("content")

            if not path:
                return "[错误] 缺少必需参数: path"
            if content is None:
                return "[错误] 缺少必需参数: content"

            try:
                result = write_file(path, content, project_root)
                logger.info("[工具] write_file 成功: %s", path)
                return f"[文件] {result}"
            except Exception as e:
                return f"[错误] 写入文件失败: {e}"

        elif tool_name == "edit_file":
            path = arguments.get("path")
            old_text = arguments.get("old_text")
            new_text = arguments.get("new_text")

            if not path:
                return "[错误] 缺少必需参数: path"
            if old_text is None:
                return "[错误] 缺少必需参数: old_text"
            if new_text is None:
                return "[错误] 缺少必需参数: new_text"

            try:
                result = edit_file(path, old_text, new_text, project_root)
                logger.info("[工具] edit_file 成功: %s", path)
                return f"[文件] {result}"
            except Exception as e:
                return f"[错误] 编辑文件失败: {e}"

        elif tool_name == "list_directory":
            path = arguments.get("path", ".")
            depth = arguments.get("depth", 2)

            try:
                result = list_directory(path, project_root, depth)
                logger.info("[工具] list_directory 成功: %s (深度 %d)", path, depth)
                return f"[文件] 目录结构:\n\n{result}"
            except Exception as e:
                return f"[错误] 列出目录失败: {e}"

        # ===== 命令执行工具 =====
        elif tool_name == "run_command":
            command = arguments.get("command")

            if not command:
                return "[错误] 缺少必需参数: command"

            try:
                result = await run_command(
                    command=command,
                    cwd=project_root,
                    config=config,
                    project_root=project_root,
                )

                output_lines = []
                output_lines.append(f"[命令] 执行: {command}")
                output_lines.append(f"[命令] 退出码: {result.returncode}")

                if result.stdout:
                    output_lines.append(f"\n标准输出:\n{result.stdout}")
                if result.stderr:
                    output_lines.append(f"\n标准错误:\n{result.stderr}")

                if not result.success:
                    output_lines.append(f"\n[错误] {result.error_message}")

                logger.info("[工具] run_command 完成: %s (退出码 %d)", command, result.returncode)
                return "\n".join(output_lines)

            except Exception as e:
                return f"[错误] 执行命令失败: {e}"

        # ===== Git 操作工具（T14 实现）=====
        elif tool_name in ["git_commit", "git_diff", "git_log", "git_status", "git_create_branch"]:
            return f"[提示] {tool_name} 工具尚未实现，将在 T14 完成。"

        # ===== 未知工具 =====
        else:
            return f"[错误] 未知工具: {tool_name}"

    except Exception as e:
        logger.error("[工具] 执行失败: %s - %s", tool_name, e)
        return f"[错误] 工具执行异常: {e}"


# ---------------------------------------------------------------------------
# 工具定义格式转换
# ---------------------------------------------------------------------------


def get_tool_definitions(
    format: Literal["claude", "openai"] = "claude",
) -> list[dict[str, Any]]:
    """获取工具定义列表（转换为 LLM API 格式）。

    参数
    ----
    format : "claude" 或 "openai"

    返回
    ----
    list[dict] : 工具定义列表

    格式说明
    --------
    Claude 格式：
    {
        "name": "tool_name",
        "description": "工具描述",
        "input_schema": { JSON Schema }
    }

    OpenAI 格式：
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "工具描述",
            "parameters": { JSON Schema }
        }
    }
    """
    if format == "claude":
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in TOOL_DEFINITIONS
        ]
    elif format == "openai":
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in TOOL_DEFINITIONS
        ]
    else:
        raise ValueError(f"不支持的格式: {format}，仅支持 'claude' 或 'openai'")


def get_tool_by_name(tool_name: str) -> ToolDefinition | None:
    """根据名称获取工具定义。

    参数
    ----
    tool_name : 工具名称

    返回
    ----
    ToolDefinition | None : 工具定义，未找到返回 None
    """
    for tool in TOOL_DEFINITIONS:
        if tool.name == tool_name:
            return tool
    return None
