"""by19code.llm.factory 单元测试【T07】

测试分组
--------
  TestRegister             - register() / list_providers() 注册机制
  TestDefaultRegistrations - 模块加载时自动注册的默认 Provider
  TestCreate               - create(config) 按 active_provider 实例化
  TestCreateByName         - create_by_name(name, config) 按名称实例化
  TestBuildKwargs          - _build_kwargs() provider_type 参数构造
  TestSwitchProvider       - switch_provider() 运行时切换
  TestLLMPackageImports    - by19code.llm __init__.py 导出完整性

注意：所有测试使用轻量 Mock Provider（_MockBase 子类），
不构造真实 ClaudeProvider / OpenAICompatibleProvider，
因此无需 anthropic / openai SDK 安装。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from by19code.config.settings import AppConfig, LLMProviderConfig
from by19code.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    StreamEvent,
    ToolDefinition,
    TokenUsage,
)
from by19code.llm.factory import LLMFactory, switch_provider


# ---------------------------------------------------------------------------
# 测试用 Mock Provider（无 SDK 依赖）
# ---------------------------------------------------------------------------


class _MockBase(LLMProvider):
    """轻量 Provider 基类，记录构造参数，满足 ABC 约束"""

    def __init__(self, **kwargs: Any) -> None:
        self._init_kwargs = kwargs

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        return LLMResponse()

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(event_type="done", data=None)

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        return 0.0


class MockClaude(_MockBase):
    """模拟 ClaudeProvider（anthropic 格式）"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    @property
    def provider_name(self) -> str:
        return "claude"


class MockDeepSeek(_MockBase):
    """模拟 OpenAICompatibleProvider（openai_compat 格式）"""

    def __init__(
        self,
        api_key: str,
        model: str,
        provider_name: str = "deepseek",
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key, model=model,
            provider_name=provider_name, base_url=base_url,
        )
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._pname = provider_name

    @property
    def provider_name(self) -> str:
        return self._pname


class MockGeneric(_MockBase):
    """通用 Mock，用于注册/列表测试"""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def provider_name(self) -> str:
        return "generic"


# ---------------------------------------------------------------------------
# 配置构造辅助函数
# ---------------------------------------------------------------------------


