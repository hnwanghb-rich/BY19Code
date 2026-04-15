"""by19code.llm.openai_provider 单元测试【T06】

测试分组
--------
  TestCalculateCost          - calculate_cost() DeepSeek/OpenAI 定价表与公式
  TestBuildApiMessages       - _build_api_messages() 消息格式转换（OpenAI 格式）
  TestBuildApiTools          - _build_api_tools() function 包装格式
  TestParseResponse          - _parse_response() 响应解析（arguments JSON 字符串→dict）
  TestMapException           - _map_exception() 异常映射
  TestChatSuccess            - chat() 正常路径
  TestChatRetry              - chat() 重试逻辑
  TestChatExceptions         - chat() 非重试异常直接抛出
  TestStreamChat             - stream_chat() 流式事件映射（text / tool / usage chunk）
  TestStreamChatExceptions   - stream_chat() 流式错误 → error 事件
  TestInterfaceConsistency   - ClaudeProvider 与 OpenAICompatibleProvider 接口一致性

全部 async 测试由 anyio（asyncio 后端）驱动。
"""
from __future__ import annotations

import asyncio
import inspect
import json
import sys
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Windows 事件循环策略（Python 3.12 目标，3.14 已弃用）
if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# 辅助：伪造 openai 模块
# ---------------------------------------------------------------------------

def _make_fake_openai() -> MagicMock:
    """构造最小化 fake openai 模块（含 SDK 异常类和 AsyncOpenAI）"""
    fo = MagicMock(name="fake_openai")

    class AuthenticationError(Exception): pass

    class RateLimitError(Exception):
        def __init__(self, msg: str = "", response: Any = None) -> None:
            super().__init__(msg)
            self.response = response

    class APITimeoutError(Exception): pass

    class APIConnectionError(Exception): pass

    class BadRequestError(Exception): pass

    class APIError(Exception): pass

    fo.AuthenticationError = AuthenticationError
    fo.RateLimitError = RateLimitError
    fo.APITimeoutError = APITimeoutError
    fo.APIConnectionError = APIConnectionError
    fo.BadRequestError = BadRequestError
    fo.APIError = APIError
    fo.AsyncOpenAI = MagicMock()
    return fo


# ---------------------------------------------------------------------------
# 辅助：构造伪造 OpenAI 响应对象（非流式）
# ---------------------------------------------------------------------------

