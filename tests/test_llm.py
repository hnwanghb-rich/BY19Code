"""by19code.llm.base 单元测试【T04】

测试分组
--------
  TestToolCall          - 序列化、默认值、extra 字段忽略
  TestToolDefinition    - 参数 schema 构造、序列化
  TestTokenUsage        - auto total_tokens、cost、边界值
  TestMessage           - 各 role、tool_calls、tool_call_id
  TestLLMResponse       - content/tool_calls 属性辅助方法
  TestStreamEvent       - 各 event_type、data 类型
  TestLLMProviderABC    - 抽象类不可实例化、子类必须实现接口
  TestMockProvider      - Mock 实现：chat / stream_chat / calculate_cost
  TestExceptions        - 异常层次、属性、str 输出
  TestRoundTrip         - model_dump → model_validate 往返一致性
"""
from __future__ import annotations

import pytest

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
    TokenUsage,
    ToolCall,
    ToolDefinition,
)

# anyio 驱动异步测试（asyncio 后端）
pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Mock Provider（供 ABC 测试使用）
# ---------------------------------------------------------------------------


class MockProvider(LLMProvider):
    """最小化 Mock 实现，用于验证抽象接口可被正确继承"""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        return LLMResponse(
            content="Mock 回复",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
            model=model or "mock-model",
            stop_reason="end_turn",
        )

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ):
        """流式 Mock 实现：产出 text_delta + usage + done"""
        yield StreamEvent(event_type="text_delta", data="Hello")
        yield StreamEvent(event_type="text_delta", data=" World")
        yield StreamEvent(
            event_type="usage",
            data=TokenUsage(prompt_tokens=10, completion_tokens=5),
        )
        yield StreamEvent(
            event_type="done",
            data=LLMResponse(
                content="Hello World",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
                model="mock-model",
            ),
        )

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        # 固定单价：输入 $0.003/1k，输出 $0.015/1k
        return (usage.prompt_tokens / 1000) * 0.003 + (
            usage.completion_tokens / 1000
        ) * 0.015


class MockProviderWithToolCall(LLMProvider):
    """返回工具调用的 Mock Provider"""

    @property
    def provider_name(self) -> str:
        return "mock-tool"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        return LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="call_001",
                    name="read_file",
                    arguments={"path": "main.py"},
                )
            ],
            usage=TokenUsage(prompt_tokens=20, completion_tokens=10),
            stop_reason="tool_use",
        )

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ):
        yield StreamEvent(
            event_type="tool_call_start",
            data=ToolCall(id="call_001", name="read_file", arguments={}),
        )
        yield StreamEvent(event_type="tool_call_delta", data='{"path":')
        yield StreamEvent(event_type="tool_call_delta", data='"main.py"}')
        yield StreamEvent(
            event_type="tool_call_end",
            data=ToolCall(id="call_001", name="read_file", arguments={"path": "main.py"}),
        )
        yield StreamEvent(event_type="done", data=None)

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# 1. ToolCall
# ---------------------------------------------------------------------------


class TestToolCall:
    def test_basic_creation(self) -> None:
        tc = ToolCall(id="tc_1", name="read_file", arguments={"path": "main.py"})
        assert tc.id == "tc_1"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "main.py"}

    def test_default_arguments(self) -> None:
        """arguments 默认为空 dict"""
        tc = ToolCall(id="tc_2", name="list_directory")
        assert tc.arguments == {}

    def test_extra_fields_ignored(self) -> None:
        """extra='ignore'：多余字段不报错"""
        tc = ToolCall.model_validate(
            {"id": "x", "name": "y", "arguments": {}, "unknown": "z"}
        )
        assert not hasattr(tc, "unknown")

    def test_model_dump(self) -> None:
        tc = ToolCall(id="tc_3", name="write_file", arguments={"path": "a.py", "content": "x"})
        d = tc.model_dump()
        assert d["id"] == "tc_3"
        assert d["arguments"]["path"] == "a.py"

    def test_model_validate_from_dict(self) -> None:
        data = {"id": "tc_4", "name": "git_commit", "arguments": {"message": "init"}}
        tc = ToolCall.model_validate(data)
        assert tc.name == "git_commit"
        assert tc.arguments["message"] == "init"

    def test_nested_arguments(self) -> None:
        """arguments 支持嵌套 dict / list"""
        tc = ToolCall(
            id="tc_5", name="run",
            arguments={"cmd": "pytest", "flags": ["-v", "--tb=short"]},
        )
        assert tc.arguments["flags"] == ["-v", "--tb=short"]