def _claude_cfg(
    api_key: str = "sk-ant-test",
    model: str = "claude-sonnet-4-20250514",
    base_url: str = "",
) -> LLMProviderConfig:
    return LLMProviderConfig(
        name="claude",
        display_name="Claude",
        provider_type="anthropic",
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


def _deepseek_cfg(
    api_key: str = "sk-ds-test",
    model: str = "deepseek-chat",
    base_url: str = "https://api.deepseek.com",
) -> LLMProviderConfig:
    return LLMProviderConfig(
        name="deepseek",
        display_name="DeepSeek",
        provider_type="openai_compat",
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


def _app_config(
    active: str = "claude",
    providers: list[LLMProviderConfig] | None = None,
) -> AppConfig:
    return AppConfig(
        active_provider=active,
        llm_providers=providers or [],
    )


# ---------------------------------------------------------------------------
# Fixture：每个测试前后还原 _providers（测试隔离）
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_registry():
    """保存并在测试结束后还原 LLMFactory._providers，防止测试间污染"""
    saved = dict(LLMFactory._providers)
    yield
    LLMFactory._providers.clear()
    LLMFactory._providers.update(saved)


# ---------------------------------------------------------------------------
# 1. register / list_providers
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_adds_to_registry(self):
        LLMFactory.register("mock_a", MockGeneric)
        assert "mock_a" in LLMFactory._providers
        assert LLMFactory._providers["mock_a"] is MockGeneric

    def test_register_multiple(self):
        LLMFactory.register("mock_x", MockGeneric)
        LLMFactory.register("mock_y", MockGeneric)
        providers = LLMFactory.list_providers()
        assert "mock_x" in providers
        assert "mock_y" in providers

    def test_register_overwrite(self):
        """重复注册同名覆盖原有映射"""
        LLMFactory.register("mock_ow", MockClaude)
        LLMFactory.register("mock_ow", MockDeepSeek)
        assert LLMFactory._providers["mock_ow"] is MockDeepSeek

    def test_list_providers_sorted(self):
        LLMFactory._providers.clear()
        LLMFactory.register("zzz", MockGeneric)
        LLMFactory.register("aaa", MockGeneric)
        LLMFactory.register("mmm", MockGeneric)
        result = LLMFactory.list_providers()
        assert result == sorted(result)

    def test_list_providers_returns_list(self):
        result = LLMFactory.list_providers()
        assert isinstance(result, list)

    def test_list_providers_empty(self):
        LLMFactory._providers.clear()
        assert LLMFactory.list_providers() == []


# ---------------------------------------------------------------------------
# 2. 默认注册项（模块加载时自动执行）
# ---------------------------------------------------------------------------


class TestDefaultRegistrations:
    def test_claude_registered(self):
        assert "claude" in LLMFactory.list_providers()

    def test_deepseek_registered(self):
        assert "deepseek" in LLMFactory.list_providers()

    def test_claude_maps_to_real_class(self):
        """注册的类名为 ClaudeProvider（跳过 identity check，避免 reload 干扰）"""
        registered = LLMFactory._providers.get("claude")
        assert registered is not None
        assert registered.__name__ == "ClaudeProvider"
        assert issubclass(registered, LLMProvider)

    def test_deepseek_maps_to_real_class(self):
        """注册的类名为 OpenAICompatibleProvider"""
        registered = LLMFactory._providers.get("deepseek")
        assert registered is not None
        assert registered.__name__ == "OpenAICompatibleProvider"
        assert issubclass(registered, LLMProvider)

    def test_at_least_two_providers(self):
        assert len(LLMFactory.list_providers()) >= 2


# ---------------------------------------------------------------------------
# 3. create(config) — 使用 active_provider
# ---------------------------------------------------------------------------


class TestCreate:
    def test_creates_claude_provider(self):
        LLMFactory.register("claude", MockClaude)
        config = _app_config("claude", [_claude_cfg()])
        provider = LLMFactory.create(config)
        assert isinstance(provider, MockClaude)

    def test_creates_deepseek_provider(self):
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config("deepseek", [_deepseek_cfg()])
        provider = LLMFactory.create(config)
        assert isinstance(provider, MockDeepSeek)

    def test_api_key_passed_to_claude(self):
        LLMFactory.register("claude", MockClaude)
        config = _app_config("claude", [_claude_cfg(api_key="sk-ant-real")])
        provider = LLMFactory.create(config)
        assert isinstance(provider, MockClaude)
        assert provider.api_key == "sk-ant-real"

    def test_api_key_passed_to_deepseek(self):
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config("deepseek", [_deepseek_cfg(api_key="sk-ds-real")])
        provider = LLMFactory.create(config)
        assert isinstance(provider, MockDeepSeek)
        assert provider.api_key == "sk-ds-real"

    def test_model_passed_correctly(self):
        LLMFactory.register("claude", MockClaude)
        config = _app_config(
            "claude",
            [_claude_cfg(model="claude-haiku-4-5-20251001")],
        )
        provider = LLMFactory.create(config)
        assert provider.model == "claude-haiku-4-5-20251001"

    def test_unregistered_provider_raises_value_error(self):
        """未注册的 provider name 应抛出 ValueError"""
        config = _app_config("nonexistent_provider", [])
        with pytest.raises(ValueError, match="未注册的 Provider"):
            LLMFactory.create(config)

    def test_error_message_contains_name(self):
        config = _app_config("missing_one", [])
        with pytest.raises(ValueError) as exc_info:
            LLMFactory.create(config)
        assert "missing_one" in str(exc_info.value)

    def test_missing_provider_config_raises_value_error(self):
        """已注册但 config.llm_providers 中无对应配置，应抛出 ValueError"""
        LLMFactory.register("claude", MockClaude)
        config = _app_config("claude", [])   # 空 providers 列表
        with pytest.raises(ValueError, match="未找到 Provider 配置"):
            LLMFactory.create(config)

    def test_error_message_suggests_config_json(self):
        LLMFactory.register("claude", MockClaude)
        config = _app_config("claude", [])
        with pytest.raises(ValueError) as exc_info:
            LLMFactory.create(config)
        assert "config.json" in str(exc_info.value) or "llm_providers" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. create_by_name(name, config) — 按名称实例化
# ---------------------------------------------------------------------------


class TestCreateByName:
    def test_creates_non_active_provider(self):
        """active_provider 为 claude 时仍可创建 deepseek"""
        LLMFactory.register("claude", MockClaude)
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config(
            active="claude",
            providers=[_claude_cfg(), _deepseek_cfg()],
        )
        provider = LLMFactory.create_by_name("deepseek", config)
        assert isinstance(provider, MockDeepSeek)

    def test_creates_active_provider_by_name(self):
        LLMFactory.register("claude", MockClaude)
        config = _app_config("claude", [_claude_cfg()])
        provider = LLMFactory.create_by_name("claude", config)
        assert isinstance(provider, MockClaude)

    def test_unregistered_name_raises(self):
        config = _app_config("claude", [_claude_cfg()])
        with pytest.raises(ValueError, match="未注册的 Provider"):
            LLMFactory.create_by_name("unknown", config)

    def test_missing_config_raises(self):
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config("claude", [_claude_cfg()])  # 无 deepseek 配置
        with pytest.raises(ValueError, match="未找到 Provider 配置"):
            LLMFactory.create_by_name("deepseek", config)


# ---------------------------------------------------------------------------
# 5. _build_kwargs — provider_type 参数构造
# ---------------------------------------------------------------------------


class TestBuildKwargs:
    def test_anthropic_kwargs(self):
        cfg = _claude_cfg(api_key="key-a", model="m1", base_url="")
        kwargs = LLMFactory._build_kwargs("claude", cfg)
        assert kwargs["api_key"] == "key-a"
        assert kwargs["model"] == "m1"
        assert "base_url" not in kwargs      # 空字符串时不传 base_url

    def test_anthropic_with_custom_base_url(self):
        cfg = _claude_cfg(base_url="https://custom.proxy.example.com")
        kwargs = LLMFactory._build_kwargs("claude", cfg)
        assert kwargs["base_url"] == "https://custom.proxy.example.com"

    def test_openai_compat_kwargs(self):
        cfg = _deepseek_cfg(api_key="key-b", model="deepseek-chat")
        kwargs = LLMFactory._build_kwargs("deepseek", cfg)
        assert kwargs["api_key"] == "key-b"
        assert kwargs["model"] == "deepseek-chat"
        assert kwargs["provider_name"] == "deepseek"
        assert kwargs["base_url"] == "https://api.deepseek.com"

    def test_openai_compat_empty_base_url(self):
        """base_url 为空字符串时不传 base_url（使用 SDK 默认端点）"""
        cfg = _deepseek_cfg(base_url="")
        kwargs = LLMFactory._build_kwargs("deepseek", cfg)
        assert "base_url" not in kwargs

    def test_provider_name_injected_for_openai_compat(self):
        """openai_compat 自动注入 provider_name=name 参数"""
        cfg = _deepseek_cfg()
        kwargs = LLMFactory._build_kwargs("deepseek", cfg)
        assert kwargs["provider_name"] == "deepseek"

    def test_unknown_provider_type_raises(self):
        cfg = LLMProviderConfig(
            name="weird",
            display_name="Weird",
            provider_type="unknown_type",  # 非法 type
            api_key="k",
            base_url="",
            model="m",
        )
        with pytest.raises(ValueError, match="未知的 provider_type"):
            LLMFactory._build_kwargs("weird", cfg)

    def test_error_message_contains_type(self):
        cfg = LLMProviderConfig(
            name="x", display_name="X", provider_type="invalid",
            api_key="k", base_url="", model="m",
        )
        with pytest.raises(ValueError) as exc_info:
            LLMFactory._build_kwargs("x", cfg)
        assert "invalid" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 6. switch_provider(name, config) — 运行时切换
# ---------------------------------------------------------------------------


class TestSwitchProvider:
    def test_switch_returns_correct_type(self):
        LLMFactory.register("claude", MockClaude)
        config = _app_config("claude", [_claude_cfg()])
        provider = switch_provider("claude", config)
        assert isinstance(provider, MockClaude)

    def test_switch_to_non_active_provider(self):
        """active 为 claude 时可切换到 deepseek"""
        LLMFactory.register("claude", MockClaude)
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config(
            active="claude",
            providers=[_claude_cfg(), _deepseek_cfg()],
        )
        provider = switch_provider("deepseek", config)
        assert isinstance(provider, MockDeepSeek)

    def test_switch_does_not_modify_config(self):
        """switch_provider 不修改传入的 config 对象"""
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config(
            active="claude",
            providers=[_claude_cfg(), _deepseek_cfg()],
        )
        switch_provider("deepseek", config)
        # config.active_provider 不变
        assert config.active_provider == "claude"

    def test_switch_api_key_passed(self):
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config(
            "deepseek",
            [_deepseek_cfg(api_key="sk-switch-test")],
        )
        provider = switch_provider("deepseek", config)
        assert isinstance(provider, MockDeepSeek)
        assert provider.api_key == "sk-switch-test"

    def test_switch_to_unregistered_raises(self):
        config = _app_config("claude", [_claude_cfg()])
        with pytest.raises(ValueError, match="未注册的 Provider"):
            switch_provider("ghost", config)

    def test_switch_with_missing_config_raises(self):
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config("claude", [_claude_cfg()])  # 无 deepseek
        with pytest.raises(ValueError, match="未找到 Provider 配置"):
            switch_provider("deepseek", config)

    def test_switch_multiple_times(self):
        """多次切换均返回新实例"""
        LLMFactory.register("claude", MockClaude)
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config(
            "claude",
            [_claude_cfg(), _deepseek_cfg()],
        )
        p1 = switch_provider("claude", config)
        p2 = switch_provider("deepseek", config)
        p3 = switch_provider("claude", config)

        assert isinstance(p1, MockClaude)
        assert isinstance(p2, MockDeepSeek)
        assert isinstance(p3, MockClaude)
        assert p1 is not p3   # 每次都是新实例

    def test_switch_provider_name_attribute(self):
        """切换后 provider.provider_name 为目标 Provider 的标识名"""
        LLMFactory.register("deepseek", MockDeepSeek)
        config = _app_config(
            "deepseek",
            [_deepseek_cfg()],
        )
        provider = switch_provider("deepseek", config)
        assert provider.provider_name == "deepseek"


# ---------------------------------------------------------------------------
# 7. by19code.llm 包导出完整性
# ---------------------------------------------------------------------------


class TestLLMPackageImports:
    def test_base_classes_exported(self):
        import by19code.llm as llm
        assert hasattr(llm, "LLMProvider")
        assert hasattr(llm, "LLMFactory")
        assert hasattr(llm, "switch_provider")

    def test_provider_classes_exported(self):
        import by19code.llm as llm
        assert hasattr(llm, "ClaudeProvider")
        assert hasattr(llm, "OpenAICompatibleProvider")

    def test_data_models_exported(self):
        import by19code.llm as llm
        for name in ("Message", "ToolCall", "ToolDefinition",
                     "TokenUsage", "LLMResponse", "StreamEvent", "StreamEventType"):
            assert hasattr(llm, name), f"缺少导出: {name}"

    def test_exceptions_exported(self):
        import by19code.llm as llm
        for name in ("LLMError", "LLMAuthError", "LLMRateLimitError",
                     "LLMTimeoutError", "LLMResponseError"):
            assert hasattr(llm, name), f"缺少导出: {name}"

    def test_exception_hierarchy_via_package(self):
        from by19code.llm import LLMError, LLMAuthError, LLMRateLimitError
        assert issubclass(LLMAuthError, LLMError)
        assert issubclass(LLMRateLimitError, LLMError)

    def test_llm_provider_is_abstract(self):
        """LLMProvider 不可直接实例化（ABC）"""
        from by19code.llm import LLMProvider
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_factory_and_switch_consistent(self):
        """__init__.py 导出的 LLMFactory 与 switch_provider 来自同一模块"""
        from by19code.llm import LLMFactory as F1, switch_provider as s1
        from by19code.llm.factory import LLMFactory as F2, switch_provider as s2
        assert F1 is F2
        assert s1 is s2

    def test_all_list_complete(self):
        """__all__ 包含所有重要名称"""
        import by19code.llm as llm
        all_names = getattr(llm, "__all__", [])
        for expected in (
            "LLMProvider", "LLMFactory", "switch_provider",
            "ClaudeProvider", "OpenAICompatibleProvider",
            "Message", "LLMResponse", "StreamEvent",
            "LLMError", "LLMAuthError",
        ):
            assert expected in all_names, f"__all__ 缺少: {expected}"
