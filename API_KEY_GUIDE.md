# API Key 配置快速指南

## 方法 1: 使用 .env 文件（推荐）

### 步骤 1: 创建 .env 文件

在项目根目录创建 `.env` 文件（或复制 `.env.example` 并重命名）：

```bash
# Windows
copy .env.example .env

# 或者直接创建新文件
notepad .env
```

### 步骤 2: 填入 API Key

在 `.env` 文件中填入你的 API Key：

```bash
# Claude (Anthropic)
BY19CODE_CLAUDE_API_KEY=sk-ant-api03-xxxxxxxxxxxxx

# OpenAI
BY19CODE_OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# DeepSeek
BY19CODE_DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

# MiniMax
BY19CODE_MINIMAX_API_KEY=xxxxxxxxxxxxx

# Kimi (Moonshot AI)
BY19CODE_KIMI_API_KEY=sk-xxxxxxxxxxxxx

# 豆包 (ByteDance)
BY19CODE_DOUBAO_API_KEY=xxxxxxxxxxxxx

# 智谱 GLM (Zhipu AI)
BY19CODE_GLM_API_KEY=xxxxxxxxxxxxx.xxxxxxxxxxxxx
```

### 步骤 3: 验证配置

运行快速测试：

```bash
python quick_test.py
```

输出示例：
```
已配置的模型:
  claude     [OK] - Claude (Anthropic)
* deepseek   [OK] - DeepSeek
  kimi       [OK] - Kimi (Moonshot AI)
  doubao     [NO] - 豆包 (ByteDance)
  glm        [OK] - 智谱 GLM (Zhipu AI)
```

## 方法 2: 直接在配置文件中填写

编辑 `config.json`，在对应的 provider 中添加 `api_key` 字段：

```json
{
  "llm_providers": [
    {
      "name": "kimi",
      "display_name": "Kimi (Moonshot AI)",
      "provider_type": "openai_compat",
      "api_key": "sk-xxxxxxxxxxxxx",
      "base_url": "https://api.moonshot.cn/v1",
      "model": "moonshot-v1-8k",
      "max_tokens": 8192,
      "cost_per_1k_input": 0.12,
      "cost_per_1k_output": 0.12
    }
  ]
}
```

**注意：** 不推荐此方法，因为容易将 API Key 提交到 Git。

## 各模型 API Key 获取方式

### 1. Claude (Anthropic)

**官方渠道：**
- 网址：https://console.anthropic.com/
- 注册并创建 API Key
- 格式：`sk-ant-api03-xxxxxxxxxxxxx`

**中转站（如果官方无法访问）：**
- 可以使用第三方中转服务
- 在 `config.json` 中修改 `base_url` 为中转站地址

### 2. OpenAI

- 网址：https://platform.openai.com/
- 注册并创建 API Key
- 格式：`sk-xxxxxxxxxxxxx`
- 支持 GPT-4o、GPT-4、GPT-3.5 等模型
- 需要国际信用卡支付

### 3. DeepSeek

- 网址：https://platform.deepseek.com/
- 注册并创建 API Key
- 格式：`sk-xxxxxxxxxxxxx`
- 新用户通常有免费额度

### 4. MiniMax

- 网址：https://api.minimax.chat/
- 注册并创建 API Key
- 支持 abab6.5-chat 等模型
- 国内服务，响应速度快
- 新用户有免费额度

### 5. Kimi (Moonshot AI)

- 网址：https://platform.moonshot.cn/
- 注册并创建 API Key
- 格式：`sk-xxxxxxxxxxxxx`
- 支持长上下文（128K）

### 6. 豆包 (ByteDance)

**特殊配置步骤：**

1. 访问：https://console.volcengine.com/ark
2. 注册火山引擎账号
3. 创建推理接入点：
   - 选择模型（如：豆包-pro）
   - 创建接入点
   - 获取 endpoint ID（格式：`ep-20241227105917-xxxxxx`）