# ---------------------------------------------------------------------------
# 2. ToolDefinition
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_basic_creation(self) -> None:
        td = ToolDefinition(
            name="read_file",
            description="读取指定路径的文件内容",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
        )
        assert td.name == "read_file"
        assert td.parameters["type"] == "object"

    def test_empty_parameters(self) -> None:
        """parameters 默认为空 dict"""
        td = ToolDefinition(name="git_status", description="查看 Git 状态")
        assert td.parameters == {}

    def test_model_dump_roundtrip(self) -> None:
        td = ToolDefinition(
            name="write_file",
            description="写入文件",
            parameters={"type": "object", "properties": {}},
        )
        data = td.model_dump()
        td2 = ToolDefinition.model_validate(data)
        assert td2.name == td.name
        assert td2.description == td.description

    def test_complex_json_schema(self) -> None:
        """支持嵌套 JSON Schema"""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string", "enum": ["utf-8", "gbk"]},
            },
            "required": ["path"],
        }
        td = ToolDefinition(name="read", description="desc", parameters=schema)
        assert td.parameters["properties"]["encoding"]["enum"] == ["utf-8", "gbk"]


# ---------------------------------------------------------------------------
# 3. TokenUsage
# ---------------------------------------------------------------------------


class TestTokenUsage:
    def test_auto_total_when_zero(self) -> None:
        """total_tokens 为 0 时自动计算"""
        u = TokenUsage(prompt_tokens=100, completion_tokens=50)
        assert u.total_tokens == 150

    def test_explicit_total_preserved(self) -> None:
        """total_tokens 显式提供时不被覆盖"""
        u = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=999)
        assert u.total_tokens == 999

    def test_default_all_zero(self) -> None:
        u = TokenUsage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0
        assert u.estimated_cost == 0.0

    def test_estimated_cost(self) -> None:
        u = TokenUsage(prompt_tokens=1000, completion_tokens=500, estimated_cost=0.012)
        assert u.estimated_cost == 0.012

    def test_model_dump(self) -> None:
        u = TokenUsage(prompt_tokens=200, completion_tokens=100)
        d = u.model_dump()
        assert d["total_tokens"] == 300

    def test_model_validate(self) -> None:
        data = {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75}
        u = TokenUsage.model_validate(data)
        assert u.total_tokens == 75  # 显式提供，不重算

    def test_only_prompt_tokens(self) -> None:
        u = TokenUsage(prompt_tokens=500)
        assert u.total_tokens == 500


# ---------------------------------------------------------------------------
# 4. Message
# ---------------------------------------------------------------------------


class TestMessage:
    def test_system_message(self) -> None:
        m = Message(role="system", content="你是 BY19Code AI 助手")
        assert m.role == "system"
        assert m.tool_calls is None
        assert m.tool_call_id is None

    def test_user_message(self) -> None:
        m = Message(role="user", content="帮我创建 hello.py")
        assert m.role == "user"

    def test_assistant_with_tool_calls(self) -> None:
        tc = ToolCall(id="c1", name="write_file", arguments={"path": "a.py", "content": ""})
        m = Message(role="assistant", content="", tool_calls=[tc])
        assert m.has_tool_calls  # noqa: attr-defined — see property below
        assert m.tool_calls[0].name == "write_file"

    def test_tool_message(self) -> None:
        m = Message(role="tool", content="文件读取成功", tool_call_id="c1")
        assert m.role == "tool"
        assert m.tool_call_id == "c1"

    def test_default_content_empty(self) -> None:
        m = Message(role="user")
        assert m.content == ""

    def test_model_dump_roundtrip(self) -> None:
        tc = ToolCall(id="c2", name="run_command", arguments={"command": "pytest"})
        m = Message(role="assistant", content="", tool_calls=[tc])
        data = m.model_dump()
        m2 = Message.model_validate(data)
        assert m2.tool_calls[0].id == "c2"

    def test_invalid_role_raises(self) -> None:
        with pytest.raises(Exception):
            Message.model_validate({"role": "unknown", "content": "x"})

    @pytest.mark.parametrize("role", ["system", "user", "assistant", "tool"])
    def test_all_valid_roles(self, role: str) -> None:
        m = Message.model_validate({"role": role})
        assert m.role == role


