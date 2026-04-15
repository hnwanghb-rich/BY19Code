"""调试流式输出问题"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from by19code.config.settings import load_config
from by19code.core.engine import ChatEngine
from by19code.db.database import init_db


async def test_stream():
    """测试流式输出"""
    # Windows 事件循环策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 加载配置
    config = load_config(project_dir=Path.cwd())
    print(f"配置加载完成: {config.active_provider}")

    # 初始化数据库
    await init_db(config.database.path)
    print(f"数据库初始化完成")

    # 创建引擎
    engine = ChatEngine(config, Path.cwd())
    print(f"引擎初始化完成")

    # 测试对话
    print("\n" + "=" * 60)
    print("测试 1: 简单对话")
    print("=" * 60)

    async for event in engine.chat("你好"):
        print(f"[事件] {event.event_type}: {str(event.data)[:50]}")

    print("\n" + "=" * 60)
    print("测试 2: 读取文件")
    print("=" * 60)

    async for event in engine.chat("读取 hello.py 文件"):
        print(f"[事件] {event.event_type}: {str(event.data)[:50]}")

    print("\n" + "=" * 60)
    print("测试 3: 修改文件")
    print("=" * 60)

    async for event in engine.chat("把 hello.py 中的 hello world 改成 hello test"):
        print(f"[事件] {event.event_type}: {str(event.data)[:50]}")

    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(test_stream())
