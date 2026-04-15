"""by19code.llm.claude_provider 单元测试【T05】

测试分组
--------
  TestCalculateCost         - calculate_cost() 定价表与公式
  TestBuildApiMessages      - _build_api_messages() 消息格式转换
  TestBuildApiTools         - _build_api_tools() 工具定义转换
  TestParseResponse         - _parse_response() 响应解析
  TestMapException          - _map_exception() 异常映射
  TestChatSuccess           - chat() 正常路径
  TestChatRetry             - chat() 重试逻辑（RateLimit / Timeout / Connection）
  TestChatExceptions        - chat() 非重试异常直接抛出
  TestStreamChat            - stream_chat() 流式事件映射
  TestStreamChatExceptions  - stream_chat() 流式错误处理

全部 async 测试由 anyio（asyncio 后端）驱动。
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 处理 Windows 事件循环策略（Python 3.12 目标，3.14 已弃用）
if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

pytestmark = pytest.mark.anyio

# ---------------------------------------------------------------------------
# 辅助：伪造 anthropic 模块
# ---------------------------------------------------------------------------

def _make_fake_anthropic() -> MagicMock:
    """构造一个最小化的 fake anthropic 模块，含 SDK 异常类和 AsyncAnthropic"""
    fa = MagicMock(name="fake_anthropic")

    # 异常类（必须是真实的 Exception 子类）
    class AuthenticationError(Exception): pass
    class RateLimitError(Exception):
        def __init__(self, msg="", response=None):
            super().__init__(msg)
            self.response = response
    class APITimeoutError(Exception): pass
    class APIConnectionError(Exception): pass
    class BadRequestError(Exception): pass
    class APIError(Exception): pass

    fa.AuthenticationError = AuthenticationError
    fa.RateLimitError = RateLimitError
    fa.APITimeoutError = APITimeoutError
    fa.APIConnectionError = APIConnectionError
    fa.BadRequestError = BadRequestError
    fa.APIError = APIError

    fa.AsyncAnthropic = MagicMock()
    return fa


def _make_provider(fake_anthropic: MagicMock) -> Any:
    """在 fake_anthropic 注入的环境下构造 ClaudeProvider"""
    with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        from importlib import reload
        import by19code.llm.claude_provider as mod
        reload(mod)
        provider = mod.ClaudeProvider.__new__(mod.ClaudeProvider)
        provider._anthropic = fake_anthropic
        provider._default_model = "claude-sonnet-4-20250514"
        provider._client = fake_anthropic.AsyncAnthropic.return_value
        return provider, mod


# ---------------------------------------------------------------------------
# 辅助：伪造 Anthropic 流事件
# ---------------------------------------------------------------------------

def _text_event(text: str, index: int = 0) -> MagicMock:
    """content_block_delta(text_delta)"""
    e = MagicMock()
    e.type = "content_block_delta"
    e.index = index
    e.delta = MagicMock()
    e.delta.type = "text_delta"
    e.delta.text = text
    return e


def _tool_start_event(index: int, tool_id: str, tool_name: str) -> MagicMock:
    """content_block_start(tool_use)"""
    e = MagicMock()
    e.type = "content_block_start"
    e.index = index
    e.content_block = MagicMock()
    e.content_block.type = "tool_use"
    e.content_block.id = tool_id
    e.content_block.name = tool_name
    return e


def _tool_delta_event(index: int, partial_json: str) -> MagicMock:
    """content_block_delta(input_json_delta)"""
    e = MagicMock()
    e.type = "content_block_delta"
    e.index = index
    e.delta = MagicMock()
    e.delta.type = "input_json_delta"
    e.delta.partial_json = partial_json
    return e


def _tool_stop_event(index: int) -> MagicMock:
    """content_block_stop（工具块结束）"""
    e = MagicMock()
    e.type = "content_block_stop"
    e.index = index
    return e


def _message_start_event(input_tokens: int) -> MagicMock:
    """message_start（含 input_tokens）"""
    e = MagicMock()
    e.type = "message_start"
    e.message = MagicMock()
    e.message.usage = MagicMock()
    e.message.usage.input_tokens = input_tokens
    return e


def _message_delta_event(output_tokens: int, stop_reason: str = "end_turn") -> MagicMock:
    """message_delta（含 output_tokens 和 stop_reason）"""
    e = MagicMock()
    e.type = "message_delta"
    e.usage = MagicMock()
    e.usage.output_tokens = output_tokens
    e.delta = MagicMock()
    e.delta.stop_reason = stop_reason
    return e


def _message_stop_event() -> MagicMock:
    """message_stop"""
    e = MagicMock()
    e.type = "message_stop"
    return e


class _FakeStream:
    """模拟 anthropic client.messages.stream() async context manager"""

    def __init__(self, events: list[MagicMock]) -> None:
        self._events = events

    async def __aenter__(self) -> "_FakeStream":
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    def __aiter__(self) -> AsyncIterator[MagicMock]:
        return self._async_gen()

    async def _async_gen(self) -> AsyncIterator[MagicMock]:
        for ev in self._events:
            yield ev


# ---------------------------------------------------------------------------
# 辅助：伪造 anthropic.Message 响应（非流式）
# ---------------------------------------------------------------------------

def _make_text_response(
    text: str,
    model: str = "claude-sonnet-4-20250514",
    stop_reason: str = "end_turn",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> MagicMock:
    resp = MagicMock()
    resp.model = model
    resp.stop_reason = stop_reason

    block = MagicMock()
    block.type = "text"
    block.text = text
    resp.content = [block]

    resp.usage = MagicMock()
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    return resp


def _make_tool_response(
    tool_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
    model: str = "claude-sonnet-4-20250514",
    input_tokens: int = 200,
    output_tokens: int = 80,
) -> MagicMock:
    resp = MagicMock()
    resp.model = model
    resp.stop_reason = "tool_use"

    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = tool_name
    block.input = tool_input
    resp.content = [block]

    resp.usage = MagicMock()
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    return resp


# ---------------------------------------------------------------------------
# Fixture：provider
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_anthropic() -> MagicMock:
    return _make_fake_anthropic()


@pytest.fixture
def provider_and_mod(fake_anthropic: MagicMock):
    with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        from importlib import reload
        import by19code.llm.claude_provider as mod
        reload(mod)
        # 使用真实构造器（__init__ 会 import anthropic）
        prov = mod.ClaudeProvider(api_key="sk-test", model="claude-sonnet-4-20250514")
        prov._anthropic = fake_anthropic
        prov._client = MagicMock()
        return prov, mod


@pytest.fixture
def provider(provider_and_mod):
    return provider_and_mod[0]


# ---------------------------------------------------------------------------
# 1. calculate_cost
# ---------------------------------------------------------------------------

class TestCalculateCost:
    def test_sonnet_price(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        cost = provider.calculate_cost(usage, "claude-sonnet-4-20250514")
        assert abs(cost - 18.0) < 1e-6  # 3.0 + 15.0

    def test_haiku_price(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        cost = provider.calculate_cost(usage, "claude-haiku-4-5-20251001")
        assert abs(cost - 4.8) < 1e-6  # 0.80 + 4.0

    def test_zero_tokens(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=0, completion_tokens=0)
        assert provider.calculate_cost(usage, "claude-sonnet-4-20250514") == 0.0

    def test_unknown_model_uses_default(self, provider):
        """未知模型使用 _DEFAULT_PRICE（sonnet 价格）"""
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        cost = provider.calculate_cost(usage, "unknown-model-xyz")
        assert abs(cost - 18.0) < 1e-6

    def test_small_token_count(self, provider):
        """1000 token 费用约 $0.003"""
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=0)
        cost = provider.calculate_cost(usage, "claude-sonnet-4-20250514")
        assert abs(cost - 0.003) < 1e-9

    def test_case_insensitive_model(self, provider):
        """模型名不区分大小写"""
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=0)
        cost_lower = provider.calculate_cost(usage, "claude-sonnet-4-20250514")
        cost_upper = provider.calculate_cost(usage, "CLAUDE-SONNET-4-20250514")
        assert abs(cost_lower - cost_upper) < 1e-9

    def test_haiku_model_alias(self, provider):
        """claude-haiku-4-5 短名同价"""
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=0)
        c1 = provider.calculate_cost(usage, "claude-haiku-4-5")
        c2 = provider.calculate_cost(usage, "claude-haiku-4-5-20251001")
        assert abs(c1 - c2) < 1e-9


# ---------------------------------------------------------------------------
# 2. _build_api_messages
# ---------------------------------------------------------------------------

class TestBuildApiMessages:
    def test_empty_messages(self, provider_and_mod):
        prov, mod = provider_and_mod
        system, msgs = prov._build_api_messages([])
        assert system == ""
        assert msgs == []

    def test_system_message_extracted(self, provider_and_mod):
        from by19code.llm.base import Message
        prov, _ = provider_and_mod
        messages = [
            Message(role="system", content="你是助手"),
            Message(role="user", content="你好"),
        ]
        system, msgs = prov._build_api_messages(messages)
        assert system == "你是助手"
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "你好"

    def test_last_system_wins(self, provider_and_mod):
        """多条 system 消息取最后一条"""
        from by19code.llm.base import Message
        prov, _ = provider_and_mod
        messages = [
            Message(role="system", content="第一条"),
            Message(role="system", content="第二条"),
            Message(role="user", content="问题"),
        ]
        system, _ = prov._build_api_messages(messages)
        assert system == "第二条"

    def test_user_message(self, provider_and_mod):
        from by19code.llm.base import Message
        prov, _ = provider_and_mod
        messages = [Message(role="user", content="hello")]
        _, msgs = prov._build_api_messages(messages)
        assert msgs[0] == {"role": "user", "content": "hello"}

    def test_assistant_text_only(self, provider_and_mod):
        from by19code.llm.base import Message
        prov, _ = provider_and_mod
        messages = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="world"),
        ]
        _, msgs = prov._build_api_messages(messages)
        asst = msgs[1]
        assert asst["role"] == "assistant"
        assert asst["content"][0] == {"type": "text", "text": "world"}

    def test_assistant_with_tool_calls(self, provider_and_mod):
        from by19code.llm.base import Message, ToolCall
        prov, _ = provider_and_mod
        tc = ToolCall(id="t1", name="read_file", arguments={"path": "/tmp/f"})
        messages = [
            Message(role="user", content="读文件"),
            Message(role="assistant", content="好的", tool_calls=[tc]),
        ]
        _, msgs = prov._build_api_messages(messages)
        content_blocks = msgs[1]["content"]
        types = [b["type"] for b in content_blocks]
        assert "text" in types
        assert "tool_use" in types
        tool_block = next(b for b in content_blocks if b["type"] == "tool_use")
        assert tool_block["id"] == "t1"
        assert tool_block["name"] == "read_file"
        assert tool_block["input"] == {"path": "/tmp/f"}

    def test_tool_results_grouped_into_user_message(self, provider_and_mod):
        """多条连续 tool 消息合并为单条 user 消息"""
        from by19code.llm.base import Message, ToolCall
        prov, _ = provider_and_mod
        messages = [
            Message(role="user", content="执行工具"),
            Message(role="assistant", content="", tool_calls=[
                ToolCall(id="t1", name="tool_a", arguments={}),
                ToolCall(id="t2", name="tool_b", arguments={}),
            ]),
            Message(role="tool", content="结果A", tool_call_id="t1"),
            Message(role="tool", content="结果B", tool_call_id="t2"),
        ]
        _, msgs = prov._build_api_messages(messages)
        # 最后一条应为合并的 user 消息
        last = msgs[-1]
        assert last["role"] == "user"
        assert len(last["content"]) == 2
        assert all(b["type"] == "tool_result" for b in last["content"])
        ids = [b["tool_use_id"] for b in last["content"]]
        assert "t1" in ids and "t2" in ids

    def test_no_system_no_tools(self, provider_and_mod):
        from by19code.llm.base import Message
        prov, _ = provider_and_mod
        messages = [Message(role="user", content="hello")]
        system, msgs = prov._build_api_messages(messages)
        assert system == ""
        assert len(msgs) == 1

    def test_assistant_no_content_gets_empty_text_block(self, provider_and_mod):
        """assistant 消息无文本内容时仍生成空 text 块（API 要求至少一个块）"""
        from by19code.llm.base import Message, ToolCall
        prov, _ = provider_and_mod
        tc = ToolCall(id="t1", name="f", arguments={})
        messages = [
            Message(role="user", content="go"),
            Message(role="assistant", content="", tool_calls=[tc]),
        ]
        _, msgs = prov._build_api_messages(messages)
        asst_content = msgs[1]["content"]
        # 因为 content="" 被判为 falsy，只有 tool_use 块
        tool_blocks = [b for b in asst_content if b["type"] == "tool_use"]
        assert len(tool_blocks) == 1


# ---------------------------------------------------------------------------
# 3. _build_api_tools
# ---------------------------------------------------------------------------

class TestBuildApiTools:
    def test_empty_tools(self, provider):
        result = provider._build_api_tools([])
        assert result == []

    def test_single_tool(self, provider):
        from by19code.llm.base import ToolDefinition
        td = ToolDefinition(
            name="read_file",
            description="读取文件内容",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )
        result = provider._build_api_tools([td])
        assert len(result) == 1
        assert result[0]["name"] == "read_file"
        assert result[0]["description"] == "读取文件内容"
        assert result[0]["input_schema"] == td.parameters

    def test_tool_no_parameters_gets_default_schema(self, provider):
        """无参数定义时 input_schema 为空 object"""
        from by19code.llm.base import ToolDefinition
        td = ToolDefinition(name="ping", description="测试连通性")
        result = provider._build_api_tools([td])
        assert result[0]["input_schema"] == {"type": "object", "properties": {}}

    def test_multiple_tools(self, provider):
        from by19code.llm.base import ToolDefinition
        tools = [
            ToolDefinition(name=f"tool_{i}", description=f"工具{i}")
            for i in range(5)
        ]
        result = provider._build_api_tools(tools)
        assert len(result) == 5
        assert [r["name"] for r in result] == [f"tool_{i}" for i in range(5)]


# ---------------------------------------------------------------------------
# 4. _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_text_only(self, provider):
        resp = _make_text_response("你好", input_tokens=100, output_tokens=50)
        result = provider._parse_response(resp)
        assert result.content == "你好"
        assert result.tool_calls is None
        assert result.usage.prompt_tokens == 100
        assert result.usage.completion_tokens == 50
        assert result.usage.total_tokens == 150
        assert result.stop_reason == "end_turn"

    def test_tool_use_response(self, provider):
        resp = _make_tool_response(
            "toolu_01", "read_file", {"path": "/tmp/test.py"},
            input_tokens=200, output_tokens=80,
        )
        result = provider._parse_response(resp)
        assert result.content == ""
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.id == "toolu_01"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/tmp/test.py"}
        assert result.stop_reason == "tool_use"

    def test_mixed_text_and_tool(self, provider):
        """文本块 + 工具调用块共存"""
        resp = MagicMock()
        resp.model = "claude-sonnet-4-20250514"
        resp.stop_reason = "tool_use"
        resp.usage = MagicMock()
        resp.usage.input_tokens = 300
        resp.usage.output_tokens = 100

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "我来帮你"

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "toolu_02"
        tool_block.name = "list_files"
        tool_block.input = {"dir": "/tmp"}

        resp.content = [text_block, tool_block]

        result = provider._parse_response(resp)
        assert result.content == "我来帮你"
        assert result.tool_calls is not None
        assert result.tool_calls[0].name == "list_files"

    def test_empty_content(self, provider):
        resp = MagicMock()
        resp.model = "claude-sonnet-4-20250514"
        resp.stop_reason = "end_turn"
        resp.content = []
        resp.usage = MagicMock()
        resp.usage.input_tokens = 10
        resp.usage.output_tokens = 5
        result = provider._parse_response(resp)
        assert result.content == ""
        assert result.tool_calls is None

    def test_model_name_propagated(self, provider):
        resp = _make_text_response("hi", model="claude-haiku-4-5-20251001")
        result = provider._parse_response(resp)
        assert result.model == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# 5. _map_exception
# ---------------------------------------------------------------------------

class TestMapException:
    def test_auth_error(self, provider, fake_anthropic):
        exc = fake_anthropic.AuthenticationError("Invalid API key")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMAuthError
        assert isinstance(mapped, LLMAuthError)
        assert mapped.provider == "claude"
        assert mapped.original_error is exc

    def test_rate_limit_error(self, provider, fake_anthropic):
        exc = fake_anthropic.RateLimitError("Rate limit exceeded")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMRateLimitError
        assert isinstance(mapped, LLMRateLimitError)

    def test_rate_limit_with_retry_after(self, provider, fake_anthropic):
        mock_response = MagicMock()
        mock_response.headers = {"retry-after": "30"}
        exc = fake_anthropic.RateLimitError("rate", response=mock_response)
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMRateLimitError
        assert isinstance(mapped, LLMRateLimitError)
        assert mapped.retry_after == 30.0

    def test_timeout_error(self, provider, fake_anthropic):
        exc = fake_anthropic.APITimeoutError("timeout")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMTimeoutError
        assert isinstance(mapped, LLMTimeoutError)

    def test_connection_error(self, provider, fake_anthropic):
        exc = fake_anthropic.APIConnectionError("connection failed")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMTimeoutError
        assert isinstance(mapped, LLMTimeoutError)

    def test_bad_request_error(self, provider, fake_anthropic):
        exc = fake_anthropic.BadRequestError("bad request")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMResponseError
        assert isinstance(mapped, LLMResponseError)

    def test_unknown_error(self, provider, fake_anthropic):
        exc = RuntimeError("unexpected")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMError
        assert isinstance(mapped, LLMError)
        assert mapped.provider == "claude"

    def test_str_contains_provider(self, provider, fake_anthropic):
        exc = fake_anthropic.AuthenticationError("bad key")
        mapped = provider._map_exception(exc)
        assert "[claude]" in str(mapped).lower()


# ---------------------------------------------------------------------------
# 6. chat() 正常路径
# ---------------------------------------------------------------------------

class TestChatSuccess:
    async def test_text_response(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_text_response("你好！", input_tokens=100, output_tokens=40)
        provider._client.messages.create = AsyncMock(return_value=resp_mock)

        messages = [Message(role="user", content="你好")]
        result = await provider.chat(messages)

        assert result.content == "你好！"
        assert result.tool_calls is None
        assert result.usage.prompt_tokens == 100
        assert result.usage.completion_tokens == 40
        assert result.usage.total_tokens == 140

    async def test_cost_calculated(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_text_response(
            "ok", input_tokens=1_000_000, output_tokens=1_000_000
        )
        provider._client.messages.create = AsyncMock(return_value=resp_mock)

        result = await provider.chat([Message(role="user", content="test")])
        # sonnet: 3+15 = 18$/MTok * 2MTok
        assert abs(result.usage.estimated_cost - 18.0) < 1e-6

    async def test_system_message_passed(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_text_response("hi")
        provider._client.messages.create = AsyncMock(return_value=resp_mock)

        messages = [
            Message(role="system", content="你是专业助手"),
            Message(role="user", content="你好"),
        ]
        await provider.chat(messages)

        call_kwargs = provider._client.messages.create.call_args.kwargs
        assert call_kwargs.get("system") == "你是专业助手"

    async def test_no_system_no_system_kwarg(self, provider):
        """无 system 消息时不传 system 参数"""
        from by19code.llm.base import Message
        resp_mock = _make_text_response("hi")
        provider._client.messages.create = AsyncMock(return_value=resp_mock)

        await provider.chat([Message(role="user", content="hi")])

        call_kwargs = provider._client.messages.create.call_args.kwargs
        assert "system" not in call_kwargs

    async def test_tools_passed(self, provider):
        from by19code.llm.base import Message, ToolDefinition
        resp_mock = _make_text_response("ok")
        provider._client.messages.create = AsyncMock(return_value=resp_mock)

        tools = [ToolDefinition(name="ping", description="test")]
        await provider.chat([Message(role="user", content="go")], tools=tools)

        call_kwargs = provider._client.messages.create.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["name"] == "ping"

    async def test_model_override(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_text_response("ok", model="claude-haiku-4-5-20251001")
        provider._client.messages.create = AsyncMock(return_value=resp_mock)

        await provider.chat(
            [Message(role="user", content="hi")],
            model="claude-haiku-4-5-20251001",
        )

        call_kwargs = provider._client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    async def test_tool_call_response(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_tool_response("t1", "read_file", {"path": "/tmp/a"})
        provider._client.messages.create = AsyncMock(return_value=resp_mock)

        result = await provider.chat([Message(role="user", content="读文件")])
        assert result.has_tool_calls
        assert result.tool_calls[0].name == "read_file"


# ---------------------------------------------------------------------------
# 7. chat() 重试逻辑
# ---------------------------------------------------------------------------

class TestChatRetry:
    async def test_rate_limit_retries_three_times(self, provider, fake_anthropic):
        """RateLimitError 重试 3 次均失败后抛出 LLMRateLimitError"""
        from by19code.llm.base import LLMRateLimitError

        provider._client.messages.create = AsyncMock(
            side_effect=fake_anthropic.RateLimitError("429")
        )

        with patch("by19code.llm.claude_provider.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(LLMRateLimitError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        # 3 次尝试 → 2 次 sleep（第 3 次失败后不 sleep）
        assert mock_sleep.call_count == 2

    async def test_retry_sleep_durations(self, provider, fake_anthropic):
        """重试等待时间为 1s、2s"""
        from by19code.llm.base import LLMRateLimitError

        provider._client.messages.create = AsyncMock(
            side_effect=fake_anthropic.RateLimitError("429")
        )

        sleep_durations: list[float] = []

        async def fake_sleep(secs: float) -> None:
            sleep_durations.append(secs)

        with patch("by19code.llm.claude_provider.asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(LLMRateLimitError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        assert sleep_durations == [1.0, 2.0]

    async def test_retry_succeeds_on_second_attempt(self, provider, fake_anthropic):
        """第一次 RateLimitError，第二次成功"""
        resp_mock = _make_text_response("成功")
        provider._client.messages.create = AsyncMock(
            side_effect=[
                fake_anthropic.RateLimitError("429"),
                resp_mock,
            ]
        )

        with patch("by19code.llm.claude_provider.asyncio.sleep", new_callable=AsyncMock):
            from by19code.llm.base import Message
            result = await provider.chat([Message(role="user", content="hi")])

        assert result.content == "成功"
        assert provider._client.messages.create.call_count == 2

    async def test_timeout_error_retries(self, provider, fake_anthropic):
        """APITimeoutError 也触发重试"""
        from by19code.llm.base import LLMTimeoutError

        provider._client.messages.create = AsyncMock(
            side_effect=fake_anthropic.APITimeoutError("timeout")
        )

        with patch("by19code.llm.claude_provider.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMTimeoutError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        assert provider._client.messages.create.call_count == 3

    async def test_connection_error_retries(self, provider, fake_anthropic):
        """APIConnectionError 也触发重试"""
        from by19code.llm.base import LLMTimeoutError

        provider._client.messages.create = AsyncMock(
            side_effect=fake_anthropic.APIConnectionError("conn failed")
        )

        with patch("by19code.llm.claude_provider.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMTimeoutError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])


# ---------------------------------------------------------------------------
# 8. chat() 非重试异常
# ---------------------------------------------------------------------------

class TestChatExceptions:
    async def test_auth_error_not_retried(self, provider, fake_anthropic):
        """AuthenticationError 不重试，直接抛出 LLMAuthError"""
        from by19code.llm.base import LLMAuthError

        provider._client.messages.create = AsyncMock(
            side_effect=fake_anthropic.AuthenticationError("bad key")
        )

        with patch("by19code.llm.claude_provider.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(LLMAuthError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        # 没有 sleep
        mock_sleep.assert_not_called()
        # 只尝试一次
        assert provider._client.messages.create.call_count == 1

    async def test_bad_request_not_retried(self, provider, fake_anthropic):
        """BadRequestError 不重试，映射为 LLMResponseError"""
        from by19code.llm.base import LLMResponseError

        provider._client.messages.create = AsyncMock(
            side_effect=fake_anthropic.BadRequestError("bad req")
        )

        with patch("by19code.llm.claude_provider.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMResponseError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        assert provider._client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# 9. stream_chat() 流式事件映射
# ---------------------------------------------------------------------------

class TestStreamChat:
    async def test_text_stream(self, provider):
        """纯文本流：text_delta → usage → done"""
        from by19code.llm.base import Message, StreamEvent, TokenUsage, LLMResponse

        events = [
            _message_start_event(input_tokens=100),
            _text_event("Hello"),
            _text_event(", World"),
            _message_delta_event(output_tokens=10),
            _message_stop_event(),
        ]

        provider._client.messages.stream = MagicMock(return_value=_FakeStream(events))

        collected: list[StreamEvent] = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        types = [e.event_type for e in collected]
        assert "text_delta" in types
        assert "usage" in types
        assert "done" in types

        text_parts = [e.data for e in collected if e.event_type == "text_delta"]
        assert "".join(text_parts) == "Hello, World"

        usage_ev = next(e for e in collected if e.event_type == "usage")
        assert isinstance(usage_ev.data, TokenUsage)
        assert usage_ev.data.prompt_tokens == 100
        assert usage_ev.data.completion_tokens == 10

        done_ev = next(e for e in collected if e.event_type == "done")
        assert isinstance(done_ev.data, LLMResponse)
        assert done_ev.data.content == "Hello, World"

    async def test_tool_call_stream(self, provider):
        """工具调用流：tool_call_start → tool_call_delta → tool_call_end"""
        from by19code.llm.base import Message, ToolCall

        events = [
            _message_start_event(input_tokens=200),
            _tool_start_event(0, "toolu_01", "read_file"),
            _tool_delta_event(0, '{"path":'),
            _tool_delta_event(0, ' "/tmp/a"}'),
            _tool_stop_event(0),
            _message_delta_event(output_tokens=50, stop_reason="tool_use"),
            _message_stop_event(),
        ]

        provider._client.messages.stream = MagicMock(return_value=_FakeStream(events))

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="读文件")]):
            collected.append(ev)

        tool_start = next(e for e in collected if e.event_type == "tool_call_start")
        assert isinstance(tool_start.data, ToolCall)
        assert tool_start.data.name == "read_file"

        tool_deltas = [e for e in collected if e.event_type == "tool_call_delta"]
        assert len(tool_deltas) == 2

        tool_end = next(e for e in collected if e.event_type == "tool_call_end")
        assert isinstance(tool_end.data, ToolCall)
        assert tool_end.data.id == "toolu_01"
        assert tool_end.data.arguments == {"path": "/tmp/a"}

        done_ev = next(e for e in collected if e.event_type == "done")
        assert done_ev.data.tool_calls is not None
        assert done_ev.data.tool_calls[0].name == "read_file"

    async def test_stream_done_contains_llmresponse(self, provider):
        """done 事件 data 为 LLMResponse 实例"""
        from by19code.llm.base import Message, LLMResponse

        events = [
            _message_start_event(50),
            _text_event("ok"),
            _message_delta_event(20),
            _message_stop_event(),
        ]
        provider._client.messages.stream = MagicMock(return_value=_FakeStream(events))

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        done_ev = next(e for e in collected if e.event_type == "done")
        assert isinstance(done_ev.data, LLMResponse)

    async def test_stream_cost_in_usage_event(self, provider):
        """usage 事件 data.estimated_cost > 0"""
        from by19code.llm.base import Message

        events = [
            _message_start_event(1_000_000),
            _message_delta_event(1_000_000),
            _message_stop_event(),
        ]
        provider._client.messages.stream = MagicMock(return_value=_FakeStream(events))

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        usage_ev = next(e for e in collected if e.event_type == "usage")
        # sonnet 1M+1M = $18
        assert abs(usage_ev.data.estimated_cost - 18.0) < 1e-6

    async def test_stream_invalid_tool_json(self, provider):
        """工具参数 JSON 解析失败时，arguments 为空 dict 而非崩溃"""
        from by19code.llm.base import Message, ToolCall

        events = [
            _message_start_event(100),
            _tool_start_event(0, "t1", "broken_tool"),
            _tool_delta_event(0, "这不是JSON"),
            _tool_stop_event(0),
            _message_delta_event(30, "tool_use"),
            _message_stop_event(),
        ]
        provider._client.messages.stream = MagicMock(return_value=_FakeStream(events))

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="go")]):
            collected.append(ev)

        tool_end = next(e for e in collected if e.event_type == "tool_call_end")
        assert isinstance(tool_end.data, ToolCall)
        assert tool_end.data.arguments == {}


# ---------------------------------------------------------------------------
# 10. stream_chat() 异常处理
# ---------------------------------------------------------------------------

class TestStreamChatExceptions:
    async def test_stream_auth_error_yields_error_event(self, provider, fake_anthropic):
        """AuthenticationError 在流中 yield error 事件而不崩溃"""
        from by19code.llm.base import Message

        class _RaisingStream:
            async def __aenter__(self):
                raise fake_anthropic.AuthenticationError("bad key")
            async def __aexit__(self, *_): pass

        provider._client.messages.stream = MagicMock(return_value=_RaisingStream())

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        assert len(collected) == 1
        assert collected[0].event_type == "error"
        assert "bad key" in collected[0].data.lower() or "auth" in collected[0].data.lower() or "claude" in collected[0].data.lower()

    async def test_stream_rate_limit_yields_error_event(self, provider, fake_anthropic):
        """RateLimitError 在流中 yield error 事件"""
        from by19code.llm.base import Message

        class _RaisingStream:
            async def __aenter__(self):
                raise fake_anthropic.RateLimitError("429")
            async def __aexit__(self, *_): pass

        provider._client.messages.stream = MagicMock(return_value=_RaisingStream())

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        assert any(e.event_type == "error" for e in collected)

    async def test_stream_unexpected_error_yields_error_event(self, provider):
        """未知异常也 yield error 事件"""
        from by19code.llm.base import Message

        class _RaisingStream:
            async def __aenter__(self):
                raise RuntimeError("unexpected boom")
            async def __aexit__(self, *_): pass

        provider._client.messages.stream = MagicMock(return_value=_RaisingStream())

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        assert any(e.event_type == "error" for e in collected)


# ---------------------------------------------------------------------------
# 11. provider_name 属性
# ---------------------------------------------------------------------------

class TestProviderName:
    def test_provider_name(self, provider):
        assert provider.provider_name == "claude"
