"""BY19Code 对话引擎单元测试【T11】

测试覆盖
--------
1. 引擎初始化
2. 普通对话（无工具调用）
3. 带工具调用的对话
4. 工具调用循环
5. 工具调用次数限制
6. 模型切换
7. 费用汇总
8. 清空历史
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from by19code.core.engine import ChatEngine
from by19code.config.settings import AppConfig, LLMProviderConfig, SafetyConfig
from by19code.llm.base import (
    Message,
    StreamEvent,
    LLMResponse,
    TokenUsage,
    ToolCall,
)


@pytest.fixture
def temp_project():
    """创建临时项目目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config():
    """测试配置"""
    return AppConfig(
        version="0.1.0",
        llm_providers=[
            LLMProviderConfig(
                name="test_provider",
                display_name="Test Provider",
                provider_type="anthropic",
                api_key="test-key",
                base_url="https://api.test.com",
                model="test-model",
                max_tokens=4096,
                cost_per_1k_input=1.0,
                cost_per_1k_output=2.0,
            )
        ],
        active_provider="test_provider",
        safety=SafetyConfig(
            command_timeout_seconds=5,
            max_tool_rounds=3,  # 限制为 3 轮，便于测试
        ),
    )


class TestChatEngineInit:
    """测试引擎初始化"""

    @patch("by19code.core.engine.LLMFactory.create")
    def test_engine_initialization(self, mock_create, temp_project, test_config):
        """测试引擎初始化"""
        mock_provider = MagicMock()
        mock_provider.provider_name = "test_provider"
        mock_create.return_value = mock_provider

        engine = ChatEngine(test_config, temp_project)

        assert engine.config == test_config
        assert engine.project_root == temp_project.resolve()
        assert engine.provider == mock_provider
        assert len(engine.messages) == 1  # System prompt
        assert engine.messages[0].role == "system"
        assert "Windows" in engine.messages[0].content

    @patch("by19code.core.engine.LLMFactory.create")
    def test_system_prompt_contains_project_path(self, mock_create, temp_project, test_config):
        """测试 System Prompt 包含项目路径"""
        mock_provider = MagicMock()
        mock_create.return_value = mock_provider

        engine = ChatEngine(test_config, temp_project)

        system_content = engine.messages[0].content
        assert str(temp_project.resolve()) in system_content


class TestChatSimple:
    """测试普通对话（无工具调用）"""

    @pytest.mark.asyncio
    @patch("by19code.core.engine.LLMFactory.create")
    @patch("by19code.core.engine.get_db")
    async def test_simple_chat_no_tools(self, mock_get_db, mock_create, temp_project, test_config):
        """测试简单对话（无工具调用）"""
        # Mock Provider
        mock_provider = MagicMock()
        mock_provider.provider_name = "test_provider"

        # Mock stream_chat 返回简单文本回复
        async def mock_stream(*args, **kwargs):
            yield StreamEvent(event_type="text_delta", data="Hello")
            yield StreamEvent(event_type="text_delta", data=" World")
            yield StreamEvent(
                event_type="done",
                data=LLMResponse(
                    content="Hello World",
                    tool_calls=None,
                    usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
                    model="test-model",
                    stop_reason="end_turn",
                ),
            )

        mock_provider.stream_chat = mock_stream
        mock_create.return_value = mock_provider

        # Mock database
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        # 创建引擎
        engine = ChatEngine(test_config, temp_project)

        # 执行对话
        events = []
        async for event in engine.chat("Hello"):
            events.append(event)

        # 验证
        assert len(events) > 0
        text_events = [e for e in events if e.event_type == "text_delta"]
        assert len(text_events) == 2

        # 验证消息历史
        assert len(engine.messages) == 3  # system + user + assistant
        assert engine.messages[1].role == "user"
        assert engine.messages[1].content == "Hello"
        assert engine.messages[2].role == "assistant"


