"""测试 Git 操作模块【T14】"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from by19code.git_ops import (
    git_status,
    git_diff,
    git_log,
    git_commit,
    git_create_branch,
    GitOperationError,
    GitNotFoundError,
    GitRepositoryError,
)

def test_git_operations():
    """测试 Git 操作"""
    project_root = Path.cwd()

    print("=" * 60)
    print("测试 Git 操作模块")
    print("=" * 60)

    # 测试 1: git_status
    print("\n[测试 1] git_status")
    print("-" * 60)
    try:
        result = git_status(project_root)
        print(result)
        print("[成功] git_status 测试通过")
    except Exception as e:
        print(f"[失败] {e}")

    # 测试 2: git_diff
    print("\n[测试 2] git_diff")
    print("-" * 60)
    try:
        result = git_diff(project_root)
        print(result[:500] if len(result) > 500 else result)  # 只显示前500字符
        print("[成功] git_diff 测试通过")
    except Exception as e:
        print(f"[失败] {e}")

    # 测试 3: git_log
    print("\n[测试 3] git_log")
    print("-" * 60)
    try:
        result = git_log(5, project_root)
        print(result)
        print("[成功] git_log 测试通过")
    except Exception as e:
        print(f"[失败] {e}")

    # 测试 4: git_commit (如果有更改)
    print("\n[测试 4] git_commit")
    print("-" * 60)
    try:
        result = git_commit("test: T14 Git 操作模块测试", project_root)
        print(result)
        print("[成功] git_commit 测试通过")
    except Exception as e:
        print(f"[失败] {e}")

    # 测试 5: 错误处理 - 非 Git 仓库
    print("\n[测试 5] 错误处理 - 非 Git 仓库")
    print("-" * 60)
    try:
        result = git_status("C:\\Windows\\Temp")
        print(f"[失败] 应该抛出异常但没有")
    except GitRepositoryError as e:
        print(f"[成功] 正确捕获异常: {e}")
    except Exception as e:
        print(f"[失败] 异常类型错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_git_operations()
