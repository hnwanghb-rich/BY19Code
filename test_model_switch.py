"""测试模型列表和切换功能"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    from by19code.config.settings import load_config
    from by19code.db.database import init_db, close_db
    from by19code.cli.app import CLIApp

    print("初始化...")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config(project_dir=Path.cwd())
    await init_db(config.database.path)

    app = CLIApp(config, Path.cwd())
    print("初始化完成\n")

    # 测试 1: 列出所有模型
    print("=" * 60)
    print("测试 1: 列出所有模型")
    print("=" * 60)
    app._list_models()

    # 测试 2: 切换到 kimi
    print("\n" + "=" * 60)
    print("测试 2: 切换到 kimi")
    print("=" * 60)
    result = await app.engine.switch_model("kimi")
    print(result)

    # 测试 3: 再次列出模型（验证切换成功）
    print("\n" + "=" * 60)
    print("测试 3: 验证切换结果")
    print("=" * 60)
    app._list_models()

    # 测试 4: 切换到不存在的模型
    print("\n" + "=" * 60)
    print("测试 4: 切换到不存在的模型")
    print("=" * 60)
    result = await app.engine.switch_model("nonexistent")
    print(result)

    # 测试 5: 切换回 deepseek
    print("\n" + "=" * 60)
    print("测试 5: 切换回 deepseek")
    print("=" * 60)
    result = await app.engine.switch_model("deepseek")
    print(result)

    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)

    # 清理
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
