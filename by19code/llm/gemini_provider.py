"""BY19Code Gemini Provider（原生 Google Generative AI SDK）

使用 Google 原生 API，支持 AQ. 格式的新版 API Key。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from by19code.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    StreamEvent,
    ToolCall,
    ToolDefinition,
    TokenUsage,
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMResponseError,
)

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini Provider（原生 SDK）

    构造参数
    --------
    api_key       : Google API Key（支持 AQ. 和 AIza 格式）
    model         : 模型标识符（如 "gemini-2.5-pro"）

    异常映射
    --------
    google.api_core.exceptions.Unauthenticated → LLMAuthError
    google.api_core.exceptions.ResourceExhausted → LLMRateLimitError
    google.api_core.exceptions.DeadlineExceeded → LLMTimeoutError
    google.api_core.exceptions.InvalidArgument → LLMResponseError
    其他异常 → LLMError
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-pro",
    ) -> None:
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError(
                "google-generativeai SDK 未安装，请运行: pip install google-generativeai"
            ) from exc

        genai.configure(api_key=api_key)
        self._genai = genai
        self._default_model = model
        self._api_key = api_key

        logger.debug("[Gemini] Provider 初始化完成，默认模型: %s", model)

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _build_gemini_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """将 Message 列表转换为 Gemini 格式。

        Gemini 格式：
        - role: "user" / "model"（assistant → model）
        - parts: [{"text": "..."}]
        """
        gemini_messages = []

        for msg in messages:
            # 跳过 system 消息（Gemini 通过 system_instruction 参数传递）
            if msg.role == "system":
                continue

            # 转换角色名称
            role = "model" if msg.role == "assistant" else msg.role

            # 构建 parts
            parts = []
            if msg.content:
                parts.append({"text": msg.content})

            # 工具调用结果（tool role）
            if msg.role == "tool" and msg.tool_call_id:
                # Gemini 使用 function_response 格式
                parts = [{
                    "function_response": {
                        "name": msg.tool_call_id,  # 使用 tool_call_id 作为函数名
                        "response": {"result": msg.content}
                    }
                }]

            # 助手的工具调用
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append({
                        "function_call": {
                            "name": tc.name,
                            "args": tc.arguments
                        }
                    })

            gemini_messages.append({
                "role": role,
                "parts": parts
            })

        return gemini_messages

    def _build_gemini_tools(self, tools: list[ToolDefinition]) -> list[Any]:
        """将 ToolDefinition 列表转换为 Gemini 工具格式。

        注意：Gemini 的 Schema 不支持某些 JSON Schema 字段（如 default, examples 等），
        需要清理这些字段。
        """
        from google.generativeai.types import FunctionDeclaration, Tool

        function_declarations = []

        for tool in tools:
            # 清理参数定义，移除 Gemini 不支持的字段
            parameters = tool.parameters or {"type": "object", "properties": {}}
            cleaned_params = self._clean_schema_for_gemini(parameters)

            func_decl = FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=cleaned_params
            )
            function_declarations.append(func_decl)

        return [Tool(function_declarations=function_declarations)] if function_declarations else []

    def _clean_schema_for_gemini(self, schema: dict[str, Any]) -> dict[str, Any]:
        """清理 JSON Schema，移除 Gemini 不支持的字段。

        Gemini 不支持的字段：
        - default
        - examples
        - additionalProperties
        - $schema
        - $ref
        """
        if not isinstance(schema, dict):
            return schema

        # 需要移除的字段
        unsupported_fields = {"default", "examples", "additionalProperties", "$schema", "$ref"}

        cleaned = {}
        for key, value in schema.items():
            if key in unsupported_fields:
                continue

            # 递归清理嵌套对象
            if isinstance(value, dict):
                cleaned[key] = self._clean_schema_for_gemini(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    self._clean_schema_for_gemini(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                cleaned[key] = value

        return cleaned

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        """非流式聊天。"""
        effective_model = model or self._default_model

        # 提取 system 消息
        system_instruction = None
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
                break

        # 构建消息和工具
        gemini_messages = self._build_gemini_messages(messages)
        gemini_tools = self._build_gemini_tools(tools) if tools else None

        try:
            # 创建模型实例
            model_instance = self._genai.GenerativeModel(
                model_name=effective_model,
                system_instruction=system_instruction,
                tools=gemini_tools,
            )

            # 生成配置
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }

            # 调用 API
            response = await asyncio.to_thread(
                model_instance.generate_content,
                gemini_messages,
                generation_config=generation_config,
            )

            # 解析响应
            content_text = ""
            tool_calls_list = []

            for part in response.parts:
                if hasattr(part, "text"):
                    content_text += part.text
                elif hasattr(part, "function_call"):
                    fc = part.function_call
                    tool_calls_list.append(ToolCall(
                        id=fc.name,  # Gemini 没有独立的 ID，使用函数名
                        name=fc.name,
                        arguments=dict(fc.args)
                    ))

            # Token 用量
            usage = TokenUsage(
                prompt_tokens=response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
                completion_tokens=response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
            )

            return LLMResponse(
                content=content_text,
                tool_calls=tool_calls_list if tool_calls_list else None,
                usage=usage,
                model=effective_model,
                stop_reason=response.candidates[0].finish_reason.name if response.candidates else "STOP",
            )

        except Exception as exc:
            raise self._map_exception(exc) from exc

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> AsyncIterator[StreamEvent]:
        """流式聊天。"""
        effective_model = model or self._default_model

        # 提取 system 消息
        system_instruction = None
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
                break

        # 构建消息和工具
        gemini_messages = self._build_gemini_messages(messages)
        gemini_tools = self._build_gemini_tools(tools) if tools else None

        try:
            # 创建模型实例
            model_instance = self._genai.GenerativeModel(
                model_name=effective_model,
                system_instruction=system_instruction,
                tools=gemini_tools,
            )

            # 生成配置
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }

            # 流式调用
            response_stream = await asyncio.to_thread(
                model_instance.generate_content,
                gemini_messages,
                generation_config=generation_config,
                stream=True,
            )

            # 流式处理
            accumulated_text = ""
            tool_calls_dict = {}
            input_tokens = 0
            output_tokens = 0

            for chunk in response_stream:
                # 处理文本增量
                if chunk.text:
                    accumulated_text += chunk.text
                    yield StreamEvent(event_type="text_delta", data=chunk.text)

                # 处理工具调用
                for part in chunk.parts:
                    if hasattr(part, "function_call"):
                        fc = part.function_call
                        tc = ToolCall(
                            id=fc.name,
                            name=fc.name,
                            arguments=dict(fc.args)
                        )

                        if fc.name not in tool_calls_dict:
                            tool_calls_dict[fc.name] = tc
                            yield StreamEvent(event_type="tool_call_start", data=tc)

                        yield StreamEvent(event_type="tool_call_end", data=tc)

                # 更新 token 用量
                if chunk.usage_metadata:
                    input_tokens = chunk.usage_metadata.prompt_token_count
                    output_tokens = chunk.usage_metadata.candidates_token_count

            # 发送用量和完成事件
            usage = TokenUsage(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
            yield StreamEvent(event_type="usage", data=usage)
            yield StreamEvent(event_type="done", data=None)

        except Exception as exc:
            error = self._map_exception(exc)
            yield StreamEvent(event_type="error", data=str(error))
            raise error from exc

    def _map_exception(self, exc: Exception) -> LLMError:
        """将 Google API 异常映射为 LLMError 子类。"""
        try:
            from google.api_core import exceptions as gcp_exceptions
        except ImportError:
            return LLMError(f"LLM 调用失败: {exc}", provider=self.provider_name, original_error=exc)

        if isinstance(exc, gcp_exceptions.Unauthenticated):
            return LLMAuthError(
                f"API Key 无效或权限不足: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )

        if isinstance(exc, gcp_exceptions.ResourceExhausted):
            return LLMRateLimitError(
                f"请求频率超限: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )

        if isinstance(exc, gcp_exceptions.DeadlineExceeded):
            return LLMTimeoutError(
                f"请求超时: {exc}",
                provider=self.provider_name,
                original_error=exc,
            )

        if isinstance(exc, gcp_exceptions.InvalidArgument):
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

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        """根据 token 用量与模型定价计算费用（美元）。

        Gemini 定价（2026年4月）：
        - gemini-2.0-flash: 输入 $0.10/M, 输出 $0.40/M
        - gemini-2.5-pro: 输入 $1.25/M, 输出 $5.00/M
        - gemini-1.5-pro: 输入 $1.25/M, 输出 $5.00/M
        - gemini-1.5-flash: 输入 $0.075/M, 输出 $0.30/M
        """
        # Gemini 定价表（美元/百万 tokens）
        pricing = {
            "gemini-2.0-flash": (0.10, 0.40),
            "gemini-2.5-pro": (1.25, 5.00),
            "gemini-1.5-pro": (1.25, 5.00),
            "gemini-1.5-flash": (0.075, 0.30),
        }

        model_key = model.lower()
        price_input, price_output = pricing.get(model_key, (1.25, 5.00))  # 默认使用 Pro 定价

        cost = (
            (usage.prompt_tokens / 1_000_000) * price_input
            + (usage.completion_tokens / 1_000_000) * price_output
        )
        return round(cost, 6)
