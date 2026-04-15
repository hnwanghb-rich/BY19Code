"""BY19Code LLM 适配层基类【T04】

设计原则
--------
- 与具体 SDK（anthropic / openai）零耦合：本模块不 import 任何第三方 LLM 库
- 统一数据模型：所有 Provider 共用同一套 Message / ToolCall / StreamEvent
- 新增模型只需继承 LLMProvider 并实现三个抽象方法
- 异常体系：LLMError 基类 + 四种具体子类，Provider 内部捕获 SDK 异常后转换

模块内容
--------
  数据模型  : ToolCall / ToolDefinition / TokenUsage / Message / LLMResponse / StreamEvent
  抽象基类  : LLMProvider
  异常体系  : LLMError / LLMAuthError / LLMRateLimitError / LLMTimeoutError / LLMResponseError
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    """LLM 返回的工具调用实例

    字段说明
    --------
    id        : 工具调用唯一 ID（Claude 用 tool_use_id；OpenAI 用 call_id）
    name      : 工具名称，对应 ToolDefinition.name
    arguments : LLM 生成的参数 dict（JSON 反序列化后）
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    """传给 LLM 的工具定义（即"工具说明书"）

    字段说明
    --------
    name        : 工具名称，如 "read_file"
    description : 工具功能描述（提供给 LLM 理解用途）
    parameters  : JSON Schema 格式的参数定义 dict
                  示例：{"type": "object", "properties": {"path": {"type": "string"}},
                         "required": ["path"]}
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Token 用量统计（一次 LLM 调用的消耗）

    字段说明
    --------
    prompt_tokens     : 输入（prompt）token 数
    completion_tokens : 输出（completion）token 数
    total_tokens      : 总 token 数；为 0 时自动计算为 prompt + completion
    estimated_cost    : 估算费用（美元），由 Provider.calculate_cost() 填充
    """

    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0

    @model_validator(mode="after")
    def _auto_compute_total(self) -> "TokenUsage":
        """total_tokens 为 0 时自动计算为 prompt + completion"""
        if self.total_tokens == 0 and (self.prompt_tokens or self.completion_tokens):
            self.total_tokens = self.prompt_tokens + self.completion_tokens
        return self


class Message(BaseModel):
    """统一消息格式，覆盖 Anthropic / OpenAI 两种 API 格式

    role 说明
    ---------
    system    : 系统提示词（对话开头）
    user      : 用户输入
    assistant : AI 回复（可能含 tool_calls）
    tool      : 工具执行结果（需配合 tool_call_id 指向哪次工具调用）

    字段说明
    --------
    content      : 文本内容；tool 角色填写工具执行结果
    tool_calls   : 仅 assistant 角色使用，列出本次调用的工具
    tool_call_id : 仅 tool 角色使用，指向被响应的 ToolCall.id
    """

    model_config = ConfigDict(extra="ignore")

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        """是否包含工具调用（assistant 角色使用）"""
        return bool(self.tool_calls)


class LLMResponse(BaseModel):
    """LLM 非流式调用的完整响应

    字段说明
    --------
    content     : 文本回复内容（可能为空，若 LLM 仅返回 tool_calls）
    tool_calls  : 工具调用列表（LLM 需要调用工具时填充）
    usage       : 本次调用的 token 用量
    model       : 实际使用的模型标识符（provider 可能重写默认模型）
    stop_reason : 停止原因（"end_turn" / "max_tokens" / "tool_use" / "stop" 等）
    """

    model_config = ConfigDict(extra="ignore")

    content: str = ""
    tool_calls: list[ToolCall] | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    model: str = ""
    stop_reason: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        """是否包含工具调用"""
        return bool(self.tool_calls)

    @property
    def is_complete(self) -> bool:
        """是否为纯文本回复（无待执行工具调用）"""
        return not self.has_tool_calls


# 流事件类型字面量
StreamEventType = Literal[
    "text_delta",       # 新文本块（data: str）
    "tool_call_start",  # 工具调用开始（data: ToolCall，arguments 可能为空 dict）
    "tool_call_delta",  # 工具调用参数增量（data: str，JSON 片段）
    "tool_call_end",    # 工具调用完整结束（data: ToolCall，含完整 arguments）
    "usage",            # Token 用量（data: TokenUsage）
    "done",             # 响应完全结束（data: LLMResponse | None）
    "error",            # 发生错误（data: str 错误信息）
]


