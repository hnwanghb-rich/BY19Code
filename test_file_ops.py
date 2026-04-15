"""测试文件操作是否会卡住"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    from by19code.config.settings import load_config
    from by19code.db.database import init_db, close_db
    from by19code.core.engine import ChatEngine

    print("初始化...")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config(project_dir=Path.cwd())
    await init_db(config.database.path)
    engine = ChatEngine(config, Path.cwd())
    print("初始化完成\n")

    # 测试 1: 创建文件
    print("=" * 60)
    print("测试 1: 创建文件")
    print("=" * 60)
    try:
        count = 0
        async for event in engine.chat("创建一个 test.txt 文件，内容是 hello"):
            if event.event_type == "text_delta":
                print(event.data, end="", flush=True)
            elif event.event_type == "tool_call_start":
                print(f"\n[工具] {event.data.name}")
            count += 1
            if count > 200:  # 防止无限循环
                print("\n[警告] 事件过多，停止")
                break
        print("\n测试 1 完成\n")
    except asyncio.TimeoutError:
        print("\n[错误] 测试 1 超时")
    except Exception as e:
        print(f"\n[错误] 测试 1 失败: {e}")

    # 测试 2: 读取文件
    print("=" * 60)
    print("测试 2: 读取文件")
    print("=" * 60)
    try:
        count = 0
        async for event in engine.chat("读取 test.txt 文件"):
            if event.event_type == "text_delta":
                print(event.data, end="", flush=True)
            elif event.event_type == "tool_call_start":
                print(f"\n[工具] {event.data.name}")
            count += 1
            if count > 200:
                print("\n[警告] 事件过多，停止")
                break
        print("\n测试 2 完成\n")
    except asyncio.TimeoutError:
        print("\n[错误] 测试 2 超时")
    except Exception as e:
        print(f"\n[错误] 测试 2 失败: {e}")

    # 测试 3: 修改文件
    print("=" * 60)
    print("测试 3: 修改文件")
    print("=" * 60)
    try:
        count = 0
        async for event in engine.chat("把 test.txt 中的 hello 改成 world"):
            if event.event_type == "text_delta":
                print(event.data, end="", flush=True)
            elif event.event_type == "tool_call_start":
                print(f"\n[工具] {event.data.name}")
            count += 1
            if count > 200:
                print("\n[警告] 事件过多，停止")
                break
        print("\n测试 3 完成\n")
    except asyncio.TimeoutError:
        print("\n[错误] 测试 3 超时")
    except Exception as e:
        print(f"\n[错误] 测试 3 失败: {e}")

    print("=" * 60)
    print("所有测试完成")
    print("=" * 60)

    # 清理
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