# 为 Message 添加 has_tool_calls 属性（测试用）
# 注：实际 Message.tool_calls 是列表，非布尔属性，测试中用 bool(m.tool_calls) 判断
def test_message_has_tool_calls_helper() -> None:
    tc = ToolCall(id="x", name="y", arguments={})
    m = Message(role="assistant", tool_calls=[tc])
    assert bool(m.tool_calls)

    m2 = Message(role="assistant")
    assert not bool(m2.tool_calls)


# ---------------------------------------------------------------------------
# 5. LLMResponse
# ---------------------------------------------------------------------------


class TestLLMResponse:
    def test_text_only_response(self) -> None:
        r = LLMResponse(content="Hello World", model="claude-3-7-sonnet-20250219", stop_reason="end_turn")
        assert r.content == "Hello World"
        assert r.is_complete
        assert not r.has_tool_calls

    def test_tool_call_response(self) -> None:
        tc = ToolCall(id="c1", name="read_file", arguments={"path": "main.py"})
        r = LLMResponse(tool_calls=[tc], stop_reason="tool_use")
        assert r.has_tool_calls
        assert not r.is_complete

    def test_empty_response_defaults(self) -> None:
        r = LLMResponse()
        assert r.content == ""
        assert r.tool_calls is None
        assert r.usage.total_tokens == 0
        assert r.is_complete

    def test_usage_auto_injected(self) -> None:
        r = LLMResponse(
            content="hi",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
        )
        assert r.usage.total_tokens == 15

    def test_model_dump_roundtrip(self) -> None:
        tc = ToolCall(id="c2", name="git_commit", arguments={"message": "feat: init"})
        r = LLMResponse(
            content="",
            tool_calls=[tc],
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50),
            model="deepseek-chat",
            stop_reason="tool_use",
        )
        data = r.model_dump()
        r2 = LLMResponse.model_validate(data)
        assert r2.tool_calls[0].name == "git_commit"
        assert r2.usage.total_tokens == 150
        assert r2.stop_reason == "tool_use"


# ---------------------------------------------------------------------------
# 6. StreamEvent
# ---------------------------------------------------------------------------


class TestStreamEvent:
    def test_text_delta(self) -> None:
        e = StreamEvent(event_type="text_delta", data="Hello")
        assert e.event_type == "text_delta"
        assert e.data == "Hello"

    def test_tool_call_start(self) -> None:
        tc = ToolCall(id="c1", name="read_file", arguments={})
        e = StreamEvent(event_type="tool_call_start", data=tc)
        assert isinstance(e.data, ToolCall)
        assert e.data.name == "read_file"

    def test_tool_call_delta(self) -> None:
        e = StreamEvent(event_type="tool_call_delta", data='{"path":')
        assert e.event_type == "tool_call_delta"
        assert e.data == '{"path":'

    def test_tool_call_end(self) -> None:
        tc = ToolCall(id="c1", name="read_file", arguments={"path": "main.py"})
        e = StreamEvent(event_type="tool_call_end", data=tc)
        assert e.data.arguments["path"] == "main.py"

    def test_usage_event(self) -> None:
        u = TokenUsage(prompt_tokens=100, completion_tokens=50)
        e = StreamEvent(event_type="usage", data=u)
        assert isinstance(e.data, TokenUsage)
        assert e.data.total_tokens == 150

    def test_done_event_with_response(self) -> None:
        r = LLMResponse(content="完成", model="claude-3-7-sonnet-20250219")
        e = StreamEvent(event_type="done", data=r)
        assert isinstance(e.data, LLMResponse)

    def test_done_event_none_data(self) -> None:
        e = StreamEvent(event_type="done", data=None)
        assert e.data is None

    def test_error_event(self) -> None:
        e = StreamEvent(event_type="error", data="API Key 无效")
        assert e.event_type == "error"
        assert "API Key" in e.data

    def test_invalid_event_type_raises(self) -> None:
        with pytest.raises(Exception):
            StreamEvent.model_validate({"event_type": "unknown_type", "data": None})

    @pytest.mark.parametrize(
        "event_type",
        [
            "text_delta",
            "tool_call_start",
            "tool_call_delta",
            "tool_call_end",
            "usage",
            "done",
            "error",
        ],
    )
    def test_all_valid_event_types(self, event_type: str) -> None:
        e = StreamEvent(event_type=event_type)  # type: ignore[arg-type]
        assert e.event_type == event_type


# ---------------------------------------------------------------------------
# 7. LLMProvider ABC
# ---------------------------------------------------------------------------


