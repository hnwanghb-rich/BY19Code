# 豆包和 GLM 配置问题解决方案

## 问题 1: API Key 未加载

### 原因
`.env` 文件中的环境变量名称大小写错误，且配置加载时没有自动加载 `.env` 文件。

### 解决方案

#### 1. 修复 .env 文件中的环境变量名称
**错误**：
```bash
BY19CODE_Doubao_API_KEY=xxxxx  # 大小写混合
```

**正确**：
```bash
BY19CODE_DOUBAO_API_KEY=xxxxx  # 全大写
```

#### 2. 在配置加载时自动加载 .env 文件
修改了 `by19code/config/settings.py`，在 `load_config()` 函数开始时添加：

```python
# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    if project_dir:
        env_file = Path(project_dir) / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            logger.debug("[配置] 已加载 .env 文件: %s", env_file)
except ImportError:
    logger.debug("[配置] python-dotenv 未安装，跳过 .env 文件加载")
```

### 验证
运行 `python quick_test.py`，所有模型应该显示 [OK]：

```
已配置的模型:
  claude     [OK] - Claude (Anthropic)
* deepseek   [OK] - DeepSeek
  kimi       [OK] - Kimi (Moonshot AI)
  doubao     [OK] - 豆包 (ByteDance)
  glm        [OK] - 智谱 GLM (Zhipu AI)
```

---

## 问题 2: 豆包 401 认证错误

### 错误信息
```
Error code: 401 - {'error': {'code': 'AuthenticationError', 
'message': 'the API key or AK/SK in the request is missing or invalid'}}
```

### 原因
豆包使用推理接入点（endpoint）模式，需要配置实际的 endpoint ID。

### 解决方案

#### 步骤 1: 获取 endpoint ID

1. 访问火山引擎控制台：https://console.volcengine.com/ark
2. 创建推理接入点（选择豆包模型）
3. 获取 endpoint ID，格式类似：`ep-20241227105917-abc123`

#### 步骤 2: 修改 config.json

编辑 `config.json`，找到 doubao 配置：

```json
{
  "name": "doubao",
  "display_name": "豆包 (ByteDance)",
  "provider_type": "openai_compat",
  "base_url": "https://ark.cn-beijing.volces.com/api/v3",
  "model": "ep-20241227105917-你的实际endpoint_ID",  // 修改这里
  "max_tokens": 8192,
  "cost_per_1k_input": 0.0,
  "cost_per_1k_output": 0.0
}
```

#### 步骤 3: 配置 API Key

在 `.env` 文件中：

```bash
BY19CODE_DOUBAO_API_KEY=你的豆包API_Key
```

---

## 问题 3: GLM 401 认证错误

### 错误信息
```
Error code: 401 - {'error': {'code': '1001', 
'message': 'Header中未收到Authorization参数，无法进行身份验证。'}}
```

### 原因
GLM 的 API Key 格式特殊，包含点号（.），需要确保完整复制。

### 解决方案

#### 步骤 1: 获取 API Key

1. 访问智谱 AI 开放平台：https://open.bigmodel.cn/
2. 创建 API Key
3. 完整复制 API Key（格式：`xxxxx.xxxxx`，包含点号）

#### 步骤 2: 配置 API Key

在 `.env` 文件中：

```bash
BY19CODE_GLM_API_KEY=f783f5c1a67d4602899b5964748bfd81.BKlNTp2R56RP2R4T
```

**注意**：
- API Key 包含点号（.），不要遗漏
- 确保没有前后空格
- 环境变量名必须全大写：`BY19CODE_GLM_API_KEY`

---

## 完整的 .env 配置示例

```bash
# Claude
BY19CODE_CLAUDE_API_KEY=sk-ant-api03-xxxxxxxxxxxxx

# DeepSeek
BY19CODE_DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

# Kimi
BY19CODE_KIMI_API_KEY=sk-xxxxxxxxxxxxx

# 豆包（注意：还需要在 config.json 中配置 endpoint ID）
BY19CODE_DOUBAO_API_KEY=5e0cfca5-ed98-4f8b-90a6-21cfbb063f5d

# GLM（注意：API Key 包含点号）
BY19CODE_GLM_API_KEY=f783f5c1a67d4602899b5964748bfd81.BKlNTp2R56RP2R4T
```

---

## 测试验证

### 1. 验证配置加载
```bash
python quick_test.py
```

预期输出：所有模型显示 [OK]

### 2. 测试模型切换
```bash
python -m by19code.main

> /model
> /model glm
> 你好
```

### 3. 测试豆包
```bash
> /model doubao
> 你好
```

如果豆包还是报错，检查：
1. endpoint ID 是否正确配置在 `config.json` 中
2. API Key 是否正确
3. 火山引擎账户是否有余额

---

## 常见问题

### Q: 为什么修改 .env 后还是显示 [NO]？
A: 需要重启程序。修改 `.env` 文件后，运行中的程序不会自动重新加载。

### Q: 豆包的 endpoint ID 在哪里找？
A: 
1. 登录火山引擎控制台
2. 进入"推理接入点"页面
3. 创建或查看已有的接入点
4. 复制 endpoint ID（格式：ep-xxxxxx）

### Q: GLM 的 API Key 格式是什么？
A: GLM 的 API Key 包含点号，格式：`前缀.后缀`，例如：
```
f783f5c1a67d4602899b5964748bfd81.BKlNTp2R56RP2R4T
```

### Q: 如何确认 API Key 是否有效？
A: 运行 `python quick_test.py`，查看每个模型的状态：
- [OK] = API Key 已配置
- [NO] = API Key 未配置或格式错误

---

## 修改的文件

1. **by19code/config/settings.py**
   - 添加了 `.env` 文件自动加载功能

2. **.env**
   - 修正了环境变量名称大小写

---

## 总结

✅ 所有模型的 API Key 现在都能正确加载  
✅ 配置加载时自动读取 `.env` 文件  
⚠️ 豆包需要额外配置 endpoint ID  
⚠️ GLM 的 API Key 包含点号，注意完整复制

如有问题，请查看日志文件 `by19code.log` 获取详细错误信息。