class TestChatWithTools:
    """测试带工具调用的对话"""

    @pytest.mark.asyncio
    @patch("by19code.core.engine.LLMFactory.create")
    @patch("by19code.core.engine.execute_tool")
    @patch("by19code.core.engine.get_db")
    async def test_chat_with_single_tool_call(
        self, mock_get_db, mock_execute_tool, mock_create, temp_project, test_config
    ):
        """测试单次工具调用"""
        # Mock Provider
        mock_provider = MagicMock()
        mock_provider.provider_name = "test_provider"

        # 第一轮：LLM 调用工具
        async def mock_stream_round1():
            yield StreamEvent(
                event_type="tool_call_end",
                data=ToolCall(id="call_1", name="read_file", arguments={"path": "test.txt"}),
            )
            yield StreamEvent(
                event_type="done",
                data=LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="call_1", name="read_file", arguments={"path": "test.txt"})],
                    usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
                    model="test-model",
                    stop_reason="tool_use",
                ),
            )

        # 第二轮：LLM 看到工具结果后给出最终回复
        async def mock_stream_round2():
            yield StreamEvent(event_type="text_delta", data="文件内容是...")
            yield StreamEvent(
                event_type="done",
                data=LLMResponse(
                    content="文件内容是...",
                    tool_calls=None,
                    usage=TokenUsage(prompt_tokens=20, completion_tokens=10),
                    model="test-model",
                    stop_reason="end_turn",
                ),
            )

        # Use side_effect with the functions themselves, not their results
        call_count = 0
        async def mock_stream_selector(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                async for event in mock_stream_round1():
                    yield event
            else:
                async for event in mock_stream_round2():
                    yield event

        mock_provider.stream_chat = mock_stream_selector
        mock_create.return_value = mock_provider

        # Mock tool execution
        mock_execute_tool.return_value = "[文件] 读取成功: test.txt\n\nHello World"

        # Mock database
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        # 创建引擎
        engine = ChatEngine(test_config, temp_project)

        # 执行对话
        events = []
        async for event in engine.chat("读取 test.txt"):
            events.append(event)

        # 验证工具被调用
        mock_execute_tool.assert_called_once()

        # 验证消息历史
        # system + user + assistant(tool_call) + tool + assistant(final)
        assert len(engine.messages) == 5
        assert engine.messages[2].tool_calls is not None
        assert engine.messages[3].role == "tool"


class TestToolCallLoop:
    """测试工具调用循环"""

    @pytest.mark.asyncio
    @patch("by19code.core.engine.LLMFactory.create")
    @patch("by19code.core.engine.execute_tool")
    @patch("by19code.core.engine.get_db")
    async def test_tool_call_limit(
        self, mock_get_db, mock_execute_tool, mock_create, temp_project, test_config
    ):
        """测试工具调用次数限制"""
        # Mock Provider - 每次都返回工具调用（模拟无限循环）
        mock_provider = MagicMock()
        mock_provider.provider_name = "test_provider"

        async def mock_stream_with_tool():
            yield StreamEvent(
                event_type="tool_call_end",
                data=ToolCall(id="call_1", name="read_file", arguments={"path": "test.txt"}),
            )
            yield StreamEvent(
                event_type="done",
                data=LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="call_1", name="read_file", arguments={"path": "test.txt"})],
                    usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
                    model="test-model",
                    stop_reason="tool_use",
                ),
            )

        # Return the generator function itself, not a list of results
        async def mock_stream_infinite(*args, **kwargs):
            async for event in mock_stream_with_tool():
                yield event

        mock_provider.stream_chat = mock_stream_infinite
        mock_create.return_value = mock_provider

        # Mock tool execution
        mock_execute_tool.return_value = "[文件] 读取成功"

        # Mock database
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        # 创建引擎
        engine = ChatEngine(test_config, temp_project)

        # 执行对话
        events = []
        async for event in engine.chat("测试"):
            events.append(event)

        # 验证达到限制（max_tool_rounds = 3）
        error_events = [e for e in events if e.event_type == "error"]
        assert len(error_events) > 0
        assert "超过限制" in error_events[-1].data


class TestModelSwitch:
    """测试模型切换"""

    @pytest.mark.asyncio
    @patch("by19code.core.engine.LLMFactory.create")
    async def test_switch_model_success(self, mock_create, temp_project, test_config):
        """测试成功切换模型"""
        # 初始 Provider
        mock_provider1 = MagicMock()
        mock_provider1.provider_name = "test_provider"

        # 新 Provider
        mock_provider2 = MagicMock()
        mock_provider2.provider_name = "new_provider"

        mock_create.side_effect = [mock_provider1, mock_provider2]

        # 创建引擎
        engine = ChatEngine(test_config, temp_project)
        assert engine.provider.provider_name == "test_provider"

        # 切换模型
        result = await engine.switch_model("new_provider")

        assert "[成功]" in result
        assert engine.provider.provider_name == "new_provider"


class TestCostSummary:
    """测试费用汇总"""

    @pytest.mark.asyncio
    @patch("by19code.core.engine.LLMFactory.create")
    @patch("by19code.core.engine.get_db")
    async def test_get_cost_summary(self, mock_get_db, mock_create, temp_project, test_config):
        """测试获取费用汇总"""
        mock_provider = MagicMock()
        mock_provider.provider_name = "test_provider"
        mock_create.return_value = mock_provider

        # Mock database
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        # Mock get_total_cost from the correct module
        with patch("by19code.db.models.get_total_cost", return_value=0.123456):
            engine = ChatEngine(test_config, temp_project)
            summary = await engine.get_cost_summary()

            assert "[费用汇总]" in summary
            assert "$0.123456" in summary


class TestClearHistory:
    """测试清空历史"""

    @patch("by19code.core.engine.LLMFactory.create")
    def test_clear_history(self, mock_create, temp_project, test_config):
        """测试清空对话历史"""
        mock_provider = MagicMock()
        mock_create.return_value = mock_provider

        engine = ChatEngine(test_config, temp_project)

        # 添加一些消息
        engine.messages.append(Message(role="user", content="test1"))
        engine.messages.append(Message(role="assistant", content="response1"))

        assert len(engine.messages) == 3  # system + user + assistant

        # 清空历史
        result = engine.clear_history()

        assert "[成功]" in result
        assert len(engine.messages) == 1  # 只保留 system
        assert engine.messages[0].role == "system"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