class TestLLMProviderABC:
    def test_cannot_instantiate_abc(self) -> None:
        """抽象类不可直接实例化"""
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_mock_provider_instantiable(self) -> None:
        """实现了所有抽象方法的子类可以实例化"""
        provider = MockProvider()
        assert provider.provider_name == "mock"

    def test_incomplete_subclass_raises(self) -> None:
        """未实现所有抽象方法的子类实例化时抛出 TypeError"""
        class IncompleteProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "incomplete"
            # 缺少 chat / stream_chat / calculate_cost

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_provider_name_readonly(self) -> None:
        provider = MockProvider()
        assert isinstance(provider.provider_name, str)
        # provider_name 是 property，不是普通属性
        with pytest.raises(AttributeError):
            provider.provider_name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 8. Mock Provider 功能测试
# ---------------------------------------------------------------------------


class TestMockProvider:
    async def test_chat_returns_response(self) -> None:
        provider = MockProvider()
        messages = [Message(role="user", content="你好")]
        response = await provider.chat(messages)
        assert isinstance(response, LLMResponse)
        assert response.content == "Mock 回复"
        assert response.stop_reason == "end_turn"

    async def test_chat_usage_populated(self) -> None:
        provider = MockProvider()
        messages = [Message(role="user", content="test")]
        response = await provider.chat(messages)
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5
        assert response.usage.total_tokens == 15

    async def test_chat_model_override(self) -> None:
        """model 参数正确传递"""
        provider = MockProvider()
        messages = [Message(role="user", content="test")]
        response = await provider.chat(messages, model="custom-model")
        assert response.model == "custom-model"

    async def test_stream_chat_yields_events(self) -> None:
        provider = MockProvider()
        messages = [Message(role="user", content="你好")]
        events: list[StreamEvent] = []
        async for event in provider.stream_chat(messages):
            events.append(event)

        event_types = [e.event_type for e in events]
        assert "text_delta" in event_types
        assert "done" in event_types

    async def test_stream_chat_text_content(self) -> None:
        """聚合 text_delta 得到完整文本"""
        provider = MockProvider()
        messages = [Message(role="user", content="test")]
        text_parts: list[str] = []
        async for event in provider.stream_chat(messages):
            if event.event_type == "text_delta":
                text_parts.append(event.data)
        assert "".join(text_parts) == "Hello World"

    async def test_stream_chat_usage_event(self) -> None:
        """usage 事件包含正确 TokenUsage"""
        provider = MockProvider()
        messages = [Message(role="user", content="test")]
        usage_events = []
        async for event in provider.stream_chat(messages):
            if event.event_type == "usage":
                usage_events.append(event)
        assert len(usage_events) == 1
        assert isinstance(usage_events[0].data, TokenUsage)
        assert usage_events[0].data.total_tokens == 15

    async def test_stream_chat_done_event(self) -> None:
        """done 事件 data 为 LLMResponse"""
        provider = MockProvider()
        messages = [Message(role="user", content="test")]
        done_events = []
        async for event in provider.stream_chat(messages):
            if event.event_type == "done":
                done_events.append(event)
        assert len(done_events) == 1
        assert isinstance(done_events[0].data, LLMResponse)

    async def test_stream_chat_with_tool_calls(self) -> None:
        """工具调用流式事件序列验证"""
        provider = MockProviderWithToolCall()
        messages = [Message(role="user", content="读取文件")]
        tools = [
            ToolDefinition(
                name="read_file",
                description="读取文件",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            )
        ]
        events: list[StreamEvent] = []
        async for event in provider.stream_chat(messages, tools=tools):
            events.append(event)

        types = [e.event_type for e in events]
        assert "tool_call_start" in types
        assert "tool_call_delta" in types
        assert "tool_call_end" in types
        assert "done" in types

        # 验证 tool_call_end 包含完整 ToolCall
        end_event = next(e for e in events if e.event_type == "tool_call_end")
        assert isinstance(end_event.data, ToolCall)
        assert end_event.data.arguments == {"path": "main.py"}

    def test_calculate_cost(self) -> None:
        provider = MockProvider()
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500)
        cost = provider.calculate_cost(usage, "mock-model")
        # (1000/1000)*0.003 + (500/1000)*0.015 = 0.003 + 0.0075 = 0.0105
        assert abs(cost - 0.0105) < 1e-9

    def test_calculate_cost_zero_tokens(self) -> None:
        provider = MockProvider()
        cost = provider.calculate_cost(TokenUsage(), "mock-model")
        assert cost == 0.0


