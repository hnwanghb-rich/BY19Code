"""测试 /exit 命令"""
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

    # 测试 /exit 命令
    print("=" * 60)
    print("测试 /exit 命令")
    print("=" * 60)

    try:
        await app._handle_command("/exit")
        print("[错误] /exit 命令没有触发退出")
    except EOFError:
        print("[成功] /exit 命令正确触发了 EOFError")

    # 测试 /quit 命令
    print("\n" + "=" * 60)
    print("测试 /quit 命令")
    print("=" * 60)

    try:
        await app._handle_command("/quit")
        print("[错误] /quit 命令没有触发退出")
    except EOFError:
        print("[成功] /quit 命令正确触发了 EOFError")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

    # 清理
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