4. 获取 API Key
5. **重要：** 在 `config.json` 中修改 `model` 字段：
   ```json
   {
     "name": "doubao",
     "model": "ep-20241227105917-你的实际ID"
   }
   ```

### 7. 智谱 GLM (Zhipu AI)

- 网址：https://open.bigmodel.cn/
- 注册并创建 API Key
- 格式：`xxxxxxxxxxxxx.xxxxxxxxxxxxx`（包含点号）
- 支持多种模型（GLM-4、GLM-4-Plus 等）

## 费用对比

| 模型 | 输入费用 | 输出费用 | 特点 |
|------|---------|---------|------|
| Claude | ¥3.00/百万tokens | ¥15.00/百万tokens | 能力最强，适合复杂任务 |
| OpenAI GPT-4o | ¥2.50/百万tokens | ¥10.00/百万tokens | 国际主流，能力强 |
| DeepSeek | ¥0.14/百万tokens | ¥0.28/百万tokens | 性价比高，适合日常开发 |
| MiniMax | ¥0.015/百万tokens | ¥0.015/百万tokens | 极低价格，国内服务 |
| Kimi | ¥0.12/百万tokens | ¥0.12/百万tokens | 长上下文，适合文档处理 |
| 豆包 | 按实际计费 | 按实际计费 | 国内服务，响应快 |
| GLM | ¥0.05/百万tokens | ¥0.05/百万tokens | 便宜，适合测试 |

## 使用建议

### 开发测试阶段
推荐使用：**MiniMax** 或 **GLM**
- 费用极低（MiniMax最便宜）
- 性能够用
- 适合频繁调试

### 日常开发
推荐使用：**DeepSeek**
- 性价比高
- 性能稳定
- 适合日常编程任务

### 生产环境
推荐使用：**Claude** 或 **OpenAI GPT-4o**
- 能力强
- 稳定性好
- 适合复杂任务

### 文档处理
推荐使用：**Kimi**
- 支持 128K 上下文
- 适合长文档分析

## 常见问题

### Q: API Key 填写后还是显示 [NO]？

A: 检查以下几点：
1. API Key 格式是否正确（注意前后空格）
2. 环境变量名称是否正确（必须是 `BY19CODE_` 开头）
3. 重启程序使环境变量生效

### Q: 豆包模型无法使用？

A: 豆包需要额外配置：
1. 确保已创建推理接入点
2. 在 `config.json` 中修改 `model` 字段为实际的 endpoint ID
3. endpoint ID 格式：`ep-20241227105917-xxxxxx`

### Q: 如何测试 API Key 是否有效？

A: 运行测试脚本：
```bash
python quick_test.py
```

或在 CLI 中使用：
```bash
/model
```

### Q: 可以同时配置多个模型吗？

A: 可以！配置多个模型后可以随时切换：
```bash
/model kimi      # 切换到 Kimi
/model deepseek  # 切换到 DeepSeek
```

### Q: API Key 会被泄露吗？

A: 只要遵循以下规则就很安全：
1. 使用 `.env` 文件存储 API Key
2. 确保 `.env` 在 `.gitignore` 中
3. 不要将 API Key 写在 `config.json` 中并提交到 Git

## 安全建议

1. **不要提交 API Key 到 Git**
   - 将 `.env` 添加到 `.gitignore`
   - 使用 `.env.example` 作为模板

2. **定期轮换 API Key**
   - 定期更换 API Key
   - 删除不再使用的 API Key

3. **设置费用预警**
   - 在各平台设置费用上限
   - 定期检查使用情况

4. **使用环境变量**
   - 优先使用 `.env` 文件
   - 避免在代码中硬编码

## 下一步

配置完成后，可以：

1. 启动 CLI：
   ```bash
   python -m by19code.main
   ```

2. 查看可用模型：
   ```bash
   /model
   ```

3. 开始使用：
   ```bash
   > 你好
   > 帮我创建一个 Python 脚本
   ```

更多使用说明请查看：
- `MODEL_USAGE.md` - 详细使用指南
- `MODEL_CONFIG.md` - 配置详解
- `SUMMARY.md` - 功能总结