def _make_text_response(
    text: str,
    model: str = "deepseek-chat",
    finish_reason: str = "stop",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> MagicMock:
    resp = MagicMock()
    resp.model = model

    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason

    resp.choices = [choice]

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    resp.usage = usage
    return resp


def _make_tool_response(
    tool_id: str,
    tool_name: str,
    tool_arguments_json: str,          # OpenAI 格式：JSON 字符串
    model: str = "deepseek-chat",
    prompt_tokens: int = 200,
    completion_tokens: int = 80,
) -> MagicMock:
    resp = MagicMock()
    resp.model = model

    func = MagicMock()
    func.name = tool_name
    func.arguments = tool_arguments_json

    tc = MagicMock()
    tc.id = tool_id
    tc.type = "function"
    tc.function = func

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "tool_calls"

    resp.choices = [choice]

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    resp.usage = usage
    return resp


# ---------------------------------------------------------------------------
# 辅助：构造流式 chunk 对象
# ---------------------------------------------------------------------------

def _text_chunk(text: str, finish_reason: str | None = None) -> MagicMock:
    """文本增量 chunk"""
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = text
    delta.tool_calls = None

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason

    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _stop_chunk(finish_reason: str = "stop") -> MagicMock:
    """finish_reason chunk（无内容）"""
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = None
    delta.tool_calls = None

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason

    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _tool_start_chunk(index: int, call_id: str, name: str) -> MagicMock:
    """工具调用首个 chunk（含 id 与函数名）"""
    chunk = MagicMock()

    func = MagicMock()
    func.name = name
    func.arguments = ""  # 首次通常为空

    tc_delta = MagicMock()
    tc_delta.index = index
    tc_delta.id = call_id
    tc_delta.function = func

    delta = MagicMock()
    delta.content = None
    delta.tool_calls = [tc_delta]

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = None

    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _tool_args_chunk(index: int, args_frag: str) -> MagicMock:
    """工具调用参数增量 chunk（id=None）"""
    chunk = MagicMock()

    func = MagicMock()
    func.name = None
    func.arguments = args_frag

    tc_delta = MagicMock()
    tc_delta.index = index
    tc_delta.id = None   # 后续 chunk 无 id
    tc_delta.function = func

    delta = MagicMock()
    delta.content = None
    delta.tool_calls = [tc_delta]

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = None

    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _usage_chunk(prompt_tokens: int, completion_tokens: int) -> MagicMock:
    """OpenAI stream_options usage chunk（choices=[]）"""
    chunk = MagicMock()
    chunk.choices = []

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    chunk.usage = usage
    return chunk


class _FakeStream:
    """模拟 openai AsyncStream：create(stream=True) 返回的异步可迭代对象"""

    def __init__(self, chunks: list[MagicMock]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[MagicMock]:
        return self._gen()

    async def _gen(self) -> AsyncIterator[MagicMock]:
        for chunk in self._chunks:
            yield chunk


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_openai() -> MagicMock:
    return _make_fake_openai()


@pytest.fixture
def provider_and_mod(fake_openai: MagicMock):
    with patch.dict("sys.modules", {"openai": fake_openai}):
        from importlib import reload
        import by19code.llm.openai_provider as mod
        reload(mod)
        prov = mod.OpenAICompatibleProvider(
            api_key="sk-test",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            provider_name="deepseek",
        )
        prov._openai = fake_openai
        prov._client = MagicMock()
        return prov, mod


@pytest.fixture
def provider(provider_and_mod):
    return provider_and_mod[0]


# ---------------------------------------------------------------------------
# 1. calculate_cost
# ---------------------------------------------------------------------------

class TestCalculateCost:
    def test_deepseek_chat_input(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=0)
        cost = provider.calculate_cost(usage, "deepseek-chat")
        assert abs(cost - 0.14) < 1e-9

    def test_deepseek_chat_output(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=0, completion_tokens=1_000_000)
        cost = provider.calculate_cost(usage, "deepseek-chat")
        assert abs(cost - 0.28) < 1e-9

    def test_deepseek_chat_combined(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        cost = provider.calculate_cost(usage, "deepseek-chat")
        assert abs(cost - 0.42) < 1e-9  # 0.14 + 0.28

    def test_gpt4o_price(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        cost = provider.calculate_cost(usage, "gpt-4o")
        assert abs(cost - 12.5) < 1e-9  # 2.5 + 10.0

    def test_unknown_model_uses_default(self, provider):
        """未知模型使用默认价格（DeepSeek-chat）"""
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        cost_unknown = provider.calculate_cost(usage, "unknown-model")
        cost_deepseek = provider.calculate_cost(usage, "deepseek-chat")
        assert abs(cost_unknown - cost_deepseek) < 1e-9

    def test_zero_tokens(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=0, completion_tokens=0)
        assert provider.calculate_cost(usage, "deepseek-chat") == 0.0

    def test_case_insensitive(self, provider):
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=0)
        assert abs(
            provider.calculate_cost(usage, "DeepSeek-Chat")
            - provider.calculate_cost(usage, "deepseek-chat")
        ) < 1e-9

    def test_small_token_count(self, provider):
        """1000 input tokens → $0.00014"""
        from by19code.llm.base import TokenUsage
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=0)
        cost = provider.calculate_cost(usage, "deepseek-chat")
        assert abs(cost - 0.00014) < 1e-10


# ---------------------------------------------------------------------------
# 2. _build_api_messages
# ---------------------------------------------------------------------------

class TestBuildApiMessages:
    def test_empty(self, provider):
        result = provider._build_api_messages([])
        assert result == []

    def test_system_stays_in_list(self, provider):
        """OpenAI: system 消息保留在 messages 列表内（不提取）"""
        from by19code.llm.base import Message
        msgs = [
            Message(role="system", content="你是助手"),
            Message(role="user", content="你好"),
        ]
        result = provider._build_api_messages(msgs)
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "你是助手"}
        assert result[1] == {"role": "user", "content": "你好"}

    def test_user_message(self, provider):
        from by19code.llm.base import Message
        result = provider._build_api_messages([Message(role="user", content="hello")])
        assert result[0] == {"role": "user", "content": "hello"}

    def test_assistant_text_only(self, provider):
        from by19code.llm.base import Message
        msgs = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="你好！"),
        ]
        result = provider._build_api_messages(msgs)
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "你好！"
        assert "tool_calls" not in result[1]

    def test_assistant_with_tool_calls(self, provider):
        """assistant tool_calls → arguments 序列化为 JSON 字符串"""
        from by19code.llm.base import Message, ToolCall
        tc = ToolCall(id="call_1", name="read_file", arguments={"path": "/tmp/a"})
        msgs = [
            Message(role="user", content="读文件"),
            Message(role="assistant", content="", tool_calls=[tc]),
        ]
        result = provider._build_api_messages(msgs)
        asst = result[1]
        assert asst["role"] == "assistant"
        assert "tool_calls" in asst
        tc_out = asst["tool_calls"][0]
        assert tc_out["id"] == "call_1"
        assert tc_out["type"] == "function"
        assert tc_out["function"]["name"] == "read_file"
        # arguments 必须是 JSON 字符串
        args_str = tc_out["function"]["arguments"]
        assert isinstance(args_str, str)
        assert json.loads(args_str) == {"path": "/tmp/a"}

    def test_assistant_no_content_with_tools(self, provider):
        """有工具调用且 content 为空时，content 字段值为 None"""
        from by19code.llm.base import Message, ToolCall
        tc = ToolCall(id="c1", name="fn", arguments={})
        msgs = [
            Message(role="user", content="go"),
            Message(role="assistant", content="", tool_calls=[tc]),
        ]
        result = provider._build_api_messages(msgs)
        assert result[1]["content"] is None

    def test_tool_result_independent(self, provider):
        """tool 消息保持独立（不合并，与 Claude 的差异）"""
        from by19code.llm.base import Message, ToolCall
        msgs = [
            Message(role="user", content="调工具"),
            Message(role="assistant", content="", tool_calls=[
                ToolCall(id="c1", name="tool_a", arguments={}),
                ToolCall(id="c2", name="tool_b", arguments={}),
            ]),
            Message(role="tool", content="结果A", tool_call_id="c1"),
            Message(role="tool", content="结果B", tool_call_id="c2"),
        ]
        result = provider._build_api_messages(msgs)
        # 每条 tool 消息独立，不合并
        tool_msgs = [m for m in result if m["role"] == "tool"]
        assert len(tool_msgs) == 2
        assert tool_msgs[0]["tool_call_id"] == "c1"
        assert tool_msgs[0]["content"] == "结果A"
        assert tool_msgs[1]["tool_call_id"] == "c2"

    def test_tool_message_structure(self, provider):
        from by19code.llm.base import Message
        msgs = [Message(role="tool", content="结果", tool_call_id="call_abc")]
        result = provider._build_api_messages(msgs)
        assert result[0] == {
            "role": "tool",
            "tool_call_id": "call_abc",
            "content": "结果",
        }

    def test_multiple_messages_order_preserved(self, provider):
        from by19code.llm.base import Message
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="u1"),
            Message(role="assistant", content="a1"),
            Message(role="user", content="u2"),
        ]
        result = provider._build_api_messages(msgs)
        roles = [m["role"] for m in result]
        assert roles == ["system", "user", "assistant", "user"]