# ---------------------------------------------------------------------------
# 9. 异常体系
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_llm_error_base(self) -> None:
        err = LLMError("基础错误")
        assert str(err) == "基础错误"
        assert err.provider == ""
        assert err.original_error is None

    def test_llm_error_with_provider(self) -> None:
        err = LLMError("API 错误", provider="claude")
        assert "[claude]" in str(err)

    def test_llm_error_with_original(self) -> None:
        orig = ValueError("原始错误")
        err = LLMError("包装错误", provider="deepseek", original_error=orig)
        assert err.original_error is orig

    def test_auth_error_is_llm_error(self) -> None:
        err = LLMAuthError("Key 无效", provider="claude")
        assert isinstance(err, LLMError)
        assert isinstance(err, LLMAuthError)

    def test_rate_limit_error_retry_after(self) -> None:
        err = LLMRateLimitError("限速", provider="deepseek", retry_after=30.0)
        assert err.retry_after == 30.0
        assert isinstance(err, LLMError)

    def test_rate_limit_error_no_retry_after(self) -> None:
        err = LLMRateLimitError("限速")
        assert err.retry_after is None

    def test_timeout_error(self) -> None:
        err = LLMTimeoutError("请求超时", provider="claude")
        assert isinstance(err, LLMError)

    def test_response_error(self) -> None:
        err = LLMResponseError("JSON 解析失败", provider="openai")
        assert isinstance(err, LLMError)

    def test_exception_hierarchy(self) -> None:
        """所有子类均可被 except LLMError 捕获"""
        errors = [
            LLMAuthError("auth"),
            LLMRateLimitError("rate"),
            LLMTimeoutError("timeout"),
            LLMResponseError("parse"),
        ]
        for err in errors:
            try:
                raise err
            except LLMError:
                pass  # 应全部被捕获
            else:
                pytest.fail(f"{type(err).__name__} 未被 LLMError 捕获")

    def test_exception_not_swallowed_by_base_except(self) -> None:
        """可用具体子类区分不同错误"""
        try:
            raise LLMAuthError("auth error", provider="claude")
        except LLMRateLimitError:
            pytest.fail("不应被 LLMRateLimitError 捕获")
        except LLMAuthError:
            pass  # 正确被捕获


# ---------------------------------------------------------------------------
# 10. 序列化往返测试
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_tool_call_roundtrip(self) -> None:
        tc = ToolCall(id="r1", name="edit_file", arguments={"path": "a.py", "old": "x", "new": "y"})
        tc2 = ToolCall.model_validate(tc.model_dump())
        assert tc2 == tc

    def test_token_usage_roundtrip(self) -> None:
        u = TokenUsage(prompt_tokens=500, completion_tokens=200, estimated_cost=0.005)
        u2 = TokenUsage.model_validate(u.model_dump())
        assert u2.total_tokens == 700
        assert u2.estimated_cost == 0.005

    def test_message_with_tool_calls_roundtrip(self) -> None:
        tc = ToolCall(id="r2", name="write_file", arguments={"path": "b.py", "content": "pass"})
        m = Message(role="assistant", tool_calls=[tc])
        m2 = Message.model_validate(m.model_dump())
        assert m2.tool_calls[0].arguments["path"] == "b.py"

    def test_llm_response_full_roundtrip(self) -> None:
        tc = ToolCall(id="r3", name="run_command", arguments={"command": "pytest"})
        r = LLMResponse(
            content="执行测试",
            tool_calls=[tc],
            usage=TokenUsage(prompt_tokens=300, completion_tokens=100),
            model="claude-sonnet-4-6",
            stop_reason="tool_use",
        )
        r2 = LLMResponse.model_validate(r.model_dump())
        assert r2.content == r.content
        assert r2.tool_calls[0].name == "run_command"
        assert r2.usage.total_tokens == 400
        assert r2.stop_reason == "tool_use"

    def test_stream_event_roundtrip_text_delta(self) -> None:
        e = StreamEvent(event_type="text_delta", data="测试内容")
        e2 = StreamEvent.model_validate(e.model_dump())
        assert e2.event_type == "text_delta"
        assert e2.data == "测试内容"

    def test_json_serialization(self) -> None:
        """model_dump_json 生成合法 JSON，可反序列化"""
        import json
        r = LLMResponse(
            content="测试",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50),
            model="test-model",
        )
        json_str = r.model_dump_json()
        data = json.loads(json_str)
        r2 = LLMResponse.model_validate(data)
        assert r2.content == "测试"
        assert r2.usage.total_tokens == 150
