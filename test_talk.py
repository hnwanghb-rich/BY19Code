"""
BY19Code 验收节点 A 测试脚本 — test_talk.py

验收目标（T01-T07 完成后执行）：
  [1] Claude 流式回复正常
  [2] 切换配置到 DeepSeek 后回复正常
  [3] SQLite 中有 token_usage 记录
  [4] 费用计算正确

使用方式：
  在项目根目录执行：python test_talk.py

前置条件：
  - T01-T07 全部完成
  - 环境变量已设置：BY19CODE_CLAUDE_API_KEY, BY19CODE_DEEPSEEK_API_KEY
  - 依赖已安装：pip install -e .
"""

import asyncio
import sys
import os
import sqlite3
import warnings  # 添加 warnings 模块
from pathlib import Path
from datetime import datetime

# Windows asyncio 兼容性设置（消除 DeprecationWarning）
if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass

# ─────────────────────────────────────────────────────────────
# 辅助工具
# ─────────────────────────────────────────────────────────────

# 测试结果统计
_results: list[tuple[str, bool, str]] = []
_output_lines: list[str] = []  # 用于保存所有输出行

def log_pass(test_name: str, detail: str = "") -> None:
    """记录测试通过"""
    _results.append((test_name, True, detail))
    line = f"  [通过] {test_name}" + (f" — {detail}" if detail else "")
    print(line)
    _output_lines.append(line)

def log_fail(test_name: str, detail: str = "") -> None:
    """记录测试失败"""
    _results.append((test_name, False, detail))
    line = f"  [失败] {test_name}" + (f" — {detail}" if detail else "")
    print(line)
    _output_lines.append(line)

def print_line(text: str = "") -> None:
    """打印并记录到输出缓冲区"""
    print(text)
    _output_lines.append(text)

def print_summary() -> None:
    """输出测试汇总"""
    total = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed

    separator = "=" * 60
    print_line()
    print_line(separator)
    print_line(f"  验收节点 A 测试结果：{passed}/{total} 通过")
    print_line(separator)

    if failed > 0:
        print_line()
        print_line("  失败项：")
        for name, ok, detail in _results:
            if not ok:
                print_line(f"    - {name}: {detail}")
        print_line()
        print_line("  !! 请修复以上问题后重新测试 !!")
    else:
        print_line()
        print_line("  全部通过！可以继续 T08。")

    print_line(separator)

    # 写入到文件
    try:
        report_path = Path("test-rep.txt")
        report_path.write_text("\n".join(_output_lines), encoding="utf-8")
        print(f"\n测试报告已保存到：{report_path.absolute()}")
    except Exception as e:
        print(f"\n[警告] 无法保存测试报告：{e}")

def get_db_path() -> Path:
    """获取默认数据库路径"""
    return Path.home() / ".by19code" / "by19code.db"