# ---------------------------------------------------------------------------
# 3. _build_api_tools
# ---------------------------------------------------------------------------

class TestBuildApiTools:
    def test_empty(self, provider):
        assert provider._build_api_tools([]) == []

    def test_function_wrapper(self, provider):
        """OpenAI 格式：type="function" 包装"""
        from by19code.llm.base import ToolDefinition
        td = ToolDefinition(
            name="read_file",
            description="读取文件",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        result = provider._build_api_tools([td])
        assert result[0]["type"] == "function"
        f = result[0]["function"]
        assert f["name"] == "read_file"
        assert f["description"] == "读取文件"
        assert f["parameters"] == td.parameters

    def test_no_parameters_default_schema(self, provider):
        from by19code.llm.base import ToolDefinition
        td = ToolDefinition(name="ping", description="测试")
        result = provider._build_api_tools([td])
        assert result[0]["function"]["parameters"] == {
            "type": "object", "properties": {}
        }

    def test_multiple_tools(self, provider):
        from by19code.llm.base import ToolDefinition
        tools = [ToolDefinition(name=f"t{i}", description=f"工具{i}") for i in range(3)]
        result = provider._build_api_tools(tools)
        assert len(result) == 3
        assert all(r["type"] == "function" for r in result)


# ---------------------------------------------------------------------------
# 4. _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_text_response(self, provider):
        resp = _make_text_response("你好", prompt_tokens=100, completion_tokens=40)
        result = provider._parse_response(resp)
        assert result.content == "你好"
        assert result.tool_calls is None
        assert result.usage.prompt_tokens == 100
        assert result.usage.completion_tokens == 40
        assert result.usage.total_tokens == 140
        assert result.stop_reason == "stop"

    def test_tool_call_response(self, provider):
        """arguments JSON 字符串自动解析为 dict"""
        resp = _make_tool_response(
            "call_1", "read_file", '{"path": "/tmp/test.py"}',
            prompt_tokens=200, completion_tokens=80,
        )
        result = provider._parse_response(resp)
        assert result.content == ""
        assert result.tool_calls is not None
        tc = result.tool_calls[0]
        assert tc.id == "call_1"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/tmp/test.py"}
        assert result.stop_reason == "tool_calls"

    def test_invalid_json_arguments(self, provider):
        """arguments JSON 解析失败时返回空 dict"""
        resp = _make_tool_response("c1", "fn", "这不是JSON")
        result = provider._parse_response(resp)
        assert result.tool_calls[0].arguments == {}

    def test_empty_arguments(self, provider):
        """arguments 为空字符串时返回空 dict"""
        resp = _make_tool_response("c1", "fn", "")
        result = provider._parse_response(resp)
        assert result.tool_calls[0].arguments == {}

    def test_no_usage_returns_zeros(self, provider):
        """usage 为 None 时 token 数为 0"""
        resp = _make_text_response("hi")
        resp.usage = None
        result = provider._parse_response(resp)
        assert result.usage.prompt_tokens == 0
        assert result.usage.completion_tokens == 0

    def test_model_propagated(self, provider):
        resp = _make_text_response("ok", model="gpt-4o")
        result = provider._parse_response(resp)
        assert result.model == "gpt-4o"

    def test_multiple_tool_calls(self, provider):
        """同一响应中多个工具调用"""
        resp = MagicMock()
        resp.model = "deepseek-chat"

        def _make_tc(tid, name, args_str):
            func = MagicMock()
            func.name = name
            func.arguments = args_str
            tc = MagicMock()
            tc.id = tid
            tc.function = func
            return tc

        msg = MagicMock()
        msg.content = None
        msg.tool_calls = [
            _make_tc("c1", "fn_a", '{"x": 1}'),
            _make_tc("c2", "fn_b", '{"y": 2}'),
        ]

        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "tool_calls"
        resp.choices = [choice]
        resp.usage = MagicMock()
        resp.usage.prompt_tokens = 100
        resp.usage.completion_tokens = 50

        result = provider._parse_response(resp)
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].name == "fn_a"
        assert result.tool_calls[1].arguments == {"y": 2}


