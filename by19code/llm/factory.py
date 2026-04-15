"""BY19Code LLM Provider 工厂【T07】

职责
----
- 维护 name → 类 的注册表（_providers），解耦 Provider 实例化细节
- 根据 AppConfig 自动选择并实例化正确的 Provider
- 提供运行时切换入口（switch_provider），供 /model 命令调用

默认注册项（模块加载时自动执行）
----------------------------------
  "claude"   → ClaudeProvider
  "deepseek" → OpenAICompatibleProvider
  "kimi"     → OpenAICompatibleProvider
  "doubao"   → OpenAICompatibleProvider
  "glm"      → OpenAICompatibleProvider

扩展方式
--------
  from by19code.llm.factory import LLMFactory
  LLMFactory.register("my_provider", MyProviderClass)
"""
from __future__ import annotations

import logging
from typing import Any

from by19code.config.settings import AppConfig, LLMProviderConfig
from by19code.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class LLMFactory:
    """LLM Provider 工厂

    类级别注册表（_providers）将 provider 名称映射到对应的类。
    工厂本身无实例状态，所有方法均为 classmethod。

    注册表内容
    ----------
    初始化时自动注册 "claude" 和 "deepseek" 两个默认 Provider。
    可通过 register() 追加自定义 Provider。
    """

    # 类级别注册表：name → Provider 类
    _providers: dict[str, type[LLMProvider]] = {}

    # ------------------------------------------------------------------
    # 注册与查询
    # ------------------------------------------------------------------

    @classmethod
    def register(
        cls,
        name: str,
        provider_class: type[LLMProvider],
    ) -> None:
        """注册 Provider。

        参数
        ----
        name           : Provider 标识名（小写，如 "claude" / "deepseek"）
        provider_class : LLMProvider 的具体子类（不实例化，仅记录类引用）
        """
        cls._providers[name] = provider_class
        logger.debug(
            "[LLMFactory] 注册 Provider: %s → %s",
            name, provider_class.__name__,
        )

    @classmethod
    def list_providers(cls) -> list[str]:
        """返回所有已注册 Provider 名称（升序排列）"""
        return sorted(cls._providers.keys())

    # ------------------------------------------------------------------
    # 创建接口
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, config: AppConfig) -> LLMProvider:
        """根据 config.active_provider 创建对应 Provider 实例。

        步骤
        ----
        1. 读取 config.active_provider 作为目标名称
        2. 在注册表中查找对应类；未找到则抛出 ValueError
        3. 在 config.llm_providers 中查找对应配置；未找到则抛出 ValueError
        4. 根据 provider_type 构造构造函数参数并实例化

        异常
        ----
        ValueError : Provider 未注册，或 config.llm_providers 中无匹配配置，
                     或 provider_type 未知
        """
        return cls.create_by_name(config.active_provider, config)

    @classmethod
    def create_by_name(cls, name: str, config: AppConfig) -> LLMProvider:
        """按名称创建指定 Provider 实例。

        与 create() 的区别：可指定任意名称，不限于 active_provider。
        供 switch_provider() 和测试使用。

        参数
        ----
        name   : Provider 名称（必须已通过 register() 注册）
        config : 包含 llm_providers 列表的应用配置

        异常
        ----
        ValueError : 名称未注册，或配置列表中无对应 Provider
        """
        # 步骤 1：查找注册类
        if name not in cls._providers:
            available = cls.list_providers()
            raise ValueError(
                f"未注册的 Provider: '{name}'。"
                f"已注册的 Provider: {available}"
            )

        provider_class = cls._providers[name]

        # 步骤 2：从配置中取出 LLMProviderConfig
        provider_cfg = config.get_provider(name)
        if provider_cfg is None:
            raise ValueError(
                f"未找到 Provider 配置: '{name}'。"
                f"请在 config.json 的 llm_providers 中添加对应配置。"
            )

        # 步骤 3：构造参数并实例化
        kwargs = cls._build_kwargs(name, provider_cfg)
        instance = provider_class(**kwargs)

        logger.debug(
            "[LLMFactory] 创建 Provider: %s（%s）",
            name, provider_class.__name__,
        )
        return instance

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @classmethod
    def _build_kwargs(
        cls,
        name: str,
        cfg: LLMProviderConfig,
    ) -> dict[str, Any]:
        """根据 provider_type 构造 Provider 构造函数所需的 kwargs。

        provider_type 对应关系
        ----------------------
        "anthropic"   → ClaudeProvider(api_key, model, base_url)
        "openai_compat" → OpenAICompatibleProvider(api_key, model, base_url, provider_name)

        base_url 空字符串统一转为 None（使用各 Provider 的默认端点）。
        """
        base_url: str | None = cfg.base_url if cfg.base_url else None

        if cfg.provider_type == "anthropic":
            kwargs: dict[str, Any] = {
                "api_key": cfg.api_key,
                "model": cfg.model,
            }
            if base_url:
                kwargs["base_url"] = base_url
            return kwargs

        if cfg.provider_type == "openai_compat":
            kwargs = {
                "api_key": cfg.api_key,
                "model": cfg.model,
                "provider_name": name,
            }
            if base_url:
                kwargs["base_url"] = base_url
            return kwargs

        raise ValueError(
            f"未知的 provider_type: '{cfg.provider_type}'。"
            f"支持的类型: 'anthropic', 'openai_compat'。"
        )


# ---------------------------------------------------------------------------
# 运行时切换函数
# ---------------------------------------------------------------------------


def switch_provider(name: str, config: AppConfig) -> LLMProvider:
    """切换当前使用的 LLM Provider，供 /model 命令调用。

    原理：以 active_provider=name 的配置副本调用 LLMFactory.create()，
    不修改传入的 config 对象（不可变语义）。

    参数
    ----
    name   : 目标 Provider 名称（必须已注册且在 config.llm_providers 中有配置）
    config : 当前应用配置（不被修改）

    返回
    ----
    新的 LLMProvider 实例，调用方应替换当前的 provider 引用。

    异常
    ----
    ValueError : 同 LLMFactory.create_by_name()
    """
    logger.debug("[LLMFactory] 切换 Provider: %s", name)
    return LLMFactory.create_by_name(name, config)


# ---------------------------------------------------------------------------
# 模块加载时自动注册默认 Provider
# ---------------------------------------------------------------------------

# 延迟导入避免循环依赖：factory → base（已完成），factory → claude/openai（此处发生）
# ClaudeProvider / OpenAICompatibleProvider 的 __init__ 内部才会 import anthropic/openai，
# 因此此处仅注册类引用，不触发 SDK 导入。

from by19code.llm.claude_provider import ClaudeProvider  # noqa: E402
from by19code.llm.openai_provider import OpenAICompatibleProvider  # noqa: E402

# 注册 Anthropic Provider
LLMFactory.register("claude", ClaudeProvider)

# 注册 OpenAI 兼容 Provider（所有使用 OpenAI API 格式的模型）
LLMFactory.register("deepseek", OpenAICompatibleProvider)
LLMFactory.register("kimi", OpenAICompatibleProvider)
LLMFactory.register("doubao", OpenAICompatibleProvider)
LLMFactory.register("glm", OpenAICompatibleProvider)
