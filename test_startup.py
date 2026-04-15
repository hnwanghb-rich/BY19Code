"""测试 BY19Code 启动流程

验证配置加载、数据库初始化、CLI 启动是否正常。
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from by19code.config.settings import load_config
from by19code.db.database import init_db


async def test_startup():
    """测试启动流程"""
    print("=" * 60)
    print("测试 BY19Code 启动流程")
    print("=" * 60)

    # 1. 测试配置加载
    print("\n[1] 测试配置加载...")
    try:
        config = load_config(project_dir=Path.cwd())
        print(f"[OK] 配置加载成功")
        print(f"  - Active Provider: {config.active_provider}")
        print(f"  - Providers: {[p.name for p in config.llm_providers]}")
        print(f"  - Database: {config.database.path}")
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return False

    # 2. 测试数据库初始化
    print("\n[2] 测试数据库初始化...")
    try:
        await init_db(config.database.path)
        print(f"[OK] 数据库初始化成功: {config.database.path}")
    except Exception as e:
        print(f"[ERROR] 数据库初始化失败: {e}")
        return False

    # 3. 检查 API Key
    print("\n[3] 检查 API Key...")
    has_key = False
    for provider in config.llm_providers:
        if provider.api_key and provider.api_key != "${BY19CODE_CLAUDE_API_KEY}":
            print(f"[OK] {provider.name} API Key 已配置")
            has_key = True
        else:
            print(f"[WARN] {provider.name} API Key 未配置")

    if not has_key:
        print("\n[WARN] 没有配置任何 API Key，无法进行实际对话测试")
        print("请编辑 .env 文件，填入 BY19CODE_CLAUDE_API_KEY")

    print("\n" + "=" * 60)
    print("启动流程测试完成！")
    print("=" * 60)

    if has_key:
        print("\n[OK] 所有检查通过，可以启动 CLI 进行测试")
        print("\n运行命令：")
        print("  python -m by19code.main")
    else:
        print("\n[WARN] 请先配置 API Key 再启动 CLI")

    return True


if __name__ == "__main__":
    # Windows 事件循环策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    success = asyncio.run(test_startup())
    sys.exit(0 if success else 1)
