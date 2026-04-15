"""BY19Code 上下文管理器【T12】

上下文管理器负责：
1. 管理对话历史（messages）
2. 估算 token 用量
3. 自动裁剪超长对话
4. 保持 tool_call/tool_result 配对完整性
5. 提供压缩和统计功能

裁剪策略
--------
- 当总 token 数超过 max_tokens 的 80% 时触发裁剪
- 裁剪到 60% 以下（预留 40% 给后续对话）
- 始终保留 system_message
- 从最早的消息开始删除
- 保持 tool_call 和 tool_result 的配对完整性

Token 估算
----------
- 中文：1 字符 ≈ 2 tokens
- 英文：4 字符 ≈ 1 token
- 工具调用参数 JSON 也计入
- 不需要精确，用于粗略判断
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from by19code.llm.base import Message, ToolCall

logger = logging.getLogger(__name__)


class ContextManager:
    """上下文管理器

    职责
    ----
    - 管理对话历史（messages）
    - 自动裁剪超长对话
    - 保持 tool_call/tool_result 配对完整性
    - 提供压缩和统计功能
    """

    def __init__(self, max_tokens: int = 100000):
        """初始化上下文管理器。

        参数
        ----
        max_tokens : 上下文窗口上限（默认 100000）
        """
        self.max_tokens = max_tokens
        self.system_message: Optional[Message] = None
        self.messages: list[Message] = []

        logger.info("[上下文] 初始化: max_tokens=%d", max_tokens)

    def add_message(self, message: Message) -> None:
        """添加消息到历史。

        参数
        ----
        message : 要添加的消息
        """
        # 如果是 system 消息，单独保存
        if message.role == "system":
            self.system_message = message
            logger.debug("[上下文] 设置 system_message")
            return

        # 添加到历史
        self.messages.append(message)
        logger.debug("[上下文] 添加消息: role=%s, content_len=%d", message.role, len(message.content))

        # 检查是否需要裁剪
        self._check_and_trim()

    def get_messages(self) -> list[Message]:
        """获取完整消息列表（供 LLM API 使用）。

        返回
        ----
        list[Message] : [system_message] + messages
        """
        if self.system_message:
            return [self.system_message] + self.messages
        return self.messages

    def clear(self) -> None:
        """清空对话历史（保留 system_message）。"""
        self.messages.clear()
        logger.info("[上下文] 已清空对话历史")

    def compact(self) -> str:
        """压缩对话历史（保留最近 10 条消息）。

        返回
        ----
        str : 压缩结果消息
        """
        old_count = len(self.messages)
        old_tokens = self._estimate_tokens(self.messages)

        # 保留最近 10 条消息
        if len(self.messages) > 10:
            self.messages = self.messages[-10:]

        new_count = len(self.messages)
        new_tokens = self._estimate_tokens(self.messages)
        saved_tokens = old_tokens - new_tokens

        logger.info("[上下文] 压缩完成: %d → %d 条消息，释放 %d tokens", old_count, new_count, saved_tokens)

        return f"已压缩：从 {old_count} 条消息压缩到 {new_count} 条，释放约 {saved_tokens} tokens"

    def get_stats(self) -> dict:
        """获取上下文统计信息。

        返回
        ----
        dict : {"message_count", "estimated_tokens", "max_tokens", "usage_percent"}
        """
        message_count = len(self.messages)
        estimated_tokens = self._estimate_tokens(self.get_messages())
        usage_percent = (estimated_tokens / self.max_tokens * 100) if self.max_tokens > 0 else 0.0

        return {
            "message_count": message_count,
            "estimated_tokens": estimated_tokens,
            "max_tokens": self.max_tokens,
            "usage_percent": usage_percent,
        }

    def _estimate_tokens(self, messages: list[Message]) -> int:
        """估算消息列表的 token 数。

        参数
        ----
        messages : 消息列表

        返回
        ----
        int : 估算的 token 数

        估算规则
        --------
        - 中文：1 字符 ≈ 2 tokens
        - 英文：4 字符 ≈ 1 token
        - 工具调用参数 JSON 也计入
        """
        total_tokens = 0

        for message in messages:
            # 估算 content
            content = message.content or ""
            total_tokens += self._estimate_text_tokens(content)

            # 估算 tool_calls
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    # 工具名称
                    total_tokens += self._estimate_text_tokens(tool_call.name)
                    # 参数 JSON
                    args_json = json.dumps(tool_call.arguments, ensure_ascii=False)
                    total_tokens += self._estimate_text_tokens(args_json)

        return total_tokens

    def _estimate_text_tokens(self, text: str) -> int:
        """估算单个文本的 token 数。

        参数
        ----
        text : 文本内容

        返回
        ----
        int : 估算的 token 数

        规则
        ----
        - 中文字符（Unicode >= 0x4E00）：1 字符 ≈ 2 tokens
        - 英文字符：4 字符 ≈ 1 token
        """
        chinese_chars = sum(1 for c in text if ord(c) >= 0x4E00)
        english_chars = len(text) - chinese_chars

        # 中文：1 字符 ≈ 2 tokens
        # 英文：4 字符 ≈ 1 token
        tokens = chinese_chars * 2 + english_chars // 4

        return tokens

    def _check_and_trim(self) -> None:
        """检查并裁剪超长对话。

        策略
        ----
        - 当总 token 数超过 max_tokens 的 80% 时触发裁剪
        - 裁剪到 60% 以下
        - 从最早的消息开始删除
        - 保持 tool_call/tool_result 配对完整性
        """
        current_tokens = self._estimate_tokens(self.get_messages())
        threshold = int(self.max_tokens * 0.8)

        if current_tokens <= threshold:
            return

        logger.info("[上下文] 触发裁剪: 当前 %d tokens，阈值 %d tokens", current_tokens, threshold)

        # 目标：裁剪到 60% 以下
        target_tokens = int(self.max_tokens * 0.6)

        # 从最早的消息开始删除
        while len(self.messages) > 0 and current_tokens > target_tokens:
            # 找到可以安全删除的消息索引
            delete_index = self._find_safe_delete_index()

            if delete_index is None:
                # 无法安全删除，停止裁剪
                logger.warning("[上下文] 无法安全删除消息，停止裁剪")
                break

            # 删除消息
            deleted_message = self.messages.pop(delete_index)
            logger.debug("[上下文] 删除消息: index=%d, role=%s", delete_index, deleted_message.role)

            # 重新计算 token 数
            current_tokens = self._estimate_tokens(self.get_messages())

        logger.info("[上下文] 裁剪完成: 剩余 %d 条消息，%d tokens", len(self.messages), current_tokens)

    def _find_safe_delete_index(self) -> Optional[int]:
        """找到可以安全删除的消息索引。

        返回
        ----
        int | None : 可删除的索引，None 表示无法安全删除

        规则
        ----
        - 如果是 assistant 消息且有 tool_calls，必须同时删除对应的 tool 消息
        - 如果是 tool 消息，必须同时删除对应的 assistant 消息
        - 优先删除最早的消息
        """
        if not self.messages:
            return None

        # 从第一条消息开始检查
        for i in range(len(self.messages)):
            message = self.messages[i]

            # 如果是 assistant 消息且有 tool_calls
            if message.role == "assistant" and message.tool_calls:
                # 检查后续是否有对应的 tool 消息
                tool_call_ids = {tc.id for tc in message.tool_calls}

                # 找到所有对应的 tool 消息索引
                tool_indices = []
                for j in range(i + 1, len(self.messages)):
                    if self.messages[j].role == "tool" and self.messages[j].tool_call_id in tool_call_ids:
                        tool_indices.append(j)

                # 如果找到了所有对应的 tool 消息，可以一起删除
                if len(tool_indices) == len(tool_call_ids):
                    # 先删除后面的 tool 消息（从后往前删，避免索引变化）
                    for j in reversed(tool_indices):
                        self.messages.pop(j)
                    # 返回 assistant 消息的索引（已经调整过）
                    return i

            # 如果是 tool 消息
            elif message.role == "tool":
                # 找到对应的 assistant 消息
                tool_call_id = message.tool_call_id

                # 向前查找对应的 assistant 消息
                for j in range(i - 1, -1, -1):
                    if self.messages[j].role == "assistant" and self.messages[j].tool_calls:
                        # 检查是否包含此 tool_call_id
                        if any(tc.id == tool_call_id for tc in self.messages[j].tool_calls):
                            # 找到了，但不能单独删除 tool 消息
                            # 跳过这条消息
                            break
                else:
                    # 没找到对应的 assistant 消息，可以安全删除
                    return i

            # 如果是普通的 user 或 assistant 消息（无 tool_calls）
            else:
                return i

        # 无法找到可安全删除的消息
        return None
