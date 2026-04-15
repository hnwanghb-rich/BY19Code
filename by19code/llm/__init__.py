"""by19code LLM 适配层包【T07】

导出层级
--------
  抽象基类  : LLMProvider
  工厂      : LLMFactory, switch_provider
  具体实现  : ClaudeProvider, OpenAICompatibleProvider
  数据模型  : Message, ToolCall, ToolDefinition, TokenUsage, LLMResponse, StreamEvent
  类型别名  : StreamEventType
  异常体系  : LLMError, LLMAuthError, LLMRateLimitError, LLMTimeoutError, LLMResponseError

典型用法
--------
  from by19code.llm import LLMFactory, LLMProvider, LLMError
  from by19code.llm import Message, LLMResponse, StreamEvent

  provider = LLMFactory.create(config)
  response = await provider.chat(messages)

  # 运行时切换
  from by19code.llm import switch_provider
  provider = switch_provider("deepseek", config)
"""
from __future__ import annotations

# 数据模型与抽象基类（无第三方 SDK 依赖）
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
    StreamEventType,
    ToolCall,
    ToolDefinition,
    TokenUsage,
)

# 具体 Provider 实现（SDK 在各自 __init__ 内部延迟导入）
from by19code.llm.claude_provider import ClaudeProvider
from by19code.llm.openai_provider import OpenAICompatibleProvider

# 工厂与切换函数
from by19code.llm.factory import LLMFactory, switch_provider

__all__ = [
    # 抽象基类
    "LLMProvider",
    # 工厂
    "LLMFactory",
    "switch_provider",
    # 具体 Provider
    "ClaudeProvider",
    "OpenAICompatibleProvider",
    # 数据模型
    "Message",
    "ToolCall",
    "ToolDefinition",
    "TokenUsage",
    "LLMResponse",
    "StreamEvent",
    "StreamEventType",
    # 异常体系
    "LLMError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMResponseError",
]
