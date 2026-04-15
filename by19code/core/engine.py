"""BY19Code 对话引擎核心【T11】

对话引擎负责：
1. 管理对话历史
2. 调用 LLM Provider
3. 执行工具调用
4. 记录 token 用量
5. 处理异常

工具调用循环
------------
1. 用户输入 → LLM 生成回复
2. 如果包含工具调用 → 执行工具 → 将结果返回给 LLM
3. 重复步骤 2，直到 LLM 不再调用工具
4. 返回最终回复给用户
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncGenerator, Optional
from collections.abc import AsyncIterator

from by19code.config.settings import AppConfig
from by19code.llm.base import (
    Message,
    StreamEvent,
    LLMProvider,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
    ToolCall,
)
from by19code.llm.factory import LLMFactory
from by19code.core.tools import execute_tool, get_tool_definitions
from by19code.core.context import ContextManager
from by19code.db.database import get_db
from by19code.db.models import add_token_usage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 对话引擎
# ---------------------------------------------------------------------------


class ChatEngine:
    """对话引擎核心类

    职责
    ----
    - 管理对话历史（messages）
    - 调用 LLM Provider 生成回复
    - 执行工具调用并处理结果
    - 记录 token 用量到数据库
    - 处理异常并给出友好提示
    """

    def __init__(self, config: AppConfig, project_root: str | Path):
        """初始化对话引擎。

        参数
        ----
        config       : 应用配置
        project_root : 项目根目录
        """
        self.config = config
        self.project_root = Path(project_root).resolve()

        # 创建 LLM Provider
        self.provider: LLMProvider = LLMFactory.create(config)

        # 上下文管理器（T12）
        self.context = ContextManager(max_tokens=100000)

        # 初始化 System Prompt
        self._init_system_prompt()

        logger.info(
            "[引擎] 初始化完成: provider=%s, project=%s",
            self.provider.provider_name,
            self.project_root,
        )

    def _init_system_prompt(self) -> None:
        """初始化 System Prompt（Windows 版本）"""
        system_content = f"""你是 BY19Code，一个运行在 Windows 系统上的 AI 编程助手。

## 运行环境
- 操作系统：Windows
- Shell：PowerShell / cmd.exe
- 执行命令时请使用 Windows 兼容语法
- 文件路径使用 pathlib 或正斜杠，避免反斜杠转义问题
- 所有文件读写使用 UTF-8 编码

## 当前项目
- 项目路径：{self.project_root}
- 你可以使用以下工具：read_file, write_file, edit_file, run_command, list_directory, git_commit, git_diff, git_log, git_status, git_create_branch