# ---------------------------------------------------------------------------
# 5. _map_exception
# ---------------------------------------------------------------------------

class TestMapException:
    def test_auth_error(self, provider, fake_openai):
        exc = fake_openai.AuthenticationError("bad key")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMAuthError
        assert isinstance(mapped, LLMAuthError)
        assert mapped.provider == "deepseek"
        assert mapped.original_error is exc

    def test_rate_limit_error(self, provider, fake_openai):
        exc = fake_openai.RateLimitError("429")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMRateLimitError
        assert isinstance(mapped, LLMRateLimitError)

    def test_rate_limit_with_retry_after(self, provider, fake_openai):
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "60"}
        exc = fake_openai.RateLimitError("rate", response=mock_resp)
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMRateLimitError
        assert isinstance(mapped, LLMRateLimitError)
        assert mapped.retry_after == 60.0

    def test_timeout_error(self, provider, fake_openai):
        exc = fake_openai.APITimeoutError("timeout")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMTimeoutError
        assert isinstance(mapped, LLMTimeoutError)

    def test_connection_error(self, provider, fake_openai):
        exc = fake_openai.APIConnectionError("connection failed")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMTimeoutError
        assert isinstance(mapped, LLMTimeoutError)

    def test_bad_request_error(self, provider, fake_openai):
        exc = fake_openai.BadRequestError("invalid")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMResponseError
        assert isinstance(mapped, LLMResponseError)

    def test_unknown_error(self, provider):
        exc = RuntimeError("unexpected")
        mapped = provider._map_exception(exc)
        from by19code.llm.base import LLMError
        assert isinstance(mapped, LLMError)
        assert mapped.provider == "deepseek"

    def test_str_contains_provider(self, provider, fake_openai):
        exc = fake_openai.AuthenticationError("bad")
        mapped = provider._map_exception(exc)
        assert "deepseek" in str(mapped).lower()


# ---------------------------------------------------------------------------
# 6. chat() 正常路径
# ---------------------------------------------------------------------------

