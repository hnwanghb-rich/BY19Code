# 豆包配置快速指南

## 当前状态

✅ API Key 已配置  
❌ Endpoint ID 需要修改

## 需要做什么

### 步骤 1: 获取你的 endpoint ID

1. 访问：https://console.volcengine.com/ark
2. 登录你的火山引擎账号
3. 找到"推理接入点"或"模型推理"
4. 查看你创建的接入点，复制 endpoint ID
   - 格式类似：`ep-20241227105917-abc123`

### 步骤 2: 修改 config.json

打开 `config.json` 文件，找到第 39 行：

**当前配置**：
```json
"model": "ep-20241227105917-xxxxxx",
```

**修改为**：
```json
"model": "ep-20241227105917-你的实际ID",
```

例如，如果你的 endpoint ID 是 `ep-20241227105917-abc123`，则改为：
```json
"model": "ep-20241227105917-abc123",
```

### 步骤 3: 重启程序测试

```bash
python -m by19code.main

> /model doubao
> 你好
```

## 如果还是报错

### 检查清单

1. ✅ Endpoint ID 是否正确复制（包含 `ep-` 前缀）
2. ✅ API Key 是否正确（在 .env 文件中）
3. ✅ 火山引擎账户是否有余额
4. ✅ 推理接入点是否已启用

### 查看详细错误

查看日志文件：
```bash
tail -n 50 by19code.log
```

## GLM 配置

GLM 的配置已经完成，API Key 格式正确（包含点号）。

测试 GLM：
```bash
python -m by19code.main

> /model glm
> 你好
```

## 需要帮助？

如果配置过程中遇到问题：

1. 查看 `DOUBAO_GLM_FIX.md` - 详细的问题解决方案
2. 查看 `API_KEY_GUIDE.md` - API Key 配置指南
3. 查看日志文件 `by19code.log` - 详细错误信息

---

**重要提示**：豆包是唯一需要额外配置 endpoint ID 的模型，其他模型只需要配置 API Key 即可。
