"""BY19Code Claude Provider【T05】

基于 Anthropic SDK 的 ClaudeProvider 实现。

设计要点
--------
- 与 anthropic SDK 耦合隔离在本文件：仅此处 import anthropic
- 消息格式转换：Message → Anthropic API 格式（system 单独提取、tool_use/tool_result 块）
- 流式事件映射：Anthropic SSE → StreamEvent（text_delta / tool_call_* / usage / done）
- 异常统一映射到 LLMError 子类
- 限流/超时时指数退避重试（1s → 2s → 4s，最多 3 次）
- 费用计算：按 _PRICE_PER_MTOK 表查询，单位为每百万 token 的美元价格
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from by19code.llm.base import (
    LLMAuthError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
    LLMTimeoutError,
    Message,
    StreamEvent,
    ToolCall,
    ToolDefinition,
    TokenUsage,
)
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定价表（每百万 token 的美元价格）
# key: 模型标识符（小写），value: (input_price, output_price)
# ---------------------------------------------------------------------------

_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # claude-sonnet-4 系列
    "claude-sonnet-4-20250514":      (3.0,  15.0),
    "claude-sonnet-4-5-20251001":    (3.0,  15.0),
    "claude-sonnet-4-5":             (3.0,  15.0),
    "claude-sonnet-4":               (3.0,  15.0),
    # claude-haiku-4 系列
    "claude-haiku-4-5-20251001":     (0.80,  4.0),
    "claude-haiku-4-5":              (0.80,  4.0),
    "claude-haiku-4":                (0.80,  4.0),
    # 旧版 claude-3 系列（兼容）
    "claude-3-5-sonnet-20241022":    (3.0,  15.0),
    "claude-3-5-haiku-20241022":     (0.80,  4.0),
    "claude-3-opus-20240229":        (15.0, 75.0),
}

# 未匹配模型时的默认定价（使用 sonnet 价格保守估算）
_DEFAULT_PRICE: tuple[float, float] = (3.0, 15.0)

# 最大重试次数
_MAX_RETRIES = 3

# 重试基础等待时间（秒）
_RETRY_BASE_DELAY = 1.0


class ClaudeProvider(LLMProvider):
    """Anthropic Claude Provider

    构造参数
    --------
    api_key : Anthropic API Key（sk-ant-...）
    model   : 默认模型标识符；可在 chat() / stream_chat() 调用时覆盖
    base_url: 自定义 API 端点（可选，通常留空使用官方端点）

    异常映射
    --------
    anthropic.AuthenticationError  → LLMAuthError
    anthropic.RateLimitError        → LLMRateLimitError
    anthropic.APITimeoutError       → LLMTimeoutError
    anthropic.APIConnectionError    → LLMTimeoutError（连接失败视为超时重试）
    其他 anthropic.APIError         → LLMError
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-7-sonnet-20250219",  # Claude Sonnet 3.7 默认模型
        base_url: str | None = None,
        **kwargs: Any,  # 兜底：接收 provider_name 等额外参数，避免 TypeError
    ) -> None:
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic SDK 未安装，请运行: pip install anthropic"
            ) from exc

        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": 60.0,  # 设置 60 秒超时，避免流式响应挂起
            "default_headers": {
                "anthropic-version": "2023-06-01",
                "User-Agent": "BY19Code/0.1.0 (Windows; Python/3.12)",
            }
        }
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = _anthropic.AsyncAnthropic(**client_kwargs)
        self._default_model = model
        self._anthropic = _anthropic  # 保存引用，用于异常类型判断

        logger.debug("[Claude] Provider 初始化完成，默认模型: %s", model)

    # ------------------------------------------------------------------
    # LLMProvider 抽象属性
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "claude"

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _build_api_messages(
        messages: list[Message],
    ) -> tuple[str, list[dict[str, Any]]]:
        """将统一 Message 列表转换为 Anthropic API 所需格式。

        返回
        ----
        (system_prompt, api_messages)

        转换规则
        --------
        - role="system" → 提取为 system 字符串（取最后一条）
        - role="user"   → {"role": "user", "content": str}
        - role="assistant" 含 tool_calls → content 列表（text + tool_use 块）
        - role="tool"   → 合并连续 tool 消息为单条 user message（含 tool_result 块列表）
        """
        system_prompt = ""
        api_messages: list[dict[str, Any]] = []
        pending_tool_results: list[dict[str, Any]] = []

        def _flush_tool_results() -> None:
            """将积累的 tool_result 块合并为一条 user 消息推入 api_messages"""
            if pending_tool_results:
                api_messages.append({
                    "role": "user",
                    "content": list(pending_tool_results),
                })
                pending_tool_results.clear()

        for msg in messages:
            if msg.role == "system":
                # 取最后一条 system 消息作为 system prompt
                system_prompt = msg.content
                continue

            if msg.role == "tool":
                # 工具结果：积累为 tool_result 块，待下次刷新
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content,
                })
                continue

            # 遇到非 tool 消息，先刷新积累的 tool_results
            _flush_tool_results()

            if msg.role == "user":
                api_messages.append({"role": "user", "content": msg.content})

            elif msg.role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                # 文本内容块（可能为空字符串）
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                # 工具调用块
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                # assistant 消息至少需要一个块
                if not content_blocks:
                    content_blocks.append({"type": "text", "text": ""})
                api_messages.append({"role": "assistant", "content": content_blocks})

        # 循环结束后刷新剩余 tool_results
        _flush_tool_results()

        return system_prompt, api_messages

    @staticmethod
    def _build_api_tools(
        tools: list[ToolDefinition],
    ) -> list[dict[str, Any]]:
        """将 ToolDefinition 列表转换为 Anthropic tool 格式"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters if t.parameters else {
                    "type": "object",
                    "properties": {},
                },
            }
            for t in tools
        ]

    @staticmethod
    def _parse_response(response: Any) -> LLMResponse:
        """将 anthropic.Message 解析为 LLMResponse。

        content 块类型处理
        ------------------
        - "text"     → 拼接到 content 字符串
        - "tool_use" → 转换为 ToolCall，加入 tool_calls 列表
        """
        content_text = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                # input 字段已是 dict，无需 json.loads
                arguments = block.input if isinstance(block.input, dict) else {}
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=arguments,
                ))

        usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls if tool_calls else None,
            usage=usage,
            model=response.model,
            stop_reason=response.stop_reason,
        )

    def _map_exception(self, exc: Exception) -> LLMError:
        """将 anthropic SDK 异常映射为 LLMError 子类"""
        a = self._anthropic

        if isinstance(exc, a.AuthenticationError):
            return LLMAuthError(
                f"API Key 无效或权限不足: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )
        if isinstance(exc, a.RateLimitError):
            # 尝试从响应头取 retry_after
            retry_after: float | None = None
            if hasattr(exc, "response") and exc.response is not None:
                ra = exc.response.headers.get("retry-after")
                if ra is not None:
                    try:
                        retry_after = float(ra)
                    except ValueError:
                        pass
            return LLMRateLimitError(
                f"请求频率超限: {exc}",
                retry_after=retry_after,
                provider=self.provider_name,
                original_error=exc,
            )
        if isinstance(exc, (a.APITimeoutError, a.APIConnectionError)):
            return LLMTimeoutError(
                f"请求超时或连接失败: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )
        if isinstance(exc, a.BadRequestError):
            return LLMResponseError(
                f"请求格式错误: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )
        # 其他 APIError 及未知异常
        return LLMError(
            f"LLM 调用失败: {exc}",
            provider=self.provider_name,
            original_error=exc,
        )

    async def _create_with_retry(
        self,
        **kwargs: Any,
    ) -> Any:
        """带指数退避的 messages.create() 调用。

        仅在 RateLimitError / TimeoutError / ConnectionError 时重试。
        AuthenticationError / BadRequestError 等立即抛出，不重试。
        """
        a = self._anthropic
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                return await self._client.messages.create(**kwargs)
            except (a.RateLimitError, a.APITimeoutError, a.APIConnectionError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)  # 1s, 2s, 4s
                    logger.warning(
                        "[Claude] 第 %d/%d 次重试，等待 %.1fs: %s",
                        attempt + 1, _MAX_RETRIES, delay, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("[Claude] 已达最大重试次数 %d，放弃", _MAX_RETRIES)
            except Exception:
                # 非重试类异常立即向上抛出
                raise

        # 所有重试均失败
        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------
    # 核心接口实现
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        """非流式聊天。将消息转换为 Anthropic 格式后调用 messages.create()"""
        effective_model = model or self._default_model
        system_prompt, api_messages = self._build_api_messages(messages)

        kwargs: dict[str, Any] = {
            "model": effective_model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._build_api_tools(tools)

        logger.debug(
            "[Claude] chat() 调用 model=%s messages=%d",
            effective_model, len(api_messages),
        )

        try:
            response = await self._create_with_retry(**kwargs)
        except (
            self._anthropic.RateLimitError,
            self._anthropic.APITimeoutError,
            self._anthropic.APIConnectionError,
        ) as exc:
            # 重试耗尽后到达此处
            raise self._map_exception(exc) from exc
        except Exception as exc:
            raise self._map_exception(exc) from exc

        result = self._parse_response(response)
        result.usage.estimated_cost = self.calculate_cost(result.usage, effective_model)

        logger.debug(
            "[Claude] chat() 完成 tokens=%d cost=$%.6f",
            result.usage.total_tokens, result.usage.estimated_cost,
        )
        return result

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> AsyncIterator[StreamEvent]:
        """流式聊天，逐块产出 StreamEvent。

        Anthropic 流事件 → StreamEvent 映射
        -------------------------------------
        message_start(usage.input_tokens)          → （记录 input_tokens，不 yield）
        content_block_start(tool_use)              → tool_call_start
        content_block_delta(text_delta)            → text_delta
        content_block_delta(input_json_delta)      → tool_call_delta
        content_block_stop（tool_use 块）           → tool_call_end
        message_delta(usage.output_tokens)         → usage（含完整 TokenUsage）
        message_stop                               → done（含 LLMResponse）
        """
        effective_model = model or self._default_model
        system_prompt, api_messages = self._build_api_messages(messages)

        kwargs: dict[str, Any] = {
            "model": effective_model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._build_api_tools(tools)

        logger.debug(
            "[Claude] stream_chat() 开始 model=%s messages=%d",
            effective_model, len(api_messages),
        )

        # 流式状态跟踪变量
        input_tokens: int = 0
        output_tokens: int = 0
        accumulated_text: str = ""
        tool_calls: list[ToolCall] = []
        stop_reason: str | None = None

        # 当前正在积累的工具调用：index → (ToolCall, json_parts)
        active_tools: dict[int, tuple[ToolCall, list[str]]] = {}

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    event_type: str = event.type

                    if event_type == "message_start":
                        # 记录输入 token（来自 message_start.message.usage）
                        if hasattr(event, "message") and hasattr(event.message, "usage"):
                            input_tokens = event.message.usage.input_tokens

                    elif event_type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            tc = ToolCall(id=block.id, name=block.name, arguments={})
                            active_tools[event.index] = (tc, [])
                            yield StreamEvent(event_type="tool_call_start", data=tc)

                    elif event_type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            accumulated_text += delta.text
                            yield StreamEvent(event_type="text_delta", data=delta.text)
                        elif delta.type == "input_json_delta":
                            if event.index in active_tools:
                                active_tools[event.index][1].append(delta.partial_json)
                            yield StreamEvent(
                                event_type="tool_call_delta",
                                data=delta.partial_json,
                            )

                    elif event_type == "content_block_stop":
                        if event.index in active_tools:
                            tc, parts = active_tools.pop(event.index)
                            # 拼接 JSON 并解析 arguments
                            full_json = "".join(parts)
                            try:
                                tc = ToolCall(
                                    id=tc.id,
                                    name=tc.name,
                                    arguments=json.loads(full_json) if full_json else {},
                                )
                            except json.JSONDecodeError:
                                logger.warning(
                                    "[Claude] 工具 %s 参数 JSON 解析失败: %r",
                                    tc.name, full_json,
                                )
                                # 保持 arguments 为空 dict
                                tc = ToolCall(id=tc.id, name=tc.name, arguments={})
                            tool_calls.append(tc)
                            yield StreamEvent(event_type="tool_call_end", data=tc)

                    elif event_type == "message_delta":
                        if hasattr(event, "usage") and event.usage is not None:
                            output_tokens = event.usage.output_tokens
                        if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                            stop_reason = event.delta.stop_reason

                    elif event_type == "message_stop":
                        # 构造最终 TokenUsage 并 yield usage 事件
                        usage = TokenUsage(
                            prompt_tokens=input_tokens,
                            completion_tokens=output_tokens,
                        )
                        usage.estimated_cost = self.calculate_cost(usage, effective_model)
                        yield StreamEvent(event_type="usage", data=usage)

                        # 构造 LLMResponse 并 yield done 事件
                        final_response = LLMResponse(
                            content=accumulated_text,
                            tool_calls=tool_calls if tool_calls else None,
                            usage=usage,
                            model=effective_model,
                            stop_reason=stop_reason,
                        )
                        yield StreamEvent(event_type="done", data=final_response)

                        logger.debug(
                            "[Claude] stream_chat() 完成 tokens=%d cost=$%.6f",
                            usage.total_tokens, usage.estimated_cost,
                        )

        except (
            self._anthropic.RateLimitError,
            self._anthropic.APITimeoutError,
            self._anthropic.APIConnectionError,
            self._anthropic.AuthenticationError,
            self._anthropic.BadRequestError,
        ) as exc:
            mapped = self._map_exception(exc)
            logger.error("[Claude] stream_chat() 流式错误: %s", mapped)
            yield StreamEvent(event_type="error", data=str(mapped))
        except Exception as exc:
            mapped = self._map_exception(exc)
            logger.error("[Claude] stream_chat() 未知错误: %s", mapped)
            yield StreamEvent(event_type="error", data=str(mapped))

    # ------------------------------------------------------------------
    # 费用计算
    # ------------------------------------------------------------------

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        """根据 token 用量与模型定价计算费用（美元）。

        公式（PRD §7）：
          cost = (prompt_tokens / 1_000_000) * price_input
               + (completion_tokens / 1_000_000) * price_output

        未知模型使用 _DEFAULT_PRICE（sonnet 价格）。
        """
        model_key = model.lower()
        price_input, price_output = _PRICE_PER_MTOK.get(model_key, _DEFAULT_PRICE)

        cost = (
            (usage.prompt_tokens / 1_000_000) * price_input
            + (usage.completion_tokens / 1_000_000) * price_output
        )
        return round(cost, 6)