class TestChatSuccess:
    async def test_text_response(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_text_response("你好！", prompt_tokens=100, completion_tokens=40)
        provider._client.chat.completions.create = AsyncMock(return_value=resp_mock)

        result = await provider.chat([Message(role="user", content="你好")])
        assert result.content == "你好！"
        assert result.tool_calls is None
        assert result.usage.total_tokens == 140

    def _assert_create_called_with(self, provider, **expected_kwargs):
        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        for k, v in expected_kwargs.items():
            assert call_kwargs[k] == v

    async def test_system_in_messages_list(self, provider):
        """OpenAI: system 消息在 messages 列表里，不是独立参数"""
        from by19code.llm.base import Message
        resp_mock = _make_text_response("hi")
        provider._client.chat.completions.create = AsyncMock(return_value=resp_mock)

        await provider.chat([
            Message(role="system", content="你是助手"),
            Message(role="user", content="hi"),
        ])

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        # 没有独立的 system 参数
        assert "system" not in call_kwargs
        # messages[0] 是 system
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "你是助手"

    async def test_tools_passed(self, provider):
        from by19code.llm.base import Message, ToolDefinition
        resp_mock = _make_text_response("ok")
        provider._client.chat.completions.create = AsyncMock(return_value=resp_mock)

        tools = [ToolDefinition(name="ping", description="test")]
        await provider.chat([Message(role="user", content="go")], tools=tools)

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "ping"

    async def test_model_override(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_text_response("ok", model="gpt-4o")
        provider._client.chat.completions.create = AsyncMock(return_value=resp_mock)

        await provider.chat([Message(role="user", content="hi")], model="gpt-4o")

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"

    async def test_cost_calculated(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_text_response(
            "ok", prompt_tokens=1_000_000, completion_tokens=1_000_000
        )
        provider._client.chat.completions.create = AsyncMock(return_value=resp_mock)

        result = await provider.chat([Message(role="user", content="hi")])
        # deepseek-chat: 0.14 + 0.28 = 0.42
        assert abs(result.usage.estimated_cost - 0.42) < 1e-9

    async def test_tool_call_response(self, provider):
        from by19code.llm.base import Message
        resp_mock = _make_tool_response("c1", "read_file", '{"path":"/tmp/a"}')
        provider._client.chat.completions.create = AsyncMock(return_value=resp_mock)

        result = await provider.chat([Message(role="user", content="读文件")])
        assert result.has_tool_calls
        tc = result.tool_calls[0]
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/tmp/a"}


# ---------------------------------------------------------------------------
# 7. chat() 重试逻辑
# ---------------------------------------------------------------------------

class TestChatRetry:
    async def test_rate_limit_retries_three_times(self, provider, fake_openai):
        from by19code.llm.base import LLMRateLimitError
        provider._client.chat.completions.create = AsyncMock(
            side_effect=fake_openai.RateLimitError("429")
        )

        with patch("by19code.llm.openai_provider.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(LLMRateLimitError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        assert mock_sleep.call_count == 2  # 3次尝试 → 2次sleep

    async def test_retry_sleep_durations(self, provider, fake_openai):
        from by19code.llm.base import LLMRateLimitError
        provider._client.chat.completions.create = AsyncMock(
            side_effect=fake_openai.RateLimitError("429")
        )
        durations: list[float] = []

        async def fake_sleep(secs: float) -> None:
            durations.append(secs)

        with patch("by19code.llm.openai_provider.asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(LLMRateLimitError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        assert durations == [1.0, 2.0]

    async def test_retry_succeeds_on_second_attempt(self, provider, fake_openai):
        resp_mock = _make_text_response("成功")
        provider._client.chat.completions.create = AsyncMock(
            side_effect=[fake_openai.RateLimitError("429"), resp_mock]
        )

        with patch("by19code.llm.openai_provider.asyncio.sleep", new_callable=AsyncMock):
            from by19code.llm.base import Message
            result = await provider.chat([Message(role="user", content="hi")])

        assert result.content == "成功"
        assert provider._client.chat.completions.create.call_count == 2

    async def test_timeout_retries(self, provider, fake_openai):
        from by19code.llm.base import LLMTimeoutError
        provider._client.chat.completions.create = AsyncMock(
            side_effect=fake_openai.APITimeoutError("timeout")
        )

        with patch("by19code.llm.openai_provider.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMTimeoutError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        assert provider._client.chat.completions.create.call_count == 3

    async def test_connection_error_retries(self, provider, fake_openai):
        from by19code.llm.base import LLMTimeoutError
        provider._client.chat.completions.create = AsyncMock(
            side_effect=fake_openai.APIConnectionError("conn failed")
        )

        with patch("by19code.llm.openai_provider.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMTimeoutError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])


# ---------------------------------------------------------------------------
# 8. chat() 非重试异常
# ---------------------------------------------------------------------------

class TestChatExceptions:
    async def test_auth_error_not_retried(self, provider, fake_openai):
        from by19code.llm.base import LLMAuthError
        provider._client.chat.completions.create = AsyncMock(
            side_effect=fake_openai.AuthenticationError("bad key")
        )

        with patch("by19code.llm.openai_provider.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(LLMAuthError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        mock_sleep.assert_not_called()
        assert provider._client.chat.completions.create.call_count == 1

    async def test_bad_request_not_retried(self, provider, fake_openai):
        from by19code.llm.base import LLMResponseError
        provider._client.chat.completions.create = AsyncMock(
            side_effect=fake_openai.BadRequestError("bad req")
        )

        with patch("by19code.llm.openai_provider.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMResponseError):
                from by19code.llm.base import Message
                await provider.chat([Message(role="user", content="hi")])

        assert provider._client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# 9. stream_chat() 流式事件映射
# ---------------------------------------------------------------------------

class TestStreamChat:
    async def test_text_stream(self, provider):
        """纯文本流：text_delta → usage → done"""
        from by19code.llm.base import Message, TokenUsage, LLMResponse

        chunks = [
            _text_chunk("Hello"),
            _text_chunk(", World"),
            _stop_chunk("stop"),
            _usage_chunk(100, 10),
        ]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        event_types = [e.event_type for e in collected]
        assert "text_delta" in event_types
        assert "usage" in event_types
        assert "done" in event_types

        # 文本拼接正确
        text_parts = [e.data for e in collected if e.event_type == "text_delta"]
        assert "".join(text_parts) == "Hello, World"

        # usage 含正确 token 数
        usage_ev = next(e for e in collected if e.event_type == "usage")
        assert isinstance(usage_ev.data, TokenUsage)
        assert usage_ev.data.prompt_tokens == 100
        assert usage_ev.data.completion_tokens == 10

        # done 含 LLMResponse
        done_ev = next(e for e in collected if e.event_type == "done")
        assert isinstance(done_ev.data, LLMResponse)
        assert done_ev.data.content == "Hello, World"

    async def test_text_stream_without_usage_chunk(self, provider):
        """没有 usage chunk 时：usage.tokens == 0，done 仍然发出"""
        from by19code.llm.base import Message, LLMResponse

        chunks = [
            _text_chunk("ok"),
            _stop_chunk("stop"),
            # 无 usage chunk
        ]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        usage_ev = next(e for e in collected if e.event_type == "usage")
        assert usage_ev.data.prompt_tokens == 0
        assert usage_ev.data.completion_tokens == 0

        done_ev = next(e for e in collected if e.event_type == "done")
        assert isinstance(done_ev.data, LLMResponse)

    async def test_tool_call_stream(self, provider):
        """工具调用流：tool_call_start → delta × N → tool_call_end"""
        from by19code.llm.base import Message, ToolCall

        chunks = [
            _tool_start_chunk(0, "call_abc", "read_file"),
            _tool_args_chunk(0, '{"path":'),
            _tool_args_chunk(0, ' "/tmp/a"}'),
            _stop_chunk("tool_calls"),
            _usage_chunk(200, 50),
        ]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="读文件")]):
            collected.append(ev)

        # tool_call_start
        start = next(e for e in collected if e.event_type == "tool_call_start")
        assert isinstance(start.data, ToolCall)
        assert start.data.name == "read_file"
        assert start.data.id == "call_abc"

        # tool_call_delta（两次）
        deltas = [e for e in collected if e.event_type == "tool_call_delta"]
        assert len(deltas) == 2
        assert "".join(e.data for e in deltas) == '{"path": "/tmp/a"}'

        # tool_call_end（arguments 完整解析）
        end = next(e for e in collected if e.event_type == "tool_call_end")
        assert isinstance(end.data, ToolCall)
        assert end.data.arguments == {"path": "/tmp/a"}

        # done.tool_calls 包含该工具
        done = next(e for e in collected if e.event_type == "done")
        assert done.data.tool_calls is not None
        assert done.data.tool_calls[0].name == "read_file"

    async def test_multiple_tool_calls_stream(self, provider):
        """两个工具调用（按 index 0 和 1）"""
        from by19code.llm.base import Message

        chunks = [
            _tool_start_chunk(0, "call_1", "fn_a"),
            _tool_args_chunk(0, '{"a": 1}'),
            _tool_start_chunk(1, "call_2", "fn_b"),
            _tool_args_chunk(1, '{"b": 2}'),
            _stop_chunk("tool_calls"),
            _usage_chunk(300, 80),
        ]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="go")]):
            collected.append(ev)

        starts = [e for e in collected if e.event_type == "tool_call_start"]
        ends = [e for e in collected if e.event_type == "tool_call_end"]
        assert len(starts) == 2
        assert len(ends) == 2

        done = next(e for e in collected if e.event_type == "done")
        assert len(done.data.tool_calls) == 2

    async def test_stream_cost_calculated(self, provider):
        """cost 在 usage 事件中正确计算"""
        from by19code.llm.base import Message

        chunks = [
            _stop_chunk("stop"),
            _usage_chunk(1_000_000, 1_000_000),
        ]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        usage_ev = next(e for e in collected if e.event_type == "usage")
        # deepseek-chat 1M+1M = $0.42
        assert abs(usage_ev.data.estimated_cost - 0.42) < 1e-9

    async def test_stream_stop_reason_propagated(self, provider):
        """stop_reason 在 done 事件中正确传递"""
        from by19code.llm.base import Message

        chunks = [
            _text_chunk("ok"),
            _stop_chunk("length"),
        ]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            collected.append(ev)

        done = next(e for e in collected if e.event_type == "done")
        assert done.data.stop_reason == "length"

    async def test_stream_invalid_tool_json(self, provider):
        """工具参数 JSON 解析失败时 arguments 为空 dict"""
        from by19code.llm.base import Message, ToolCall

        chunks = [
            _tool_start_chunk(0, "c1", "bad_tool"),
            _tool_args_chunk(0, "这不是JSON"),
            _stop_chunk("tool_calls"),
        ]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        collected = []
        async for ev in provider.stream_chat([Message(role="user", content="go")]):
            collected.append(ev)

        end = next(e for e in collected if e.event_type == "tool_call_end")
        assert isinstance(end.data, ToolCall)
        assert end.data.arguments == {}

    async def test_stream_stream_options_passed(self, provider):
        """stream_options={"include_usage": True} 在请求 kwargs 中存在"""
        from by19code.llm.base import Message

        chunks = [_stop_chunk("stop")]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        async for _ in provider.stream_chat([Message(role="user", content="hi")]):
            pass

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("stream") is True
        assert call_kwargs.get("stream_options") == {"include_usage": True}


# ---------------------------------------------------------------------------
# 10. stream_chat() 异常 → error 事件
# ---------------------------------------------------------------------------

class TestStreamChatExceptions:
    async def _collect_from_raising_create(
        self, provider, exc_to_raise
    ):
        provider._client.chat.completions.create = AsyncMock(side_effect=exc_to_raise)
        from by19code.llm.base import Message
        events = []
        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            events.append(ev)
        return events

    async def test_auth_error_yields_error(self, provider, fake_openai):
        events = await self._collect_from_raising_create(
            provider, fake_openai.AuthenticationError("bad key")
        )
        assert len(events) == 1
        assert events[0].event_type == "error"

    async def test_rate_limit_yields_error(self, provider, fake_openai):
        events = await self._collect_from_raising_create(
            provider, fake_openai.RateLimitError("429")
        )
        assert any(e.event_type == "error" for e in events)

    async def test_timeout_yields_error(self, provider, fake_openai):
        events = await self._collect_from_raising_create(
            provider, fake_openai.APITimeoutError("timeout")
        )
        assert any(e.event_type == "error" for e in events)

    async def test_unknown_error_yields_error(self, provider):
        events = await self._collect_from_raising_create(
            provider, RuntimeError("unexpected boom")
        )
        assert any(e.event_type == "error" for e in events)

    async def test_error_message_contains_provider(self, provider, fake_openai):
        """error 事件的 data 字符串包含 provider 名"""
        events = await self._collect_from_raising_create(
            provider, fake_openai.AuthenticationError("bad key")
        )
        err_ev = next(e for e in events if e.event_type == "error")
        assert "deepseek" in err_ev.data.lower()


# ---------------------------------------------------------------------------
# 11. 接口一致性测试
# ---------------------------------------------------------------------------

class TestInterfaceConsistency:
    """验证 ClaudeProvider 与 OpenAICompatibleProvider 遵循相同的 LLMProvider 接口"""

    def test_both_inherit_llm_provider(self):
        from by19code.llm.base import LLMProvider
        # 不实际构造，只检查类继承关系
        with patch.dict("sys.modules", {"anthropic": _make_fake_anthropic()}):
            from importlib import reload
            import by19code.llm.claude_provider as cm
            reload(cm)
            assert issubclass(cm.ClaudeProvider, LLMProvider)

        with patch.dict("sys.modules", {"openai": _make_fake_openai()}):
            from importlib import reload
            import by19code.llm.openai_provider as om
            reload(om)
            assert issubclass(om.OpenAICompatibleProvider, LLMProvider)

    def test_chat_method_signature_identical(self):
        """chat() 方法参数名与顺序完全相同"""
        with patch.dict("sys.modules", {"anthropic": _make_fake_anthropic()}):
            from importlib import reload
            import by19code.llm.claude_provider as cm
            reload(cm)

        with patch.dict("sys.modules", {"openai": _make_fake_openai()}):
            from importlib import reload
            import by19code.llm.openai_provider as om
            reload(om)

        claude_params = list(inspect.signature(cm.ClaudeProvider.chat).parameters.keys())
        openai_params = list(inspect.signature(om.OpenAICompatibleProvider.chat).parameters.keys())
        assert claude_params == openai_params

    def test_stream_chat_method_signature_identical(self):
        """stream_chat() 方法参数名与顺序完全相同"""
        with patch.dict("sys.modules", {"anthropic": _make_fake_anthropic()}):
            from importlib import reload
            import by19code.llm.claude_provider as cm
            reload(cm)

        with patch.dict("sys.modules", {"openai": _make_fake_openai()}):
            from importlib import reload
            import by19code.llm.openai_provider as om
            reload(om)

        claude_params = list(
            inspect.signature(cm.ClaudeProvider.stream_chat).parameters.keys()
        )
        openai_params = list(
            inspect.signature(om.OpenAICompatibleProvider.stream_chat).parameters.keys()
        )
        assert claude_params == openai_params

    def test_calculate_cost_signature_identical(self):
        """calculate_cost() 方法参数名与顺序完全相同"""
        with patch.dict("sys.modules", {"anthropic": _make_fake_anthropic()}):
            from importlib import reload
            import by19code.llm.claude_provider as cm
            reload(cm)

        with patch.dict("sys.modules", {"openai": _make_fake_openai()}):
            from importlib import reload
            import by19code.llm.openai_provider as om
            reload(om)

        claude_params = list(
            inspect.signature(cm.ClaudeProvider.calculate_cost).parameters.keys()
        )
        openai_params = list(
            inspect.signature(om.OpenAICompatibleProvider.calculate_cost).parameters.keys()
        )
        assert claude_params == openai_params

    def test_provider_name_property_exists(self):
        """两个 Provider 均有 provider_name 属性"""
        with patch.dict("sys.modules", {"anthropic": _make_fake_anthropic()}):
            from importlib import reload
            import by19code.llm.claude_provider as cm
            reload(cm)

        with patch.dict("sys.modules", {"openai": _make_fake_openai()}):
            from importlib import reload
            import by19code.llm.openai_provider as om
            reload(om)

        assert isinstance(
            inspect.getattr_static(cm.ClaudeProvider, "provider_name"), property
        )
        assert isinstance(
            inspect.getattr_static(om.OpenAICompatibleProvider, "provider_name"), property
        )

    async def test_chat_returns_llmresponse(self, provider):
        """chat() 返回值是 LLMResponse 实例"""
        from by19code.llm.base import Message, LLMResponse
        provider._client.chat.completions.create = AsyncMock(
            return_value=_make_text_response("ok")
        )
        result = await provider.chat([Message(role="user", content="hi")])
        assert isinstance(result, LLMResponse)

    async def test_stream_chat_yields_stream_events(self, provider):
        """stream_chat() 产出的事件均为 StreamEvent 实例"""
        from by19code.llm.base import Message, StreamEvent

        chunks = [_text_chunk("hi"), _stop_chunk("stop")]
        provider._client.chat.completions.create = AsyncMock(
            return_value=_FakeStream(chunks)
        )

        async for ev in provider.stream_chat([Message(role="user", content="hi")]):
            assert isinstance(ev, StreamEvent)


# ---------------------------------------------------------------------------
# 辅助：为接口一致性测试提供 fake_anthropic（复用 T05 的结构）
# ---------------------------------------------------------------------------

def _make_fake_anthropic() -> MagicMock:
    fa = MagicMock(name="fake_anthropic")

    class AuthenticationError(Exception): pass
    class RateLimitError(Exception): pass
    class APITimeoutError(Exception): pass
    class APIConnectionError(Exception): pass
    class BadRequestError(Exception): pass

    fa.AuthenticationError = AuthenticationError
    fa.RateLimitError = RateLimitError
    fa.APITimeoutError = APITimeoutError
    fa.APIConnectionError = APIConnectionError
    fa.BadRequestError = BadRequestError
    fa.AsyncAnthropic = MagicMock()
    return fa
