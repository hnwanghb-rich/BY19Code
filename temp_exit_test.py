
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    from by19code.config.settings import load_config
    from by19code.db.database import init_db
    from by19code.cli.app import CLIApp

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config(project_dir=Path.cwd())
    await init_db(config.database.path)

    app = CLIApp(config, Path.cwd())

    # 模拟用户输入 /exit
    print("\n模拟用户输入: /exit")
    await app._handle_command("/exit")

if __name__ == "__main__":
    asyncio.run(main())
