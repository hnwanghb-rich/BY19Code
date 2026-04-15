"""BY19Code OpenAI 兼容 Provider【T06】

基于 openai SDK 的 OpenAICompatibleProvider 实现，通过 base_url 参数适配
DeepSeek / OpenAI 官方及任意 OpenAI 格式兼容 API。

设计要点
--------
- 与 openai SDK 耦合隔离在本文件：仅此处 import openai
- 消息格式转换：Message → OpenAI API 格式
  * system 消息保留在 messages 列表内（无需单独提取，与 Claude 的差异）
  * assistant 含 tool_calls → tool_calls 数组（arguments 序列化为 JSON 字符串）
  * tool 消息保持独立（无需合并，与 Claude 的差异）
- 流式事件映射：OpenAI chunk delta → StreamEvent
  * delta.content          → text_delta
  * delta.tool_calls 首次  → tool_call_start
  * delta.tool_calls 续增  → tool_call_delta
  * finish_reason 出现时   → tool_call_end（所有待完成工具）
  * choices=[] usage chunk → 记录 token 用量
  * 流结束后               → usage + done
- 异常统一映射到 LLMError 子类
- 限流/超时时指数退避重试（非流式；1s → 2s → 4s，最多 3 次）
- 费用计算：_PRICE_PER_MTOK 表，单位 $/MTok
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定价表（每百万 token 的美元价格）
# key: 模型标识符（小写），value: (input_price, output_price)
# ---------------------------------------------------------------------------

_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # DeepSeek 系列
    # ¥1/MTok input ≈ $0.14；¥2/MTok output ≈ $0.28（汇率 7.14）
    "deepseek-chat":          (0.14, 0.28),
    "deepseek-coder":         (0.14, 0.28),
    # DeepSeek-R1 推理模型（¥4/¥16 per MTok）
    "deepseek-reasoner":      (0.55, 2.19),
    "deepseek-r1":            (0.55, 2.19),
    # OpenAI 系列（通过 base_url 切换时使用）
    "gpt-4o":                 (2.50, 10.0),
    "gpt-4o-mini":            (0.15,  0.60),
    "gpt-4-turbo":            (10.0, 30.0),
    "gpt-4-turbo-preview":    (10.0, 30.0),
    "gpt-3.5-turbo":          (0.50,  1.50),
}

# 未匹配模型时的默认定价（DeepSeek-chat 价格）
_DEFAULT_PRICE: tuple[float, float] = (0.14, 0.28)

# 最大重试次数
_MAX_RETRIES = 3

# 重试基础等待时间（秒）
_RETRY_BASE_DELAY = 1.0


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 API Provider（DeepSeek / OpenAI 等）

    构造参数
    --------
    api_key       : API Key
    model         : 默认模型标识符（如 "deepseek-chat" / "gpt-4o"）
    base_url      : 自定义 API 端点，如 "https://api.deepseek.com"；
                    为 None 时使用 OpenAI 官方端点
    provider_name : 标识符字符串，如 "deepseek" / "openai"（默认 "openai"）

    异常映射
    --------
    openai.AuthenticationError  → LLMAuthError
    openai.RateLimitError        → LLMRateLimitError
    openai.APITimeoutError       → LLMTimeoutError
    openai.APIConnectionError    → LLMTimeoutError（连接失败视为超时重试）
    openai.BadRequestError       → LLMResponseError
    其他 APIError 及未知异常     → LLMError
    """

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str | None = None,
        provider_name: str = "openai",
    ) -> None:
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError(
                "openai SDK 未安装，请运行: pip install openai"
            ) from exc

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": 60.0,  # 设置 60 秒超时，避免流式响应挂起
            "max_retries": 0,  # 禁用自动重试，避免卡住
        }
        if base_url:
            kwargs["base_url"] = base_url

        self._client = _openai.AsyncOpenAI(**kwargs)
        self._default_model = model
        self._provider_name_val = provider_name
        self._openai = _openai  # 保存引用，用于异常类型判断

        logger.debug("[%s] Provider 初始化完成，默认模型: %s", provider_name, model)

    # ------------------------------------------------------------------
    # LLMProvider 抽象属性
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return self._provider_name_val

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _build_api_messages(
        messages: list[Message],
    ) -> list[dict[str, Any]]:
        """将统一 Message 列表转换为 OpenAI API 格式。

        与 Anthropic 格式的关键差异
        --------------------------
        - system 消息保留在 messages 列表第一位（无需单独提取）
        - tool 消息保持独立（role="tool"，含 tool_call_id）
        - assistant 的 tool_calls 中 arguments 必须序列化为 JSON 字符串

        转换规则
        --------
        system    → {"role": "system", "content": str}
        user      → {"role": "user", "content": str}
        assistant → {"role": "assistant", "content": str | None,
                      "tool_calls": [{id, type, function: {name, arguments_json}}]}
        tool      → {"role": "tool", "tool_call_id": str, "content": str}
        """
        api_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                api_messages.append({"role": "system", "content": msg.content})

            elif msg.role == "user":
                api_messages.append({"role": "user", "content": msg.content})

            elif msg.role == "assistant":
                m: dict[str, Any] = {"role": "assistant"}
                if msg.tool_calls:
                    # 有工具调用时，content 通常为 None（OpenAI 规范）
                    m["content"] = msg.content if msg.content else None
                    m["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                # OpenAI 要求 arguments 为 JSON 字符串（非 dict）
                                "arguments": json.dumps(
                                    tc.arguments, ensure_ascii=False
                                ),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                else:
                    m["content"] = msg.content
                api_messages.append(m)

            elif msg.role == "tool":
                # tool 消息保持独立，不合并（与 Anthropic 格式不同）
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id or "",
                    "content": msg.content,
                })

        return api_messages

    @staticmethod
    def _build_api_tools(
        tools: list[ToolDefinition],
    ) -> list[dict[str, Any]]:
        """将 ToolDefinition 列表转换为 OpenAI tool 格式（包裹在 function 层）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters if t.parameters else {
                        "type": "object",
                        "properties": {},
                    },
                },
            }
            for t in tools
        ]

    @staticmethod
    def _parse_response(response: Any) -> LLMResponse:
        """将 openai.ChatCompletion 解析为 LLMResponse。

        关键差异（对比 Anthropic）
        --------------------------
        - response.choices[0].message.tool_calls → 每个 tc.function.arguments
          是 JSON 字符串，必须 json.loads() 转为 dict
        - response.usage 可能为 None（部分兼容 API 不返回用量）
        - response.model 对应实际使用的模型
        """
        choice = response.choices[0]
        message = choice.message

        content_text: str = message.content or ""
        tool_calls: list[ToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = (
                        json.loads(tc.function.arguments)
                        if tc.function.arguments
                        else {}
                    )
                except json.JSONDecodeError:
                    logger.warning(
                        "[OpenAI] 工具 %s 参数 JSON 解析失败: %r",
                        tc.function.name, tc.function.arguments,
                    )
                    arguments = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=arguments,
                ))

        usage = TokenUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls if tool_calls else None,
            usage=usage,
            model=response.model or "",
            stop_reason=choice.finish_reason,
        )

    def _map_exception(self, exc: Exception) -> LLMError:
        """将 openai SDK 异常映射为 LLMError 子类"""
        o = self._openai

        if isinstance(exc, o.AuthenticationError):
            return LLMAuthError(
                f"API Key 无效或权限不足: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )
        if isinstance(exc, o.RateLimitError):
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
        if isinstance(exc, (o.APITimeoutError, o.APIConnectionError)):
            return LLMTimeoutError(
                f"请求超时或连接失败: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )
        if isinstance(exc, o.BadRequestError):
            return LLMResponseError(
                f"请求格式错误: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )
        return LLMError(
            f"LLM 调用失败: {exc}",
            provider=self.provider_name,
            original_error=exc,
        )

    async def _create_with_retry(self, **kwargs: Any) -> Any:
        """带指数退避的 chat.completions.create() 调用（仅用于非流式）。

        仅在 RateLimitError / TimeoutError / ConnectionError 时重试（最多 3 次）。
        AuthenticationError / BadRequestError 等立即抛出，不重试。
        """
        o = self._openai
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                return await self._client.chat.completions.create(**kwargs)
            except (o.RateLimitError, o.APITimeoutError, o.APIConnectionError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)  # 1s, 2s, 4s
                    logger.warning(
                        "[%s] 第 %d/%d 次重试，等待 %.1fs: %s",
                        self.provider_name, attempt + 1, _MAX_RETRIES, delay, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "[%s] 已达最大重试次数 %d，放弃",
                        self.provider_name, _MAX_RETRIES,
                    )
            except Exception:
                # 非重试类异常立即向上抛出
                raise

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
        """非流式聊天。将消息转换为 OpenAI 格式后调用 chat.completions.create()"""
        effective_model = model or self._default_model
        api_messages = self._build_api_messages(messages)

        kwargs: dict[str, Any] = {
            "model": effective_model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = self._build_api_tools(tools)

        logger.debug(
            "[%s] chat() 调用 model=%s messages=%d",
            self.provider_name, effective_model, len(api_messages),
        )

        try:
            response = await self._create_with_retry(**kwargs)
        except (
            self._openai.RateLimitError,
            self._openai.APITimeoutError,
            self._openai.APIConnectionError,
        ) as exc:
            # 重试耗尽后到达此处
            raise self._map_exception(exc) from exc
        except Exception as exc:
            raise self._map_exception(exc) from exc

        result = self._parse_response(response)
        result.usage.estimated_cost = self.calculate_cost(result.usage, effective_model)

        logger.debug(
            "[%s] chat() 完成 tokens=%d cost=$%.6f",
            self.provider_name, result.usage.total_tokens, result.usage.estimated_cost,
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

        OpenAI chunk → StreamEvent 映射
        --------------------------------
        delta.content（非空）               → text_delta
        delta.tool_calls[i]（id 非 None）   → tool_call_start
        delta.tool_calls[i]（id 为 None）   → tool_call_delta
        choice.finish_reason（非 None）     → 触发所有待完成工具的 tool_call_end
        chunk（choices=[]，usage 非 None）  → 记录 token 用量（stream_options）
        流结束后                            → usage + done

        注意
        ----
        - stream_options={"include_usage": True} 请求携带用量，部分兼容 API 可能忽略
        - 若流中未携带用量，usage 事件 token 数为 0（不影响 done 事件）
        - 流式模式不重试（重启流式响应代价过高）
        """
        effective_model = model or self._default_model
        api_messages = self._build_api_messages(messages)

        kwargs: dict[str, Any] = {
            "model": effective_model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            # 请求携带 token 用量（OpenAI / DeepSeek 均支持）
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = self._build_api_tools(tools)

        logger.debug(
            "[%s] stream_chat() 开始 model=%s messages=%d",
            self.provider_name, effective_model, len(api_messages),
        )

        # 流式状态跟踪变量
        input_tokens: int = 0
        output_tokens: int = 0
        accumulated_text: str = ""
        completed_tool_calls: list[ToolCall] = []
        stop_reason: str | None = None

        # 正在积累的工具调用：index → {"id": str, "name": str, "args_parts": list[str]}
        active_tools: dict[int, dict[str, Any]] = {}

        try:
            stream = await self._client.chat.completions.create(**kwargs)

            logger.debug("[%s] 开始接收流式响应", self.provider_name)

            async for chunk in stream:
                logger.debug("[%s] 收到 chunk: choices=%d", self.provider_name, len(chunk.choices) if chunk.choices else 0)
                # ----------------------------------------------------------
                # usage chunk：choices=[]，携带最终 token 用量
                # OpenAI 在 stream_options.include_usage=True 时最后发一条
                # ----------------------------------------------------------
                if not chunk.choices:
                    if chunk.usage is not None:
                        input_tokens = chunk.usage.prompt_tokens or 0
                        output_tokens = chunk.usage.completion_tokens or 0
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # ----------------------------------------------------------
                # 文本增量
                # ----------------------------------------------------------
                if delta.content:
                    accumulated_text += delta.content
                    yield StreamEvent(event_type="text_delta", data=delta.content)

                # ----------------------------------------------------------
                # 工具调用增量
                # ----------------------------------------------------------
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx: int = tc_delta.index

                        # 首次出现此 index（id 非 None）→ tool_call_start
                        if tc_delta.id is not None:
                            func_name = (
                                tc_delta.function.name
                                if tc_delta.function is not None
                                else ""
                            )
                            active_tools[idx] = {
                                "id": tc_delta.id,
                                "name": func_name,
                                "args_parts": [],
                            }
                            tc_stub = ToolCall(
                                id=tc_delta.id,
                                name=func_name,
                                arguments={},
                            )
                            yield StreamEvent(event_type="tool_call_start", data=tc_stub)

                        # arguments 增量（可能与首次同 chunk，也可能在后续 chunk）
                        if (
                            tc_delta.function is not None
                            and tc_delta.function.arguments
                            and idx in active_tools
                        ):
                            active_tools[idx]["args_parts"].append(
                                tc_delta.function.arguments
                            )
                            yield StreamEvent(
                                event_type="tool_call_delta",
                                data=tc_delta.function.arguments,
                            )

                # ----------------------------------------------------------
                # finish_reason 出现：所有工具调用参数已完整，逐个 emit tool_call_end
                # ----------------------------------------------------------
                if choice.finish_reason:
                    stop_reason = choice.finish_reason

                    if active_tools:
                        for idx in sorted(active_tools.keys()):
                            info = active_tools[idx]
                            full_json = "".join(info["args_parts"])
                            try:
                                arguments = json.loads(full_json) if full_json else {}
                            except json.JSONDecodeError:
                                logger.warning(
                                    "[%s] 工具 %s 参数 JSON 解析失败: %r",
                                    self.provider_name, info["name"], full_json,
                                )
                                arguments = {}
                            tc = ToolCall(
                                id=info["id"],
                                name=info["name"],
                                arguments=arguments,
                            )
                            completed_tool_calls.append(tc)
                            yield StreamEvent(event_type="tool_call_end", data=tc)
                        active_tools.clear()

            # ------------------------------------------------------------------
            # 流结束：emit usage 与 done
            # ------------------------------------------------------------------
            usage = TokenUsage(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
            usage.estimated_cost = self.calculate_cost(usage, effective_model)
            yield StreamEvent(event_type="usage", data=usage)

            final_response = LLMResponse(
                content=accumulated_text,
                tool_calls=completed_tool_calls if completed_tool_calls else None,
                usage=usage,
                model=effective_model,
                stop_reason=stop_reason,
            )
            yield StreamEvent(event_type="done", data=final_response)

            logger.debug(
                "[%s] stream_chat() 完成 tokens=%d cost=$%.6f",
                self.provider_name, usage.total_tokens, usage.estimated_cost,
            )

        except (
            self._openai.RateLimitError,
            self._openai.APITimeoutError,
            self._openai.APIConnectionError,
            self._openai.AuthenticationError,
            self._openai.BadRequestError,
        ) as exc:
            mapped = self._map_exception(exc)
            logger.error("[%s] stream_chat() 流式错误: %s", self.provider_name, mapped)
            yield StreamEvent(event_type="error", data=str(mapped))
        except Exception as exc:
            mapped = self._map_exception(exc)
            logger.error("[%s] stream_chat() 未知错误: %s", self.provider_name, mapped)
            yield StreamEvent(event_type="error", data=str(mapped))

    # ------------------------------------------------------------------
    # 费用计算
    # ------------------------------------------------------------------

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        """根据 token 用量与模型定价计算费用（美元）。

        公式（PRD §7）：
          cost = (prompt_tokens / 1_000_000) * price_input
               + (completion_tokens / 1_000_000) * price_output

        未知模型使用 _DEFAULT_PRICE（DeepSeek-chat 价格）。
        """
        model_key = model.lower()
        price_input, price_output = _PRICE_PER_MTOK.get(model_key, _DEFAULT_PRICE)

        cost = (
            (usage.prompt_tokens / 1_000_000) * price_input
            + (usage.completion_tokens / 1_000_000) * price_output
        )
        return round(cost, 6)