class StreamEvent(BaseModel):
    """流式响应事件单元

    event_type → data 类型对应关系
    --------------------------------
    "text_delta"      → str
    "tool_call_start" → ToolCall（arguments 可能为空 dict，流式积累中）
    "tool_call_delta" → str（arguments JSON 增量片段）
    "tool_call_end"   → ToolCall（arguments 已完整）
    "usage"           → TokenUsage
    "done"            → LLMResponse | None
    "error"           → str（错误描述）

    用法示例
    --------
    async for event in provider.stream_chat(messages):
        match event.event_type:
            case "text_delta":
                print(event.data, end="", flush=True)
            case "tool_call_end":
                handle_tool(event.data)   # ToolCall
            case "usage":
                record_cost(event.data)   # TokenUsage
            case "done":
                break
    """

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    event_type: StreamEventType
    # data 类型随 event_type 变化，详见类文档注释
    data: Any = None


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """LLM Provider 抽象基类

    所有具体 Provider（ClaudeProvider / OpenAIProvider 等）必须继承此类
    并实现三个抽象成员：provider_name / chat / stream_chat / calculate_cost。

    设计约束
    --------
    - 不直接 import anthropic / openai，解耦具体 SDK
    - 所有方法标注完整 type hint
    - chat() 为非流式接口；stream_chat() 为流式接口（async generator）
    - calculate_cost() 根据模型定价计算费用，供 TokenTracker 调用

    异常约定
    --------
    所有实现必须将 SDK 原生异常转换为本模块定义的 LLMError 子类后抛出。
    """

    # ------------------------------------------------------------------
    # 只读属性
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 标识名，小写字母，如 "claude" / "deepseek"（只读）"""
        ...

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        """非流式聊天，等待 LLM 生成完整响应后一次性返回。

        参数
        ----
        messages    : 对话历史列表（含 system prompt）；角色顺序须符合对应 API 要求
        tools       : 可用工具定义；为 None 时不启用 tool use
        model       : 覆盖 Provider 默认模型；为 None 时使用配置中的 model 字段
        temperature : 采样温度，范围 0.0（确定性）~ 1.0（随机）
        max_tokens  : 最大输出 token 数，防止无限生成

        返回
        ----
        LLMResponse : 完整响应（content / tool_calls / usage / stop_reason）

        异常
        ----
        LLMAuthError      : API Key 无效或权限不足
        LLMRateLimitError : 请求频率超过限制
        LLMTimeoutError   : 请求超时（建议设置 30s）
        LLMResponseError  : 响应格式解析失败
        """
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> AsyncIterator[StreamEvent]:
        """流式聊天接口，逐块产出 StreamEvent。

        子类应实现为 async generator（async def + yield）：

            async def stream_chat(self, messages, ...) -> AsyncIterator[StreamEvent]:
                async for chunk in sdk_stream:
                    yield StreamEvent(event_type="text_delta", data=chunk.text)
                yield StreamEvent(event_type="done", data=response)

        调用方式（无需 await，直接迭代）：

            async for event in provider.stream_chat(messages):
                if event.event_type == "text_delta":
                    print(event.data, end="")

        异常：与 chat() 相同，在迭代过程中可能抛出 LLMError 子类。
        """
        # 使此抽象方法成为 async generator stub，子类需覆盖
        raise NotImplementedError(f"{type(self).__name__} 未实现 stream_chat()")
        yield  # type: ignore[misc]  # noqa: unreachable — 让 Python 识别为 async generator

    @abstractmethod
    def calculate_cost(
        self,
        usage: TokenUsage,
        model: str,
    ) -> float:
        """根据 token 用量与模型定价计算本次调用费用（美元）。

        计算公式（参考 PRD §7）：
          cost = (prompt_tokens / 1000) * price_per_1k_input
               + (completion_tokens / 1000) * price_per_1k_output

        参数
        ----
        usage : 包含 prompt_tokens 和 completion_tokens 的用量对象
        model : 模型标识符（不同 model 定价不同）

        返回
        ----
        float : 费用（美元），精度到小数点后 6 位
        """
        ...


# ---------------------------------------------------------------------------
# 异常体系
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """LLM 调用基础异常

    所有 Provider 抛出的异常必须是此类或其子类。
    上层代码只需 except LLMError 即可统一捕获。

    属性
    ----
    provider       : 抛出异常的 Provider 名称（如 "claude"）
    original_error : 原始 SDK 异常（可选），便于调试
    """

    def __init__(
        self,
        message: str,
        provider: str = "",
        original_error: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error

    def __str__(self) -> str:
        prefix = f"[{self.provider}] " if self.provider else ""
        return f"{prefix}{super().__str__()}"


class LLMAuthError(LLMError):
    """API Key 无效或权限不足

    触发场景：HTTP 401 / 403，或 SDK 抛出 AuthenticationError。
    处理建议：提示用户检查 .env 中的 API Key 配置。
    """


class LLMRateLimitError(LLMError):
    """请求频率超过 API 限制（Rate Limit）

    触发场景：HTTP 429，或 SDK 抛出 RateLimitError。
    处理建议：指数退避后重试（1s → 2s → 4s，最多 3 次）。

    属性
    ----
    retry_after : API 建议的等待时间（秒）；None 表示未提供
    """

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        # API 建议的等待秒数（来自 Retry-After 响应头）
        self.retry_after = retry_after


class LLMTimeoutError(LLMError):
    """请求超时

    触发场景：SDK 抛出 Timeout / ConnectTimeout，或 asyncio.TimeoutError。
    处理建议：同 Rate Limit，指数退避后重试。
    """


class LLMResponseError(LLMError):
    """LLM 响应解析失败

    触发场景：
    - JSON 解析失败
    - 响应格式与预期不符（如缺少必要字段）
    - tool_call arguments 不是合法 JSON

    处理建议：记录原始响应内容后向上抛出，不应重试。
    """
