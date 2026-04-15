# 模型配置说明

BY19Code 支持多个 LLM 提供商，包括 Claude、DeepSeek、Kimi、豆包和智谱 GLM。

## 支持的模型

| 模型名称 | 提供商 | 模型标识 | API 端点 |
|---------|--------|---------|---------|
| claude | Anthropic | claude-sonnet-4-20250514 | https://api.anthropic.com |
| deepseek | DeepSeek | deepseek-chat | https://api.deepseek.com |
| kimi | Moonshot AI | moonshot-v1-8k | https://api.moonshot.cn/v1 |
| doubao | ByteDance | ep-20241227105917-xxxxxx | https://ark.cn-beijing.volces.com/api/v3 |
| glm | Zhipu AI | glm-4-plus | https://open.bigmodel.cn/api/paas/v4 |

## 配置 API Key

### 方法 1: 环境变量（推荐）

在项目根目录创建 `.env` 文件，添加以下内容：

```bash
# Claude (Anthropic)
BY19CODE_CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxx

# DeepSeek
BY19CODE_DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

# Kimi (Moonshot AI)
BY19CODE_KIMI_API_KEY=sk-xxxxxxxxxxxxx

# 豆包 (ByteDance)
BY19CODE_DOUBAO_API_KEY=xxxxxxxxxxxxx

# 智谱 GLM (Zhipu AI)
BY19CODE_GLM_API_KEY=xxxxxxxxxxxxx
```

### 方法 2: 配置文件

编辑 `config.json` 文件，在对应的 provider 中添加 `api_key` 字段：

```json
{
  "llm_providers": [
    {
      "name": "kimi",
      "api_key": "sk-xxxxxxxxxxxxx",
      ...
    }
  ]
}
```

## 获取 API Key

### Claude (Anthropic)
1. 访问 https://console.anthropic.com/
2. 注册账号并登录
3. 进入 API Keys 页面创建新的 API Key

### DeepSeek
1. 访问 https://platform.deepseek.com/
2. 注册账号并登录
3. 进入 API Keys 页面创建新的 API Key

### Kimi (Moonshot AI)
1. 访问 https://platform.moonshot.cn/
2. 注册账号并登录
3. 进入 API Keys 页面创建新的 API Key

### 豆包 (ByteDance)
1. 访问 https://console.volcengine.com/ark
2. 注册账号并登录
3. 创建推理接入点，获取 API Key 和 endpoint ID
4. 在 `config.json` 中修改 `model` 字段为你的 endpoint ID（格式：`ep-xxxxxx`）

### 智谱 GLM (Zhipu AI)
1. 访问 https://open.bigmodel.cn/
2. 注册账号并登录
3. 进入 API Keys 页面创建新的 API Key

## 使用模型

### 列出所有可用模型

```bash
/model
```

输出示例：
```
[可用模型]
★ deepseek - DeepSeek ✓
    模型: deepseek-chat | 费用: ¥0.14/¥0.28 per 1K tokens
  claude - Claude (Anthropic) ✗
    模型: claude-sonnet-4-20250514 | 费用: ¥3.00/¥15.00 per 1K tokens
  kimi - Kimi (Moonshot AI) ✓
    模型: moonshot-v1-8k | 费用: ¥0.12/¥0.12 per 1K tokens
```

- ★ 表示当前使用的模型
- ✓ 表示已配置 API Key
- ✗ 表示未配置 API Key

### 切换模型

```bash
/model kimi
```

或使用旧命令：

```bash
/switch kimi
```

## 自定义模型配置

你可以在 `config.json` 中添加更多模型配置：

```json
{
  "llm_providers": [
    {
      "name": "custom",
      "display_name": "自定义模型",
      "provider_type": "openai_compat",
      "base_url": "https://api.example.com/v1",
      "model": "custom-model-name",
      "max_tokens": 8192,
      "cost_per_1k_input": 0.0,
      "cost_per_1k_output": 0.0
    }
  ]
}
```

### 配置字段说明

- `name`: 模型标识符（用于命令行切换）
- `display_name`: 显示名称
- `provider_type`: 提供商类型（`anthropic` 或 `openai_compat`）
- `base_url`: API 端点地址
- `model`: 模型名称
- `max_tokens`: 最大 token 数
- `cost_per_1k_input`: 输入费用（每 1000 tokens，单位：元）
- `cost_per_1k_output`: 输出费用（每 1000 tokens，单位：元）

## 注意事项

1. **豆包模型配置**：豆包使用推理接入点（endpoint），需要在配置文件中将 `model` 字段修改为你的 endpoint ID
2. **API Key 安全**：不要将包含 API Key 的配置文件提交到 Git 仓库
3. **费用控制**：不同模型的费用差异较大，建议根据需求选择合适的模型
4. **网络访问**：部分 API 可能需要特殊网络环境才能访问

## 故障排查

### API Key 无效
- 检查 API Key 是否正确复制（注意前后空格）
- 确认 API Key 是否已激活
- 检查账户余额是否充足

### 连接超时
- 检查网络连接
- 确认 API 端点地址是否正确
- 部分 API 可能需要代理访问

### 模型切换失败
- 确认模型名称拼写正确
- 检查该模型的 API Key 是否已配置
- 查看日志文件 `by19code.log` 获取详细错误信息
