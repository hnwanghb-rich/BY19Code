import httpx
import json

def test_claude_code_mimic():
    url = "https://hone.vvvv.ee/v1/messages"
    
    # 完美复刻 Claude Code 的请求头
    headers = {
        "x-api-key": "sk-2xKlk7nAoq5tEu0ckMgzzDXOsWWlfLRpx67bYwe4CGgZaCmW",  # 替换成你的真实 Key
        "anthropic-version": "2023-06-01",
        # 下面这行就是 Claude Code 畅通无阻的 VIP 通行证
        "anthropic-beta": "computer-use-2024-10-22, prompt-caching-2024-07-31", 
        "content-type": "application/json"
    }
    
    # 完美遵守原生 Anthropic 的 JSON 结构（system 在外层！）
    payload = {
        "model": "claude-3-5-sonnet-latest", # 或者尝试 claude-3-7-sonnet-20250219
        "max_tokens": 1024,
        "system": "你是一个简洁的助手，回复尽量简短。", # 注意：绝对不能放进 messages 里
        "messages": [
            {"role": "user", "content": "请用一句话介绍你自己。"}
        ],
        "stream": False
    }

    print("🚀 正在模拟 Claude Code 发送原生协议请求...")
    try:
        # 禁用重定向和代理干扰
        with httpx.Client(verify=False) as client: 
            response = client.post(url, headers=headers, json=payload, timeout=30.0)
            
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("✅ 成功！回复内容：")
            print(response.json()['content'][0]['text'])
        else:
            print("❌ 失败！中转站返回：")
            print(response.text)
    except Exception as e:
        print(f"网络异常: {e}")

if __name__ == "__main__":
    test_claude_code_mimic()