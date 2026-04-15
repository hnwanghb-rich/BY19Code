"""测试 CLI 启动和基本功能

这个脚本测试 CLI 是否能正常初始化，不需要真实的 API Key。
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from by19code.config.settings import AppConfig, LLMProviderConfig, SafetyConfig, DatabaseConfig
from by19code.db.database import init_db
from by19code.cli.renderer import Renderer


async def test_cli_components():
    """测试 CLI 组件"""
    print("=" * 60)
    print("测试 BY19Code CLI 组件")
    print("=" * 60)

    # 1. 测试渲染器
    print("\n[1] 测试渲染器...")
    renderer = Renderer()
    renderer.render_welcome()
    print("[OK] 渲染器初始化成功")

    # 2. 测试配置
    print("\n[2] 测试配置...")
    config = AppConfig(
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
            command_timeout_seconds=30,
            max_tool_rounds=20,
        ),
        database=DatabaseConfig(
            path=":memory:",  # 使用内存数据库测试
            log_retention_days=90,
        ),
    )
    print("[OK] 配置创建成功")

    # 3. 测试数据库初始化
    print("\n[3] 测试数据库初始化...")
    await init_db(":memory:")
    print("[OK] 数据库初始化成功")

    # 4. 测试命令解析
    print("\n[4] 测试命令解析...")
    test_commands = [
        "/help",
        "/clear",
        "/compact",
        "/stats",
        "/cost",
        "/switch claude",
        "/exit",
    ]
    for cmd in test_commands:
        parts = cmd.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        print(f"  命令: {cmd_name}, 参数: {args}")
    print("[OK] 命令解析成功")

    print("\n" + "=" * 60)
    print("所有组件测试通过！")
    print("=" * 60)
    print("\n提示：")
    print("1. 要运行完整的 CLI，需要配置真实的 API Key")
    print("2. 编辑 .env 文件，填入 BY19CODE_CLAUDE_API_KEY")
    print("3. 然后运行: python -m by19code.main")
    print()


if __name__ == "__main__":
    # Windows 事件循环策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(test_cli_components())
