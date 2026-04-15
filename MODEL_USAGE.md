# 模型切换功能使用说明

## 功能概述

BY19Code 现在支持 5 个 LLM 提供商：
- **Claude** (Anthropic)
- **DeepSeek**
- **Kimi** (Moonshot AI)
- **豆包** (ByteDance)
- **智谱 GLM** (Zhipu AI)

## 快速开始

### 1. 查看所有可用模型

在 BY19Code CLI 中输入：

```
/model
```

输出示例：
```
[可用模型]
  claude - Claude (Anthropic) [OK]
    模型: claude-sonnet-4-20250514 | 费用: 3.00/15.00 元/1K tokens
* deepseek - DeepSeek [OK]
    模型: deepseek-chat | 费用: 0.14/0.28 元/1K tokens
  kimi - Kimi (Moonshot AI) [NO]
    模型: moonshot-v1-8k | 费用: 0.12/0.12 元/1K tokens
  doubao - 豆包 (ByteDance) [NO]
    模型: ep-20241227105917-xxxxxx | 费用: 0.00/0.00 元/1K tokens
  glm - 智谱 GLM (Zhipu AI) [NO]
    模型: glm-4-plus | 费用: 0.05/0.05 元/1K tokens
```

**说明：**
- `*` 表示当前正在使用的模型
- `[OK]` 表示已配置 API Key
- `[NO]` 表示未配置 API Key

### 2. 切换模型

```
/model kimi
```

或使用旧命令：

```
/switch kimi
```

成功后会显示：
```
[成功] 已切换到 kimi
```

## 配置 API Key

### 方法 1: 环境变量（推荐）

在项目根目录创建 `.env` 文件：

```bash
# Claude
BY19CODE_CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxx

# DeepSeek
BY19CODE_DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

# Kimi
BY19CODE_KIMI_API_KEY=sk-xxxxxxxxxxxxx

# 豆包
BY19CODE_DOUBAO_API_KEY=xxxxxxxxxxxxx

# 智谱 GLM
BY19CODE_GLM_API_KEY=xxxxxxxxxxxxx
```

### 方法 2: 配置文件

编辑 `config.json`，在对应的 provider 中添加 `api_key` 字段：

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
- 网址：https://console.anthropic.com/
- 费用：输入 $3/百万 tokens，输出 $15/百万 tokens

### DeepSeek
- 网址：https://platform.deepseek.com/
- 费用：输入 ¥0.14/百万 tokens，输出 ¥0.28/百万 tokens

### Kimi (Moonshot AI)
- 网址：https://platform.moonshot.cn/
- 费用：输入 ¥0.12/百万 tokens，输出 ¥0.12/百万 tokens

### 豆包 (ByteDance)
- 网址：https://console.volcengine.com/ark
- 注意：需要创建推理接入点，获取 endpoint ID
- 在 `config.json` 中修改 `model` 字段为你的 endpoint ID

### 智谱 GLM (Zhipu AI)
- 网址：https://open.bigmodel.cn/
- 费用：输入 ¥0.05/百万 tokens，输出 ¥0.05/百万 tokens

## 常见问题

### Q: 切换模型后提示 API Key 无效？
A: 确保已正确配置该模型的 API Key，使用 `/model` 命令查看配置状态。

### Q: 豆包模型如何配置？
A: 豆包使用推理接入点（endpoint），需要：
1. 在火山引擎控制台创建推理接入点
2. 获取 endpoint ID（格式：`ep-xxxxxx`）
3. 在 `config.json` 中修改 `model` 字段为你的 endpoint ID
4. 配置 API Key

### Q: 如何添加其他 OpenAI 兼容的模型？
A: 在 `config.json` 中添加新的 provider 配置，然后在 `by19code/llm/factory.py` 中注册：

```python
LLMFactory.register("your_model", OpenAICompatibleProvider)
```

### Q: 切换模型后对话历史会保留吗？
A: 会保留。切换模型只是更换了 LLM 提供商，对话历史不会丢失。

### Q: 不同模型的费用差异很大吗？
A: 是的，建议根据任务选择：
- **简单任务**：使用 DeepSeek、GLM（费用低）
- **复杂任务**：使用 Claude、Kimi（能力强）
- **测试开发**：使用 DeepSeek（性价比高）

## 完整命令列表

```
/help      - 显示帮助信息
/model     - 列出所有可用模型
/model <名称> - 切换到指定模型
/clear     - 清空对话历史
/compact   - 压缩上下文
/stats     - 查看上下文统计
/cost      - 查看费用汇总
/exit      - 退出程序
```

## 示例会话

```
> /model
[可用模型]
* deepseek - DeepSeek [OK]
  kimi - Kimi (Moonshot AI) [OK]
  ...

> /model kimi
[成功] 已切换到 kimi

> 你好
你好！我是 Kimi，很高兴为你服务...

> /model deepseek
[成功] 已切换到 deepseek

> 继续之前的对话
好的，我们继续...
```

## 技术细节

- 所有 OpenAI 兼容模型使用统一的 `OpenAICompatibleProvider`
- Claude 使用专用的 `ClaudeProvider`
- 模型切换不会中断当前会话
- 支持运行时动态切换，无需重启程序
