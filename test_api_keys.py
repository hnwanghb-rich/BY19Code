"""测试所有模型的 API Key 是否正确加载"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from by19code.config.settings import load_config

def test_api_keys():
    """测试所有模型的 API Key 加载情况"""
    print("=" * 60)
    print("测试 API Key 加载情况")
    print("=" * 60)

    # 加载配置
    config = load_config(project_dir=Path.cwd())

    print(f"\n当前激活的 Provider: {config.active_provider}")
    print(f"\n共配置了 {len(config.llm_providers)} 个模型：\n")

    # 检查每个 Provider 的 API Key
    for idx, provider in enumerate(config.llm_providers, 1):
        has_key = provider.api_key and provider.api_key != f"${{BY19CODE_{provider.name.upper()}_API_KEY}}"
        key_preview = ""

        if has_key:
            # 显示 API Key 的前 10 个字符和后 4 个字符
            key = provider.api_key
            if len(key) > 14:
                key_preview = f"{key[:10]}...{key[-4:]}"
            else:
                key_preview = key[:6] + "..."
            status = "[OK] 已配置"
        else:
            key_preview = "未配置"
            status = "[NO] 缺失"

        print(f"{idx}. {provider.name:12} - {provider.display_name:20} {status}")
        print(f"   模型: {provider.model}")
        print(f"   API Key: {key_preview}")
        print()

if __name__ == "__main__":
    test_api_keys()
