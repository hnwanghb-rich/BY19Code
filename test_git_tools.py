"""测试通过工具系统调用 Git 操作"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def test_git_tools():
    """测试 Git 工具集成"""
    from by19code.core.tools import execute_tool
    from by19code.config.settings import SafetyConfig

    project_root = str(Path.cwd())
    config = SafetyConfig()

    print("=" * 60)
    print("测试 Git 工具集成")
    print("=" * 60)

    # 测试 1: git_status
    print("\n[测试 1] git_status 工具")
    print("-" * 60)
    result = await execute_tool("git_status", {}, project_root, config)
    print(result[:300])
    print("...")

    # 测试 2: git_diff
    print("\n[测试 2] git_diff 工具")
    print("-" * 60)
    result = await execute_tool("git_diff", {}, project_root, config)
    print(result[:300])
    print("...")

    # 测试 3: git_log
    print("\n[测试 3] git_log 工具")
    print("-" * 60)
    result = await execute_tool("git_log", {"count": 3}, project_root, config)
    print(result)

    # 测试 4: git_commit (如果有更改)
    print("\n[测试 4] git_commit 工具")
    print("-" * 60)
    result = await execute_tool(
        "git_commit",
        {"message": "test: 测试 Git 工具集成"},
        project_root,
        config
    )
    print(result)

    # 测试 5: git_create_branch (测试错误处理)
    print("\n[测试 5] git_create_branch 工具 (测试已存在分支)")
    print("-" * 60)
    result = await execute_tool(
        "git_create_branch",
        {"branch_name": "master"},
        project_root,
        config
    )
    print(result)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(test_git_tools())
