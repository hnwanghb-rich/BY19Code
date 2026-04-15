"""测试完整的退出流程"""
import subprocess
import sys
import time

print("=" * 60)
print("测试 /exit 命令完整退出流程")
print("=" * 60)

# 创建一个临时脚本来模拟用户输入
test_script = """
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
    print("\\n模拟用户输入: /exit")
    await app._handle_command("/exit")

if __name__ == "__main__":
    asyncio.run(main())
"""

# 写入临时脚本
with open("temp_exit_test.py", "w", encoding="utf-8") as f:
    f.write(test_script)

print("\n运行测试...")
print("-" * 60)

# 运行测试脚本
result = subprocess.run(
    [sys.executable, "temp_exit_test.py"],
    capture_output=True,
    text=True,
    timeout=10
)

print("标准输出:")
print(result.stdout)

if result.stderr:
    print("\n标准错误:")
    print(result.stderr)

print("-" * 60)
print(f"\n退出码: {result.returncode}")

if result.returncode == 0:
    print("[成功] 程序正常退出")
else:
    print(f"[失败] 程序异常退出，退出码: {result.returncode}")

# 清理临时文件
import os
try:
    os.remove("temp_exit_test.py")
    print("\n临时文件已清理")
except:
    pass

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
