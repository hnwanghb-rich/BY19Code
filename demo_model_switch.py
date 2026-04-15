"""演示模型切换功能

这个脚本演示如何：
1. 列出所有可用模型
2. 切换模型
3. 使用不同模型进行对话
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    from by19code.config.settings import load_config
    from by19code.db.database import init_db, close_db
    from by19code.core.engine import ChatEngine
    from by19code.cli.renderer import Renderer

    print("=" * 60)
    print("BY19Code 模型切换功能演示")
    print("=" * 60)

    # 初始化
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config(project_dir=Path.cwd())
    await init_db(config.database.path)
    engine = ChatEngine(config, Path.cwd())
    renderer = Renderer()

    print(f"\n当前使用模型: {config.active_provider}")

    # 演示 1: 列出所有模型
    print("\n" + "=" * 60)
    print("1. 列出所有可用模型")
    print("=" * 60)

    renderer.print_info("\n[可用模型]")
    for provider in config.llm_providers:
        marker = "*" if provider.name == config.active_provider else " "
        has_key = provider.api_key and provider.api_key != f"${{BY19CODE_{provider.name.upper()}_API_KEY}}"
        key_status = "[OK]" if has_key else "[NO]"

        print(f"{marker} {provider.name} - {provider.display_name} {key_status}")
        print(f"    模型: {provider.model}")
        print(f"    费用: {provider.cost_per_1k_input:.2f}/{provider.cost_per_1k_output:.2f} 元/1K tokens")

    # 演示 2: 切换模型（如果有配置的话）
    available_models = [p.name for p in config.llm_providers if p.api_key and p.api_key != f"${{BY19CODE_{p.name.upper()}_API_KEY}}"]

    if len(available_models) > 1:
        print("\n" + "=" * 60)
        print("2. 切换模型演示")
        print("=" * 60)

        # 切换到第二个可用模型
        target_model = available_models[1] if available_models[0] == config.active_provider else available_models[0]
        print(f"\n切换到: {target_model}")

        result = await engine.switch_model(target_model)
        print(result)

        # 验证切换
        print(f"当前模型: {engine.provider.provider_name}")

        # 切换回原模型
        print(f"\n切换回: {config.active_provider}")
        result = await engine.switch_model(config.active_provider)
        print(result)
    else:
        print("\n[提示] 只有一个模型配置了 API Key，无法演示切换功能")
        print("请在 .env 文件中配置更多模型的 API Key")

    # 演示 3: 使用说明
    print("\n" + "=" * 60)
    print("3. 使用说明")
    print("=" * 60)
    print("""
在 BY19Code CLI 中使用以下命令：

  /model              - 列出所有可用模型
  /model <名称>       - 切换到指定模型
  /model kimi         - 切换到 Kimi 模型
  /model deepseek     - 切换到 DeepSeek 模型

配置 API Key：

  1. 创建 .env 文件
  2. 添加环境变量：
     BY19CODE_KIMI_API_KEY=sk-xxxxx
     BY19CODE_DOUBAO_API_KEY=xxxxx
     BY19CODE_GLM_API_KEY=xxxxx

详细说明请查看：
  - MODEL_CONFIG.md  - 配置说明
  - MODEL_USAGE.md   - 使用说明
""")

    print("=" * 60)
    print("演示完成")
    print("=" * 60)

    # 清理
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
