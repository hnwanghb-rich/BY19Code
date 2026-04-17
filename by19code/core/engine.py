"""BY19Code 对话引擎核心【T11】

对话引擎负责：
1. 管理对话历史
2. 调用 LLM Provider
3. 执行工具调用
4. 记录 token 用量
5. 处理异常
6. 超时自动切换模型

工具调用循环
------------
1. 用户输入 → LLM 生成回复
2. 如果包含工具调用 → 执行工具 → 将结果返回给 LLM
3. 重复步骤 2，直到 LLM 不再调用工具
4. 返回最终回复给用户

超时切换机制
------------
1. 如果模型响应超过 change_model_time 秒无输出
2. 自动切换到下一个可用模型
3. 使用相同的输入重试
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
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
from by19code.core.tools import execute_tool, TOOL_DEFINITIONS
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

        # 超时切换相关
        self._last_event_time = time.time()
        self._timeout_threshold = config.safety.change_model_time
        self._timeout_start_time = None  # 记录超时开始时间

        # 超时跟踪器
        from by19code.core.timeout_tracker import TimeoutTracker
        self.timeout_tracker = TimeoutTracker()

        # 初始化 System Prompt
        self._init_system_prompt()

        logger.info(
            "[引擎] 初始化完成: provider=%s, project=%s, auto_switch=%s",
            self.provider.provider_name,
            self.project_root,
            config.safety.auto_switch_on_timeout,
        )

    def _init_system_prompt(self) -> None:
        """初始化 System Prompt（Windows 版本）"""
        # 检查当前模型是否支持工具调用
        active_provider_config = self.config.get_active_provider()
        supports_tools = active_provider_config.supports_tools if active_provider_config else True

        if supports_tools:
            tools_info = """
## 当前项目
- 项目路径：{project_root}
- 可用工具：read_file, write_file, edit_file, run_command, list_directory, git_commit, git_diff, git_log, git_status, git_create_branch

## CRITICAL RULES - YOU MUST FOLLOW THESE RULES STRICTLY
- You MUST use tools to write/read/edit files. Do NOT simulate tool calls as text.
- To CREATE a file: call the `write_file` tool (you may also show the code in your reply)
- To MODIFY a file: call the `edit_file` tool
- To READ a file: call the `read_file` tool
- When writing code, ALWAYS call `write_file` to save it — showing code in the reply is allowed, but the tool call is MANDATORY.
- DO NOT output tool calls as text like `functions.write_file(...)`. You MUST use the actual API tool calling mechanism.

## FILE PATH RULES - CRITICAL
- ALL file paths MUST be RELATIVE paths, never absolute paths.
- CORRECT: `main.py`, `src/main.py`, `myproject/utils/helper.py`
- WRONG: `/main.py`, `/src/main.py`, `C:/main.py`, `D:/main.py`
- The project root is already: {{project_root}} — just use relative paths inside it.

## 强制规则
- 创建文件：必须调用 write_file 工具（回复中展示代码是允许的，但工具调用是必须的）
- 修改文件：必须调用 edit_file 工具
- 文件路径必须使用相对路径，禁止使用 /filename 或 C:/filename 等绝对路径
- 禁止用文本格式模拟工具调用（如 functions.xxx(...)），必须使用 API 工具调用机制
"""
        else:
            tools_info = """
## 当前项目
- 项目路径：{project_root}
- 注意：当前模型不支持工具调用（function calling），你只能提供建议和指导，无法直接操作文件或执行命令

## 工作原则
- 提供详细的代码示例和操作步骤
- 给出清晰的命令行指令供用户手动执行
- 解释每个步骤的目的和注意事项
"""

        system_content = f"""你是 BY19Code，一个运行在 Windows 系统上的 AI 编程助手。

