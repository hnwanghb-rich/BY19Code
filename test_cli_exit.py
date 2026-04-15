"""测试实际 CLI 退出"""
import subprocess
import sys
import time

print("=" * 60)
print("测试实际 CLI 程序退出")
print("=" * 60)

print("\n启动 CLI 程序并发送 /exit 命令...")
print("-" * 60)

# 使用 subprocess 启动程序并发送命令
process = subprocess.Popen(
    [sys.executable, "-m", "by19code.main"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

# 等待程序启动
time.sleep(3)

# 发送 /exit 命令
print("发送命令: /exit")
try:
    process.stdin.write("/exit\n")
    process.stdin.flush()
except:
    pass

# 等待程序退出
try:
    stdout, stderr = process.communicate(timeout=5)

    print("\n程序输出:")
    print(stdout[-500:] if len(stdout) > 500 else stdout)  # 只显示最后500字符

    if stderr:
        print("\n错误输出:")
        print(stderr[-500:] if len(stderr) > 500 else stderr)

    print("-" * 60)
    print(f"\n退出码: {process.returncode}")

    if process.returncode == 0:
        print("[成功] 程序正常退出到系统命令行")
    else:
        print(f"[警告] 程序退出码为 {process.returncode}")

except subprocess.TimeoutExpired:
    print("\n[失败] 程序在 5 秒内未退出，强制终止...")
    process.kill()
    print("程序已被强制终止")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