## 工作原则
- 修改文件前先读取确认内容
- 一次只修改一个文件
- 修改后说明做了什么改动
- 执行命令前说明要执行什么
- 使用工具时要谨慎，确保操作的正确性
"""

        self.context.add_message(Message(role="system", content=system_content))
        logger.debug("[引擎] System Prompt 已初始化")

    async def chat(self, user_input: str) -> AsyncGenerator[StreamEvent, None]:
        """处理用户输入并生成回复（流式）。

        参数
        ----
        user_input : 用户输入

        返回
        ----
        AsyncGenerator[StreamEvent] : 流式事件

        工作流程
        --------
        1. 添加用户消息到历史
        2. 调用 LLM 生成回复（流式）
        3. 如果包含工具调用：
           a. 执行工具
           b. 将结果添加到历史
           c. 继续调用 LLM（工具调用循环）
        4. 记录 token 用量
        5. 返回最终回复
        """
        # 1. 添加用户消息
        self.context.add_message(Message(role="user", content=user_input))
        logger.info("[引擎] 用户输入: %s", user_input[:50])

        # 2. 工具调用循环（最多 20 轮）
        max_tool_rounds = self.config.safety.max_tool_rounds
        tool_round = 0

        while tool_round < max_tool_rounds:
            tool_round += 1
            logger.debug("[引擎] 工具调用轮次: %d/%d", tool_round, max_tool_rounds)

            # 调用 LLM
            accumulated_text = ""
            tool_calls: list[ToolCall] = []
            final_event: Optional[StreamEvent] = None

            try:
                async for event in self.provider.stream_chat(
                    messages=self.context.get_messages(),
                    tools=get_tool_definitions(format="claude"),
                    model=None,  # 使用默认模型
                    temperature=0.7,
                    max_tokens=8192,
                ):
                    # 转发事件给调用方
                    yield event

                    # 收集文本和工具调用
                    if event.event_type == "text_delta":
                        accumulated_text += str(event.data)
                    elif event.event_type == "tool_call_end":
                        tool_calls.append(event.data)
                    elif event.event_type == "done":
                        final_event = event

            except LLMAuthError as e:
                error_msg = f"[错误] API Key 无效，请检查配置: {e}"
                logger.error("[引擎] %s", error_msg)
                yield StreamEvent(event_type="error", data=error_msg)
                return

            except LLMRateLimitError as e:
                error_msg = f"[错误] 请求频率限制，请稍后重试: {e}"
                logger.error("[引擎] %s", error_msg)
                yield StreamEvent(event_type="error", data=error_msg)
                return

            except LLMTimeoutError as e:
                error_msg = f"[错误] 请求超时，请检查网络: {e}"
                logger.error("[引擎] %s", error_msg)
                yield StreamEvent(event_type="error", data=error_msg)
                return

            except Exception as e:
                error_msg = f"[错误] LLM 调用失败: {e}"
                logger.error("[引擎] %s", error_msg)
                yield StreamEvent(event_type="error", data=error_msg)
                return

            # 3. 添加 assistant 消息到历史
            self.context.add_message(
                Message(
                    role="assistant",
                    content=accumulated_text,
                    tool_calls=tool_calls if tool_calls else None,
                )
            )

            # 4. 记录 token 用量
            if final_event and final_event.data:
                response = final_event.data
                if hasattr(response, "usage") and response.usage:
                    await self._record_token_usage(response.usage, response.model)

            # 5. 如果没有工具调用，结束循环
            if not tool_calls:
                logger.info("[引擎] 对话完成，无工具调用")
                break

            # 6. 执行工具调用
            logger.info("[引擎] 执行 %d 个工具调用", len(tool_calls))

            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_args = tool_call.arguments

                logger.info("[引擎] 执行工具: %s, 参数: %s", tool_name, tool_args)

                # 执行工具
                try:
                    tool_result = await execute_tool(
                        tool_name=tool_name,
                        arguments=tool_args,
                        project_root=str(self.project_root),
                        config=self.config.safety,
                    )
                except Exception as e:
                    tool_result = f"[错误] 工具执行异常: {e}"
                    logger.error("[引擎] 工具执行失败: %s - %s", tool_name, e)

                # 添加工具结果到历史
                self.context.add_message(
                    Message(
                        role="tool",
                        content=tool_result,
                        tool_call_id=tool_call.id,
                    )
                )

                logger.debug("[引擎] 工具结果: %s", tool_result[:100])

            # 继续下一轮（LLM 会看到工具结果并继续回复）

        # 7. 检查是否超过最大轮次
        if tool_round >= max_tool_rounds:
            error_msg = f"[警告] 工具调用次数超过限制（{max_tool_rounds} 轮），已停止"
            logger.warning("[引擎] %s", error_msg)
            yield StreamEvent(event_type="error", data=error_msg)

    async def switch_model(self, provider_name: str) -> str:
        """切换 LLM Provider。

        参数
        ----
        provider_name : Provider 名称（如 "claude", "deepseek"）

        返回
        ----
        str : 切换结果消息
        """
        try:
            # 更新配置
            self.config.active_provider = provider_name

            # 创建新 Provider
            new_provider = LLMFactory.create(self.config)

            # 替换当前 Provider
            old_provider = self.provider.provider_name
            self.provider = new_provider

            logger.info("[引擎] 切换模型: %s → %s", old_provider, provider_name)

            return f"[成功] 已切换到 {provider_name}"

        except Exception as e:
            error_msg = f"[错误] 切换模型失败: {e}"
            logger.error("[引擎] %s", error_msg)
            return error_msg

    async def get_cost_summary(self) -> str:
        """获取当前会话的费用汇总。

        返回
        ----
        str : 费用汇总信息
        """
        try:
            from by19code.db.models import get_total_cost

            db = await get_db()
            total_cost = await get_total_cost(db)

            summary = f"""
[费用汇总]
- 累计费用：${total_cost:.6f}
- Provider：{self.provider.provider_name}
- 对话轮次：{len([m for m in self.context.messages if m.role == 'user'])}
"""
            return summary.strip()

        except Exception as e:
            error_msg = f"[错误] 获取费用汇总失败: {e}"
            logger.error("[引擎] %s", error_msg)
            return error_msg

    def clear_history(self) -> str:
        """清空对话历史（保留 System Prompt）。

        返回
        ----
        str : 清空结果消息
        """
        self.context.clear()
        logger.info("[引擎] 对话历史已清空")
        return "[成功] 对话历史已清空"

    def compact_context(self) -> str:
        """压缩上下文（保留最近 10 条消息）。

        返回
        ----
        str : 压缩结果消息
        """
        result = self.context.compact()
        logger.info("[引擎] 上下文已压缩")
        return result

    def get_context_stats(self) -> str:
        """获取上下文统计信息。

        返回
        ----
        str : 统计信息
        """
        stats = self.context.get_stats()

        summary = f"""
[上下文统计]
- 消息数量：{stats['message_count']}
- 估算 Token：{stats['estimated_tokens']}
- 上下文上限：{stats['max_tokens']}
- 使用率：{stats['usage_percent']:.1f}%
"""
        return summary.strip()

    async def _record_token_usage(self, usage, model: str) -> None:
        """记录 token 用量到数据库。

        参数
        ----
        usage : TokenUsage 对象
        model : 模型名称
        """
        try:
            db = await get_db()
            await add_token_usage(
                conn=db,
                provider_name=self.provider.provider_name,
                model_name=model,
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                cost_usd=usage.estimated_cost,
                project_id=None,  # TODO: 关联项目 ID
            )
            logger.debug(
                "[引擎] Token 用量已记录: %d tokens, $%.6f",
                usage.total_tokens,
                usage.estimated_cost,
            )
        except Exception as e:
            logger.error("[引擎] 记录 token 用量失败: %s", e)