def create_test_config():
    """创建测试用配置（包含 claude 和 deepseek provider）"""
    from by19code.config.settings import AppConfig, LLMProviderConfig

    claude_key = os.environ.get("BY19CODE_CLAUDE_API_KEY", "")
    # 🔴 关键修改：直接用 https://hone.vvvv.ee（不带 /v1）
    # anthropic SDK 会自动拼接路径，但中转站可能不需要 /v1
    claude_base_url = os.environ.get("BY19CODE_CLAUDE_BASE_URL", "https://hone.vvvv.ee")
    deepseek_key = os.environ.get("BY19CODE_DEEPSEEK_API_KEY", "")
    deepseek_base_url = os.environ.get("BY19CODE_DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    providers = []

    # Claude 配置（使用原生 Anthropic 协议）
    if claude_key:
        providers.append(LLMProviderConfig(
            name="claude",
            display_name="Claude",
            provider_type="anthropic",  # 使用原生 Anthropic SDK
            api_key=claude_key,
            base_url=claude_base_url,  # 不带 /v1，SDK 会自动添加
            model="claude-sonnet-4-6",  # 使用你实际的模型
            max_tokens=8192,
            cost_per_1k_input=3.0,
            cost_per_1k_output=15.0,
        ))

    # DeepSeek 配置
    if deepseek_key:
        providers.append(LLMProviderConfig(
            name="deepseek",
            display_name="DeepSeek",
            provider_type="openai_compat",
            api_key=deepseek_key,
            base_url=deepseek_base_url,
            model="deepseek-chat",
            max_tokens=8192,
            cost_per_1k_input=0.14,
            cost_per_1k_output=0.28,
        ))

    return AppConfig(
        version="0.1.0",
        llm_providers=providers,
        active_provider="claude" if claude_key else "deepseek",
    )


# ─────────────────────────────────────────────────────────────
# 测试 T01：项目脚手架
# ─────────────────────────────────────────────────────────────

async def test_t01_scaffold() -> None:
    """测试 T01 项目脚手架是否完整"""
    print_line("\n【测试 T01】项目脚手架")
    print_line("-" * 40)

    # 检查目录结构
    required_dirs = [
        "by19code",
        "by19code/cli",
        "by19code/core",
        "by19code/llm",
        "by19code/file_ops",
        "by19code/git_ops",
        "by19code/db",
        "by19code/config",
        "docs",
        "tests",
    ]

    for dir_path in required_dirs:
        full_path = Path(dir_path)
        if full_path.exists() and full_path.is_dir():
            log_pass(f"目录存在", f"{dir_path}")
        else:
            log_fail(f"目录缺失", f"{dir_path}")

    # 检查关键文件
    required_files = [
        "pyproject.toml",
        ".gitignore",
        ".env.example",
        "CLAUDE.md",
        "by19code/__init__.py",
        "by19code/llm/__init__.py",
        "by19code/config/__init__.py",
        "by19code/db/__init__.py",
    ]

    for file_path in required_files:
        full_path = Path(file_path)
        if full_path.exists() and full_path.is_file():
            log_pass(f"文件存在", f"{file_path}")
        else:
            log_fail(f"文件缺失", f"{file_path}")

    # 检查 pyproject.toml 依赖
    try:
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            required_deps = ["click", "rich", "anthropic", "openai", "aiosqlite", "pydantic"]
            for dep in required_deps:
                if dep in content:
                    log_pass(f"依赖声明", f"{dep}")
                else:
                    log_fail(f"依赖缺失", f"{dep}")
    except Exception as e:
        log_fail("pyproject.toml 检查", f"{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# 测试 T02：配置管理
# ─────────────────────────────────────────────────────────────

async def test_t02_config() -> None:
    """测试 T02 配置管理模块"""
    print_line("\n【测试 T02】配置管理")
    print_line("-" * 40)

    try:
        from by19code.config.settings import AppConfig, LLMProviderConfig

        # 测试配置模型创建
        try:
            test_provider = LLMProviderConfig(
                name="test",
                display_name="Test Provider",
                provider_type="anthropic",
                api_key="sk-test-key",
                base_url="https://api.test.com",
                model="test-model",
                max_tokens=4096,
                cost_per_1k_input=1.0,
                cost_per_1k_output=2.0,
            )
            log_pass("LLMProviderConfig 创建", "Pydantic 模型正常")
        except Exception as e:
            log_fail("LLMProviderConfig 创建", f"{type(e).__name__}: {e}")

        # 测试 AppConfig 创建
        try:
            test_config = AppConfig(
                version="0.1.0",
                llm_providers=[test_provider],
                active_provider="test",
            )
            log_pass("AppConfig 创建", "配置模型正常")
        except Exception as e:
            log_fail("AppConfig 创建", f"{type(e).__name__}: {e}")

        # 测试 get_provider 方法
        try:
            provider = test_config.get_provider("test")
            if provider and provider.name == "test":
                log_pass("get_provider 方法", "查询成功")
            else:
                log_fail("get_provider 方法", "查询结果不正确")
        except Exception as e:
            log_fail("get_provider 方法", f"{type(e).__name__}: {e}")

    except ImportError as e:
        log_fail("配置模块导入", f"导入失败：{e}（请确认 T02 已完成）")
    except Exception as e:
        log_fail("配置管理测试", f"异常：{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# 测试 T04：LLM 适配层基类
# ─────────────────────────────────────────────────────────────

async def test_t04_llm_base() -> None:
    """测试 T04 LLM 适配层基类定义"""
    print_line("\n【测试 T04】LLM 适配层基类")
    print_line("-" * 40)

    try:
        from by19code.llm.base import (
            Message,
            ToolDefinition,
            TokenUsage,
            LLMResponse,
            StreamEvent,
            ToolCall,
            LLMProvider,
            LLMError,
            LLMAuthError,
            LLMRateLimitError,
            LLMTimeoutError,
            LLMResponseError,
        )

        # 测试 Message 数据模型
        try:
            msg = Message(role="user", content="测试消息")
            if msg.role == "user" and msg.content == "测试消息":
                log_pass("Message 模型", "创建和访问正常")
            else:
                log_fail("Message 模型", "字段值不正确")
        except Exception as e:
            log_fail("Message 模型", f"{type(e).__name__}: {e}")

        # 测试 TokenUsage 数据模型
        try:
            usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
            if usage.total_tokens == 150:
                log_pass("TokenUsage 模型", "total_tokens 计算正确")
            else:
                log_fail("TokenUsage 模型", f"total_tokens={usage.total_tokens}，预期 150")
        except Exception as e:
            log_fail("TokenUsage 模型", f"{type(e).__name__}: {e}")

        # 测试 ToolCall 数据模型
        try:
            tool_call = ToolCall(id="call_123", name="test_tool", arguments={"arg": "value"})
            log_pass("ToolCall 模型", "创建正常")
        except Exception as e:
            log_fail("ToolCall 模型", f"{type(e).__name__}: {e}")

        # 测试 LLMResponse 数据模型
        try:
            response = LLMResponse(
                content="测试回复",
                tool_calls=None,
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
                model="test-model",
                stop_reason="end_turn",
            )
            log_pass("LLMResponse 模型", "创建正常")
        except Exception as e:
            log_fail("LLMResponse 模型", f"{type(e).__name__}: {e}")

        # 测试 StreamEvent 数据模型
        try:
            event = StreamEvent(event_type="text_delta", data="测试文本")
            if event.event_type == "text_delta":
                log_pass("StreamEvent 模型", "创建正常")
            else:
                log_fail("StreamEvent 模型", "event_type 不正确")
        except Exception as e:
            log_fail("StreamEvent 模型", f"{type(e).__name__}: {e}")

        # 测试 ToolDefinition 数据模型
        try:
            tool_def = ToolDefinition(
                name="test_tool",
                description="测试工具",
                parameters={"type": "object", "properties": {}},
            )
            log_pass("ToolDefinition 模型", "创建正常")
        except Exception as e:
            log_fail("ToolDefinition 模型", f"{type(e).__name__}: {e}")

        # 测试异常类层次结构
        try:
            # 测试基类
            base_error = LLMError("测试错误", provider="test")
            log_pass("LLMError 异常", "基类创建正常")

            # 测试子类
            auth_error = LLMAuthError("认证失败", provider="test")
            rate_error = LLMRateLimitError("频率限制", provider="test", retry_after=60.0)
            timeout_error = LLMTimeoutError("超时", provider="test")
            response_error = LLMResponseError("响应错误", provider="test")

            log_pass("LLM 异常子类", "所有异常类创建正常")
        except Exception as e:
            log_fail("LLM 异常类", f"{type(e).__name__}: {e}")

        # 测试 LLMProvider 抽象基类
        try:
            from abc import ABC
            if issubclass(LLMProvider, ABC):
                log_pass("LLMProvider 基类", "抽象基类定义正常")
            else:
                log_fail("LLMProvider 基类", "不是 ABC 子类")
        except Exception as e:
            log_fail("LLMProvider 基类", f"{type(e).__name__}: {e}")

    except ImportError as e:
        log_fail("LLM 基类模块导入", f"导入失败：{e}（请确认 T04 已完成）")
    except Exception as e:
        log_fail("LLM 基类测试", f"异常：{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# 测试 T07：Provider 工厂与注册
# ─────────────────────────────────────────────────────────────

async def test_t07_factory() -> None:
    """测试 T07 Provider 工厂与注册机制"""
    print_line("\n【测试 T07】Provider 工厂")
    print_line("-" * 40)

    try:
        from by19code.llm.factory import LLMFactory, switch_provider
        from by19code.llm.claude_provider import ClaudeProvider
        from by19code.llm.openai_provider import OpenAICompatibleProvider

        # 测试 list_providers
        try:
            providers = LLMFactory.list_providers()
            if isinstance(providers, list) and len(providers) > 0:
                log_pass("list_providers", f"已注册 {len(providers)} 个 Provider: {', '.join(providers)}")
            else:
                log_fail("list_providers", "返回结果为空或格式不正确")
        except Exception as e:
            log_fail("list_providers", f"{type(e).__name__}: {e}")

        # 测试工厂创建 Provider
        config = create_test_config()
        claude_cfg = config.get_provider("claude")

        if claude_cfg:
            try:
                config.active_provider = "claude"
                provider = LLMFactory.create(config)
                if provider.provider_name == "claude":
                    log_pass("LLMFactory.create", f"成功创建 {provider.provider_name} Provider")
                else:
                    log_fail("LLMFactory.create", f"provider_name={provider.provider_name}，预期 claude")
            except Exception as e:
                log_fail("LLMFactory.create", f"{type(e).__name__}: {e}")

        # 测试 switch_provider
        deepseek_cfg = config.get_provider("deepseek")
        if deepseek_cfg:
            try:
                provider = switch_provider("deepseek", config)
                if provider.provider_name == "deepseek":
                    log_pass("switch_provider", f"成功切换到 {provider.provider_name}")
                else:
                    log_fail("switch_provider", f"provider_name={provider.provider_name}，预期 deepseek")
            except Exception as e:
                log_fail("switch_provider", f"{type(e).__name__}: {e}")

        # 测试未注册 Provider 抛出异常
        try:
            config.active_provider = "nonexistent_provider"
            try:
                LLMFactory.create(config)
                log_fail("未注册 Provider 异常", "应该抛出 ValueError 但未抛出")
            except (ValueError, KeyError) as expected:
                log_pass("未注册 Provider 异常", "正确抛出异常")
        except Exception as e:
            log_fail("未注册 Provider 异常测试", f"意外异常：{type(e).__name__}: {e}")

    except ImportError as e:
        log_fail("工厂模块导入", f"导入失败：{e}（请确认 T07 已完成）")
    except Exception as e:
        log_fail("工厂测试", f"异常：{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# 测试 1：Claude 流式回复
# ─────────────────────────────────────────────────────────────

async def test_claude_streaming() -> None:
    """测试 T05 Claude Provider 流式对话"""
    print_line("\n【测试 T05】Claude 流式回复")
    print_line("-" * 40)

    try:
        from by19code.llm.factory import LLMFactory
        from by19code.llm.base import Message

        config = create_test_config()
        claude_cfg = config.get_provider("claude")
        if claude_cfg is None:
            log_fail("Claude 配置检查", "未设置 BY19CODE_CLAUDE_API_KEY 环境变量")
            return

        log_pass("Claude API Key 检查", f"Key 以 {claude_cfg.api_key[:8]}... 开头")
        print(f"  [配置] 模型: {claude_cfg.model}")
        print(f"  [配置] Base URL: {claude_cfg.base_url}")
        print(f"  [配置] Provider 类型: {claude_cfg.provider_type}")

        config.active_provider = "claude"
        try:
            provider = LLMFactory.create(config)
        except ImportError as e:
            log_fail("Claude Provider 创建", f"SDK 未安装：{e}")
            return

        log_pass("Claude Provider 创建", f"provider_name={provider.provider_name}")

        messages = [
            Message(role="system", content="你是一个简洁的助手，回复尽量简短。"),
            Message(role="user", content="请用一句话介绍你自己。"),
        ]

        collected_text = ""
        event_types_seen: set[str] = set()
        usage_event = None

        print("  Claude 回复：", end="", flush=True)
        try:
            async for event in provider.stream_chat(
                messages=messages,
                tools=None,
                model=claude_cfg.model,
                temperature=0.7,
                max_tokens=200,
            ):
                event_types_seen.add(event.event_type)
                if event.event_type == "text_delta":
                    text_chunk = event.data if isinstance(event.data, str) else str(event.data)
                    collected_text += text_chunk
                    print(text_chunk, end="", flush=True)
                elif event.event_type == "usage":
                    usage_event = event.data
                elif event.event_type == "error":
                    raise Exception(f"收到 error 事件：{event.data}")
            print()

            if len(collected_text.strip()) > 0:
                log_pass("Claude 流式文本输出", f"收到 {len(collected_text)} 个字符")
            else:
                log_fail("Claude 流式文本输出", "未收到任何文本")

            if "text_delta" in event_types_seen:
                log_pass("Claude 流式事件类型", f"事件类型：{event_types_seen}")
            else:
                log_fail("Claude 流式事件类型", f"缺少 text_delta，收到：{event_types_seen}")

            if usage_event is not None:
                log_pass("Claude Token 用量返回", f"tokens={usage_event.total_tokens}")
            else:
                print("  [提示] 未收到独立的 usage 事件（可能包含在 done 事件中）")

        except Exception as stream_error:
            print()
            log_fail("Claude 流式调用", f"{type(stream_error).__name__}: {stream_error}")
            import traceback
            print(f"  [详细错误]\n{traceback.format_exc()}")

    except ImportError as e:
        log_fail("模块导入", f"导入失败：{e}（请确认 T01-T07 已完成并安装依赖）")
    except Exception as e:
        log_fail("Claude 流式回复", f"异常：{type(e).__name__}: {e}")
        import traceback
        print(f"  [详细错误]\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────
# 测试 2：切换到 DeepSeek 后回复正常
# ─────────────────────────────────────────────────────────────

async def test_deepseek_switching() -> None:
    """测试切换到 DeepSeek Provider 后能正常对话"""
    print_line("\n【测试 T06】DeepSeek 切换与回复")
    print_line("-" * 40)

    try:
        from by19code.llm.factory import switch_provider
        from by19code.llm.base import Message

        config = create_test_config()

        # 获取 deepseek provider 配置
        deepseek_cfg = config.get_provider("deepseek")
        if deepseek_cfg is None:
            log_fail("DeepSeek 配置检查", "未设置 BY19CODE_DEEPSEEK_API_KEY 环境变量")
            print("  [跳过] 后续 DeepSeek 测试")
            return

        log_pass("DeepSeek API Key 检查", f"Key 以 {deepseek_cfg.api_key[:8]}... 开头")

        # 切换到 DeepSeek
        provider = switch_provider("deepseek", config)
        log_pass("DeepSeek Provider 创建", f"provider_name={provider.provider_name}")

        # 构建消息
        messages = [
            Message(role="system", content="你是一个简洁的助手，回复尽量简短。"),
            Message(role="user", content="请用一句话介绍你自己，并说明你是什么模型。"),
        ]

        # 流式调用
        collected_text = ""
        print("  DeepSeek 回复：", end="", flush=True)

        try:
            async for event in provider.stream_chat(
                messages=messages,
                tools=None,
                model=deepseek_cfg.model,
                temperature=0.7,
                max_tokens=200,
            ):
                if event.event_type == "text_delta":
                    text_chunk = event.data if isinstance(event.data, str) else str(event.data)
                    collected_text += text_chunk
                    print(text_chunk, end="", flush=True)
                elif event.event_type == "error":
                    error_msg = event.data if isinstance(event.data, str) else str(event.data)
                    log_fail("DeepSeek 流式回复", f"收到 error 事件：{error_msg}")
                    print()
                    return

            print()

            if len(collected_text.strip()) > 0:
                log_pass("DeepSeek 流式回复", f"收到 {len(collected_text)} 个字符")
            else:
                log_fail("DeepSeek 流式回复", "未收到任何文本")

        except Exception as stream_error:
            print()
            log_fail("DeepSeek 流式调用", f"流式调用异常：{type(stream_error).__name__}: {stream_error}")

    except ImportError as e:
        log_fail("模块导入", f"导入失败：{e}")
    except Exception as e:
        log_fail("DeepSeek 流式回复", f"异常：{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# 测试 3：SQLite 中有 token_usage 记录
# ─────────────────────────────────────────────────────────────

async def test_sqlite_token_records() -> None:
    """测试数据库中是否写入了 token_usage 记录"""
    print_line("\n【测试 T03】SQLite token_usage 记录")
    print_line("-" * 40)

    try:
        from by19code.llm.factory import LLMFactory
        from by19code.llm.base import Message
        from by19code.db.database import init_db, get_db
        from by19code.db.models import add_token_usage

        db_path = get_db_path()

        try:
            await init_db(str(db_path))
            log_pass("数据库初始化", f"路径：{db_path}")
        except Exception as db_init_error:
            log_fail("数据库初始化", f"初始化失败：{type(db_init_error).__name__}: {db_init_error}")
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM token_usage")
            count_before = cursor.fetchone()[0]
            conn.close()
            print(f"  测试前 token_usage 记录数：{count_before}")
        except Exception as count_error:
            log_fail("读取 token_usage 记录数", f"查询失败：{type(count_error).__name__}: {count_error}")
            return

        config = create_test_config()
        claude_cfg = config.get_provider("claude")
        if claude_cfg is None:
            log_fail("Claude 配置（数据库测试）", "未设置 BY19CODE_CLAUDE_API_KEY 环境变量")
            return

        print(f"  [配置] 模型: {claude_cfg.model}")
        print(f"  [配置] Base URL: {claude_cfg.base_url}")

        config.active_provider = "claude"
        try:
            provider = LLMFactory.create(config)
        except ImportError as e:
            if "anthropic" in str(e).lower():
                log_fail("Claude Provider 创建（数据库测试）", "anthropic SDK 未安装，请运行: pip install anthropic")
                return
            raise

        messages = [
            Message(role="system", content="回复OK即可。"),
            Message(role="user", content="测试"),
        ]

        try:
            response = await provider.chat(
                messages=messages,
                tools=None,
                model=claude_cfg.model,
                temperature=0,
                max_tokens=50,
            )

            print(f"  LLM 回复：{response.content[:50]}...")
            print(f"  Token 用量：prompt={response.usage.prompt_tokens}, "
                  f"completion={response.usage.completion_tokens}, "
                  f"total={response.usage.total_tokens}")

            db = await get_db()
            await add_token_usage(
                conn=db,
                provider_name=provider.provider_name,
                model_name=claude_cfg.model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                cost_usd=response.usage.estimated_cost,
            )

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM token_usage")
            count_after = cursor.fetchone()[0]
            cursor = conn.execute(
                "SELECT provider_name, model_name, input_tokens, output_tokens, total_tokens, cost_usd "
                "FROM token_usage ORDER BY id DESC LIMIT 1"
            )
            latest = cursor.fetchone()
            conn.close()

            if count_after > count_before:
                log_pass("token_usage 记录写入", f"新增 {count_after - count_before} 条，总计 {count_after} 条")
            else:
                log_fail("token_usage 记录写入", f"记录数未增加（前={count_before}，后={count_after}）")

            if latest:
                print(f"  最新记录：provider={latest[0]}, model={latest[1]}, "
                      f"input={latest[2]}, output={latest[3]}, total={latest[4]}, cost=${latest[5]:.6f}")
                log_pass("token_usage 记录内容", "字段完整")
            else:
                log_fail("token_usage 记录内容", "未能读取最新记录")

        except Exception as chat_error:
            log_fail("LLM 调用或数据库写入", f"{type(chat_error).__name__}: {chat_error}")

    except ImportError as e:
        log_fail("模块导入", f"导入失败：{e}（请确认 T03 数据库模块已完成）")
    except Exception as e:
        log_fail("SQLite token_usage 记录", f"异常：{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# 测试 4：费用计算正确
# ─────────────────────────────────────────────────────────────

async def test_cost_calculation() -> None:
    """测试 calculate_cost 费用计算逻辑"""
    print_line("\n【测试 T05/T06】费用计算")
    print_line("-" * 40)

    try:
        from by19code.llm.factory import LLMFactory
        from by19code.llm.base import TokenUsage

        config = create_test_config()

        # ── 测试 Claude 费用计算 ──
        claude_cfg = config.get_provider("claude")
        if claude_cfg:
            config.active_provider = "claude"
            try:
                claude_provider = LLMFactory.create(config)

                # 构造已知的 token 用量
                test_usage = TokenUsage(
                    prompt_tokens=1000,
                    completion_tokens=500,
                    total_tokens=1500,
                    estimated_cost=0.0,
                )

                model_name = "claude-3-7-sonnet-20250219"  # Claude Sonnet 3.7
                cost = claude_provider.calculate_cost(test_usage, model_name)

                # Claude 3.5 Sonnet: input $3/MTok, output $15/MTok
                # 预期：(1000 * 3 + 500 * 15) / 1_000_000 = 0.0105
                expected_cost = (1000 * 3 + 500 * 15) / 1_000_000

                print(f"  Claude 费用计算：usage(prompt=1000, completion=500)")
                print(f"  计算结果：${cost:.6f}")
                print(f"  预期结果：${expected_cost:.6f}")

                # 允许浮点误差
                if abs(cost - expected_cost) < 0.0001:
                    log_pass("Claude 费用计算", f"${cost:.6f}（预期 ${expected_cost:.6f}）")
                else:
                    log_fail("Claude 费用计算",
                             f"${cost:.6f} ≠ 预期 ${expected_cost:.6f}（差异 ${abs(cost - expected_cost):.6f}）")
            except ImportError as e:
                if "anthropic" in str(e).lower():
                    print("  [跳过] Claude 费用测试（anthropic SDK 未安装）")
                    log_fail("Claude 费用计算", "anthropic SDK 未安装")
                else:
                    raise e
            except Exception as claude_cost_error:
                log_fail("Claude 费用计算", f"异常：{type(claude_cost_error).__name__}: {claude_cost_error}")
        else:
            print("  [跳过] Claude 费用测试（未设置 BY19CODE_CLAUDE_API_KEY）")

        # ── 测试 DeepSeek 费用计算 ──
        deepseek_cfg = config.get_provider("deepseek")
        if deepseek_cfg:
            try:
                config.active_provider = "deepseek"
                deepseek_provider = LLMFactory.create(config)

                test_usage = TokenUsage(
                    prompt_tokens=10000,
                    completion_tokens=5000,
                    total_tokens=15000,
                    estimated_cost=0.0,
                )

                model_name = "deepseek-chat"
                cost = deepseek_provider.calculate_cost(test_usage, model_name)

                # DeepSeek: input $0.14/MTok, output $0.28/MTok
                # 预期：(10000 * 0.14 + 5000 * 0.28) / 1_000_000 = 0.0028
                expected_cost = (10000 * 0.14 + 5000 * 0.28) / 1_000_000

                print(f"  DeepSeek 费用计算：usage(prompt=10000, completion=5000)")
                print(f"  计算结果：${cost:.6f}")
                print(f"  预期结果：${expected_cost:.6f}")

                if abs(cost - expected_cost) < 0.0001:
                    log_pass("DeepSeek 费用计算", f"${cost:.6f}（预期 ${expected_cost:.6f}）")
                else:
                    log_fail("DeepSeek 费用计算",
                             f"${cost:.6f} ≠ 预期 ${expected_cost:.6f}（差异 ${abs(cost - expected_cost):.6f}）")
            except Exception as deepseek_cost_error:
                log_fail("DeepSeek 费用计算", f"异常：{type(deepseek_cost_error).__name__}: {deepseek_cost_error}")
        else:
            print("  [跳过] DeepSeek 费用测试（未设置 BY19CODE_DEEPSEEK_API_KEY）")

    except ImportError as e:
        log_fail("模块导入", f"导入失败：{e}")
    except Exception as e:
        log_fail("费用计算", f"异常：{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────

async def main() -> None:
    """执行全部验收测试"""
    print_line("=" * 60)
    print_line("  BY19Code 验收节点 A：能说话")
    print_line("  测试范围：T01-T07（脚手架 → LLM 适配层）")
    print_line(f"  执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_line("=" * 60)

    # 检查环境变量
    claude_key = os.environ.get("BY19CODE_CLAUDE_API_KEY", "")
    claude_base_url = os.environ.get("BY19CODE_CLAUDE_BASE_URL", "https://hone.vvvv.ee")
    deepseek_key = os.environ.get("BY19CODE_DEEPSEEK_API_KEY", "")
    deepseek_base_url = os.environ.get("BY19CODE_DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not claude_key and not deepseek_key:
        print_line()
        print_line("[警告] 未设置任何 API Key 环境变量")
        print_line("  请设置以下环境变量之一：")
        print_line("    - BY19CODE_CLAUDE_API_KEY")
        print_line("    - BY19CODE_DEEPSEEK_API_KEY")
        print_line()
        print_line("  Windows 设置方式：")
        print_line("    set BY19CODE_CLAUDE_API_KEY=sk-ant-...")
        print_line("    set BY19CODE_DEEPSEEK_API_KEY=sk-...")
        print_line()
        print_line("  可选：设置自定义 Base URL")
        print_line("    set BY19CODE_CLAUDE_BASE_URL=https://your-proxy.com")
        print_line("    set BY19CODE_DEEPSEEK_BASE_URL=https://api.deepseek.com")
        return

    if claude_key:
        print_line(f"\n[配置] Claude API Key: {claude_key[:8]}...")
        if claude_base_url:
            print_line(f"[配置] Claude Base URL: {claude_base_url}")
    if deepseek_key:
        print_line(f"[配置] DeepSeek API Key: {deepseek_key[:8]}...")
        if deepseek_base_url:
            print_line(f"[配置] DeepSeek Base URL: {deepseek_base_url}")

    # T01：项目脚手架
    try:
        await test_t01_scaffold()
    except Exception as e:
        log_fail("T01 执行", f"{type(e).__name__}: {e}")

    # T02：配置管理
    try:
        await test_t02_config()
    except Exception as e:
        log_fail("T02 执行", f"{type(e).__name__}: {e}")

    # T03：数据库初始化（在 T04 之前测试，因为 T03 是基础设施）
    try:
        await test_sqlite_token_records()
    except Exception as e:
        log_fail("T03 执行", f"{type(e).__name__}: {e}")

    # T04：LLM 适配层基类
    try:
        await test_t04_llm_base()
    except Exception as e:
        log_fail("T04 执行", f"{type(e).__name__}: {e}")

    # T05：Claude 流式回复
    try:
        await test_claude_streaming()
    except Exception as e:
        log_fail("T05 执行", f"{type(e).__name__}: {e}")

    # T06：切换到 DeepSeek
    try:
        await test_deepseek_switching()
    except Exception as e:
        log_fail("T06 执行", f"{type(e).__name__}: {e}")

    # T07：Provider 工厂
    try:
        await test_t07_factory()
    except Exception as e:
        log_fail("T07 执行", f"{type(e).__name__}: {e}")

    # 费用计算（T05/T06 的一部分）
    try:
        await test_cost_calculation()
    except Exception as e:
        log_fail("费用计算执行", f"{type(e).__name__}: {e}")

    # 输出汇总
    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