## 运行环境
- 操作系统：Windows
- Shell：PowerShell / cmd.exe
- 执行命令时请使用 Windows 兼容语法
- 文件路径使用 pathlib 或正斜杠，避免反斜杠转义问题
- 所有文件读写使用 UTF-8 编码
{tools_info.format(project_root=self.project_root)}
"""

        self.context.add_message(Message(role="system", content=system_content))
        logger.debug("[引擎] System Prompt 已初始化 (supports_tools=%s)", supports_tools)

    def _clean_incomplete_tool_calls(self) -> None:
        """清理对话历史中不完整的工具调用。

        移除没有对应工具结果的 assistant 消息（包含 tool_calls）。
        这可以避免切换模型后出现格式错误。
        """
        messages = self.context.get_messages()
        cleaned_messages = []
        pending_tool_calls = set()  # 等待结果的 tool_call_id

        for msg in messages:
            if msg.role == "assistant" and msg.tool_calls:
                # 记录这个 assistant 消息中的所有 tool_call_id
                tool_call_ids = {tc.id for tc in msg.tool_calls}
                pending_tool_calls.update(tool_call_ids)
                cleaned_messages.append(msg)

            elif msg.role == "tool":
                # 工具结果消息，移除对应的 pending tool_call_id
                if msg.tool_call_id in pending_tool_calls:
                    pending_tool_calls.remove(msg.tool_call_id)
                cleaned_messages.append(msg)

            else:
                # 其他消息直接保留
                cleaned_messages.append(msg)

        # 如果还有未完成的工具调用，移除最后一个包含工具调用的 assistant 消息
        if pending_tool_calls:
            logger.warning(
                "[引擎] 检测到 %d 个未完成的工具调用，清理对话历史",
                len(pending_tool_calls)
            )

            # 从后往前找到最后一个包含工具调用的 assistant 消息并移除
            for i in range(len(cleaned_messages) - 1, -1, -1):
                msg = cleaned_messages[i]
                if msg.role == "assistant" and msg.tool_calls:
                    # 检查这个消息的工具调用是否在 pending 中
                    msg_tool_ids = {tc.id for tc in msg.tool_calls}
                    if msg_tool_ids & pending_tool_calls:  # 有交集
                        logger.info("[引擎] 移除不完整的 assistant 消息（索引 %d）", i)
                        cleaned_messages.pop(i)
                        # 移除对应的 pending tool_call_ids
                        pending_tool_calls -= msg_tool_ids

                        # 如果所有 pending 都清理完了，停止
                        if not pending_tool_calls:
                            break

        # 更新上下文
        self.context._messages = cleaned_messages
        logger.debug("[引擎] 对话历史清理完成，剩余 %d 条消息", len(cleaned_messages))

    def _get_next_available_provider(self) -> str | None:
        """获取下一个可用的模型（优先选择超时次数最少的）。

        返回
        ----
        str | None : 下一个可用模型名称，如果没有则返回 None
        """
        current_provider = self.config.active_provider
        available_providers = []

        for provider in self.config.llm_providers:
            # 检查是否有 API Key
            has_key = provider.api_key and provider.api_key != f"${{BY19CODE_{provider.name.upper()}_API_KEY}}"
            if has_key:
                available_providers.append(provider.name)

        # 如果只有一个可用模型，返回 None
        if len(available_providers) <= 1:
            return None

        # 使用超时跟踪器选择超时次数最少的模型
        best_model = self.timeout_tracker.get_least_timeout_model(
            available_providers,
            exclude=current_provider
        )

        if best_model:
            timeout_count = self.timeout_tracker.get_timeout_count(best_model)
            logger.info(
                "[引擎] 选择下一个模型: %s (历史超时 %d 次)",
                best_model,
                timeout_count
            )

        return best_model

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

            # 重置超时计时器
            self._last_event_time = time.time()
            self._timeout_start_time = None  # 重置超时开始时间
            has_received_event = False

            # 检查当前模型是否支持工具调用
            active_provider_config = self.config.get_active_provider()
            supports_tools = active_provider_config.supports_tools if active_provider_config else True
            tools_to_use = TOOL_DEFINITIONS if supports_tools else []

            # 创建一个异步任务来检测超时
            timeout_detected = False

            try:
                async for event in self.provider.stream_chat(
                    messages=self.context.get_messages(),
                    tools=tools_to_use,  # 根据模型配置决定是否传递工具
                    model=None,  # 使用默认模型
                    temperature=0.7,
                    max_tokens=8192,
                ):
                    # 检查是否超时
                    current_time = time.time()
                    elapsed = current_time - self._last_event_time

                    # 如果超过阈值且启用了自动切换
                    if elapsed > self._timeout_threshold and self.config.safety.auto_switch_on_timeout:
                        if self._timeout_start_time is None:
                            # 第一次检测到超时
                            self._timeout_start_time = current_time
                            logger.warning(
                                "[引擎] 检测到超时: %s 已 %.1f 秒无响应",
                                self.config.active_provider,
                                elapsed
                            )

                        # 如果持续超时，触发切换
                        timeout_duration = current_time - self._timeout_start_time
                        if timeout_duration >= 5:  # 持续 5 秒确认超时
                            timeout_detected = True
                            logger.error(
                                "[引擎] 模型 %s 超时 (%.1f 秒)，准备切换",
                                self.config.active_provider,
                                elapsed
                            )
                            break

                    # 更新最后事件时间
                    self._last_event_time = current_time
                    self._timeout_start_time = None  # 收到事件，重置超时开始时间
                    has_received_event = True

                    # 转发事件给调用方
                    yield event

                    # 收集文本和工具调用
                    if event.event_type == "text_delta":
                        accumulated_text += str(event.data)
                    elif event.event_type == "tool_call_end":
                        tool_calls.append(event.data)
                    elif event.event_type == "done":
                        final_event = event

                # 如果检测到超时，记录并切换模型
                if timeout_detected:
                    current_model = self.config.active_provider

                    # 记录超时
                    self.timeout_tracker.record_timeout(current_model)

                    # 获取下一个模型
                    next_model = self._get_next_available_provider()

                    if next_model:
                        # 切换模型
                        yield StreamEvent(
                            event_type="error",
                            data=f"[警告] 模型 {current_model} 响应超时，自动切换到 {next_model}"
                        )

                        await self.switch_model(next_model)

                        # 重新发起请求（递归调用）
                        logger.info("[引擎] 使用新模型 %s 重新处理请求", next_model)
                        async for retry_event in self.chat(user_input):
                            yield retry_event
                        return
                    else:
                        yield StreamEvent(
                            event_type="error",
                            data=f"[错误] 模型 {current_model} 超时，但没有其他可用模型"
                        )
                        return

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

            # 5. 如果没有工具调用，尝试从文本中提取代码块并写文件
            if not tool_calls:
                if accumulated_text:
                    written = await self._extract_and_write_code(accumulated_text)
                    if written:
                        for msg in written:
                            yield StreamEvent(event_type="processing", data=msg)
                logger.info("[引擎] 对话完成，无工具调用")
                break

            # 6. 执行工具调用
            logger.info("[引擎] 执行 %d 个工具调用", len(tool_calls))

            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_args = tool_call.arguments

                logger.info("[引擎] 执行工具: %s, 参数: %s", tool_name, tool_args)

                # 发送工具执行开始事件（用于显示计时器）
                yield StreamEvent(event_type="tool_executing_start", data=tool_name)

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

                # 发送工具执行结束事件（停止计时器）
                yield StreamEvent(event_type="tool_executing_end", data=tool_name)

                # 截断过大的工具结果（避免上下文过大导致延迟）
                MAX_TOOL_RESULT_LENGTH = 10000  # 最大 10000 字符
                if len(tool_result) > MAX_TOOL_RESULT_LENGTH:
                    original_length = len(tool_result)
                    tool_result = tool_result[:MAX_TOOL_RESULT_LENGTH] + f"\n\n[结果过大，已截断。原始长度: {original_length} 字符，显示前 {MAX_TOOL_RESULT_LENGTH} 字符]"
                    logger.warning("[引擎] 工具结果过大，已截断: %d → %d 字符", original_length, len(tool_result))

                # 添加工具结果到历史
                self.context.add_message(
                    Message(
                        role="tool",
                        content=tool_result,
                        tool_call_id=tool_call.id,
                    )
                )

                logger.debug("[引擎] 工具结果: %s", tool_result[:100])

            # 所有工具执行完成，发送"处理中"事件
            yield StreamEvent(event_type="processing", data="正在处理工具结果...")

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

            # 清理对话历史中不完整的工具调用
            self._clean_incomplete_tool_calls()

            # 重新初始化 System Prompt（因为工具支持可能不同）
            # 清除旧的 system 消息
            messages = self.context.get_messages()
            if messages and messages[0].role == "system":
                messages.pop(0)

            # 添加新的 system 消息
            self._init_system_prompt()

            logger.info("[引擎] 切换模型: %s → %s", old_provider, provider_name)

            new_config = self.config.get_active_provider()
            if new_config and new_config.model_label:
                model_str = new_config.model_label
            elif new_config:
                model_str = new_config.model
            else:
                model_str = provider_name
            return f"[成功] 已切换到 {provider_name}【{model_str}】"

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

    async def _extract_and_write_code(self, text: str) -> list[str]:
        """从模型文本回复中提取代码块并写入文件。

        匹配格式：
          ```python:path/to/file.py
          ...code...
          ```
        或：
          ```python
          # filename: path/to/file.py
          ...code...
          ```
        """
        from by19code.file_ops.operations import write_file, FileOperationError

        written: list[str] = []

        # 模式1: ```lang:filepath
        pattern1 = re.compile(
            r"```[a-zA-Z]*:([^\n]+)\n(.*?)```",
            re.DOTALL,
        )
        # 模式2: ```lang\n# filename: filepath
        pattern2 = re.compile(
            r"```[a-zA-Z]*\n#\s*(?:filename|file)[:\s]+([^\n]+)\n(.*?)```",
            re.DOTALL,
        )

        matches: list[tuple[str, str]] = []
        for m in pattern1.finditer(text):
            matches.append((m.group(1).strip(), m.group(2)))
        for m in pattern2.finditer(text):
            matches.append((m.group(1).strip(), m.group(2)))

        for filepath, content in matches:
            try:
                write_file(filepath, content, self.project_root)
                msg = f"[自动写入] {filepath}"
                logger.info("[引擎] %s", msg)
                written.append(msg)
            except FileOperationError as e:
                logger.warning("[引擎] 自动写入失败 %s: %s", filepath, e)

        return written
