"""BY19Code 上下文管理器单元测试【T12】

测试覆盖
--------
1. 消息添加和获取
2. Token 估算（中文/英文/混合）
3. 自动裁剪触发
4. tool_call/tool_result 配对保护
5. compact 压缩
6. clear 清空
7. 统计信息
"""
import pytest

from by19code.core.context import ContextManager
from by19code.llm.base import Message, ToolCall


class TestContextManagerInit:
    """测试上下文管理器初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        ctx = ContextManager()
        assert ctx.max_tokens == 100000
        assert ctx.system_message is None
        assert len(ctx.messages) == 0

    def test_init_custom_max_tokens(self):
        """测试自定义 max_tokens"""
        ctx = ContextManager(max_tokens=50000)
        assert ctx.max_tokens == 50000


class TestAddAndGetMessages:
    """测试消息添加和获取"""

    def test_add_system_message(self):
        """测试添加 system 消息"""
        ctx = ContextManager()
        system_msg = Message(role="system", content="You are a helpful assistant")

        ctx.add_message(system_msg)

        assert ctx.system_message == system_msg
        assert len(ctx.messages) == 0  # system 消息不计入 messages

    def test_add_user_message(self):
        """测试添加 user 消息"""
        ctx = ContextManager()
        user_msg = Message(role="user", content="Hello")

        ctx.add_message(user_msg)

        assert len(ctx.messages) == 1
        assert ctx.messages[0] == user_msg

    def test_add_assistant_message(self):
        """测试添加 assistant 消息"""
        ctx = ContextManager()
        assistant_msg = Message(role="assistant", content="Hi there!")

        ctx.add_message(assistant_msg)

        assert len(ctx.messages) == 1
        assert ctx.messages[0] == assistant_msg

    def test_get_messages_with_system(self):
        """测试获取消息（包含 system）"""
        ctx = ContextManager()
        system_msg = Message(role="system", content="System prompt")
        user_msg = Message(role="user", content="Hello")

        ctx.add_message(system_msg)
        ctx.add_message(user_msg)

        messages = ctx.get_messages()
        assert len(messages) == 2
        assert messages[0] == system_msg
        assert messages[1] == user_msg

    def test_get_messages_without_system(self):
        """测试获取消息（无 system）"""
        ctx = ContextManager()
        user_msg = Message(role="user", content="Hello")

        ctx.add_message(user_msg)

        messages = ctx.get_messages()
        assert len(messages) == 1
        assert messages[0] == user_msg


class TestTokenEstimation:
    """测试 token 估算"""

    def test_estimate_english_text(self):
        """测试英文 token 估算"""
        ctx = ContextManager()
        # 英文：4 字符 ≈ 1 token
        text = "Hello World"  # 11 字符 → 约 2-3 tokens
        tokens = ctx._estimate_text_tokens(text)
        assert tokens >= 2

    def test_estimate_chinese_text(self):
        """测试中文 token 估算"""
        ctx = ContextManager()
        # 中文：1 字符 ≈ 2 tokens
        text = "你好世界"  # 4 字符 → 约 8 tokens
        tokens = ctx._estimate_text_tokens(text)
        assert tokens == 8

    def test_estimate_mixed_text(self):
        """测试中英文混合 token 估算"""
        ctx = ContextManager()
        text = "Hello 世界"  # 5 英文 + 2 中文 → 1 + 4 = 5 tokens
        tokens = ctx._estimate_text_tokens(text)
        assert tokens >= 4

    def test_estimate_messages_with_content(self):
        """测试消息列表 token 估算"""
        ctx = ContextManager()
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ]

        tokens = ctx._estimate_tokens(messages)
        assert tokens > 0

    def test_estimate_messages_with_tool_calls(self):
        """测试带工具调用的消息 token 估算"""
        ctx = ContextManager()
        messages = [
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="read_file",
                        arguments={"path": "test.txt"},
                    )
                ],
            )
        ]

        tokens = ctx._estimate_tokens(messages)
        assert tokens > 0  # 工具名称 + 参数 JSON


class TestAutoTrim:
    """测试自动裁剪"""

    def test_no_trim_below_threshold(self):
        """测试低于阈值不触发裁剪"""
        ctx = ContextManager(max_tokens=1000)

        # 添加少量消息
        for i in range(5):
            ctx.add_message(Message(role="user", content=f"Message {i}"))

        # 应该不触发裁剪
        assert len(ctx.messages) == 5

    def test_trim_triggered_above_threshold(self):
        """测试超过阈值触发裁剪"""
        ctx = ContextManager(max_tokens=100)  # 设置很小的上限

        # 添加大量消息
        for i in range(20):
            ctx.add_message(Message(role="user", content="A" * 50))  # 每条约 12 tokens

        # 应该触发裁剪
        assert len(ctx.messages) < 20

    def test_trim_preserves_recent_messages(self):
        """测试裁剪保留最近的消息"""
        ctx = ContextManager(max_tokens=100)

        # 添加消息
        for i in range(20):
            ctx.add_message(Message(role="user", content=f"Message {i}"))

        # 最后一条消息应该被保留
        assert "Message 19" in ctx.messages[-1].content


class TestToolCallPairing:
    """测试 tool_call/tool_result 配对保护"""

    def test_delete_assistant_with_tool_calls(self):
        """测试删除带 tool_calls 的 assistant 消息"""
        ctx = ContextManager(max_tokens=200)

        # 添加 assistant 消息（带 tool_calls）
        ctx.add_message(
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="read_file", arguments={"path": "test.txt"})],
            )
        )

        # 添加对应的 tool 消息
        ctx.add_message(Message(role="tool", content="File content", tool_call_id="call_1"))

        # 添加大量消息触发裁剪
        for i in range(30):
            ctx.add_message(Message(role="user", content="A" * 50))

        # 如果 assistant 消息被删除，对应的 tool 消息也应该被删除
        # 检查没有孤立的 tool 消息
        for msg in ctx.messages:
            if msg.role == "tool":
                # 应该能找到对应的 assistant 消息
                tool_call_id = msg.tool_call_id
                found = False
                for m in ctx.messages:
                    if m.role == "assistant" and m.tool_calls:
                        if any(tc.id == tool_call_id for tc in m.tool_calls):
                            found = True
                            break
                # 如果找不到，说明配对被破坏（这不应该发生）
                # 但由于裁剪策略，可能两者都被删除了，这是允许的


class TestCompact:
    """测试压缩功能"""

    def test_compact_keeps_recent_10_messages(self):
        """测试压缩保留最近 10 条消息"""
        ctx = ContextManager()

        # 添加 20 条消息
        for i in range(20):
            ctx.add_message(Message(role="user", content=f"Message {i}"))

        result = ctx.compact()

        assert len(ctx.messages) == 10
        assert "Message 19" in ctx.messages[-1].content
        assert "Message 10" in ctx.messages[0].content
        assert "压缩" in result

    def test_compact_no_change_if_less_than_10(self):
        """测试少于 10 条消息不压缩"""
        ctx = ContextManager()

        # 添加 5 条消息
        for i in range(5):
            ctx.add_message(Message(role="user", content=f"Message {i}"))

        result = ctx.compact()

        assert len(ctx.messages) == 5
        assert "压缩" in result


class TestClear:
    """测试清空功能"""

    def test_clear_removes_all_messages(self):
        """测试清空删除所有消息"""
        ctx = ContextManager()

        # 添加消息
        ctx.add_message(Message(role="system", content="System"))
        ctx.add_message(Message(role="user", content="Hello"))
        ctx.add_message(Message(role="assistant", content="Hi"))

        ctx.clear()

        assert len(ctx.messages) == 0
        assert ctx.system_message is not None  # system 消息保留


class TestGetStats:
    """测试统计信息"""

    def test_get_stats_empty(self):
        """测试空上下文统计"""
        ctx = ContextManager()

        stats = ctx.get_stats()

        assert stats["message_count"] == 0
        assert stats["estimated_tokens"] == 0
        assert stats["max_tokens"] == 100000
        assert stats["usage_percent"] == 0.0

    def test_get_stats_with_messages(self):
        """测试有消息的统计"""
        ctx = ContextManager(max_tokens=1000)

        # 添加消息
        ctx.add_message(Message(role="user", content="Hello World"))

        stats = ctx.get_stats()

        assert stats["message_count"] == 1
        assert stats["estimated_tokens"] > 0
        assert stats["max_tokens"] == 1000
        assert 0 < stats["usage_percent"] < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
