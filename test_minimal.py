"""最简单的测试"""
import asyncio
import sys

print("测试开始")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def simple_test():
    print("异步函数开始")
    await asyncio.sleep(0.1)
    print("异步函数结束")

asyncio.run(simple_test())

print("测试结束")
