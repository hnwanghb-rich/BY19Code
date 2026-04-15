# T13 CLI 接口 - 使用说明

## 已完成的工作

### 1. 实现的模块
- ✅ `by19code/cli/renderer.py` - 终端渲染器（使用 rich 库）
- ✅ `by19code/cli/app.py` - 主应用逻辑（REPL 循环）
- ✅ `by19code/main.py` - 程序入口（click 命令行）
- ✅ `config.example.json` - 配置文件示例
- ✅ `test_cli.py` - CLI 组件测试脚本

### 2. 功能特性
- 流式文本输出
- 工具调用显示
- Token 用量统计
- 命令处理：/help, /clear, /compact, /stats, /cost, /switch, /exit
- Ctrl+C 优雅中断
- Windows 兼容（ASCII 前缀）

### 3. 测试结果
所有组件测试通过：
- [OK] 渲染器初始化成功
- [OK] 配置创建成功
- [OK] 数据库初始化成功
- [OK] 命令解析成功

## 使用前准备

### 1. 安装依赖
```bash
pip install -e .
```

### 2. 配置 API Key

编辑 `.env` 文件，填入真实的 API Key：

```bash
# Claude API Key
BY19CODE_CLAUDE_API_KEY=sk-ant-xxxxx

# DeepSeek API Key（可选）
BY19CODE_DEEPSEEK_API_KEY=sk-xxxxx
```

### 3. 配置文件（可选）

如果需要自定义配置，复制 `config.example.json` 为 `config.json` 并修改。

## 运行方式

### 方式 1：使用 Python 模块
```bash
python -m by19code.main
```

### 方式 2：使用命令行工具（安装后）
```bash
by19code
```

### 方式 3：指定项目目录
```bash
python -m by19code.main --project D:\MyProject
```

### 方式 4：使用自定义配置
```bash
python -m by19code.main --config my_config.json
```

## 可用命令

在 CLI 中输入以下命令：

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/clear` | 清空对话历史 |
| `/compact` | 压缩上下文（保留最近 10 条消息） |
| `/stats` | 查看上下文统计 |
| `/cost` | 查看费用汇总 |
| `/switch <provider>` | 切换模型（claude/deepseek） |
| `/exit` 或 `/quit` | 退出程序 |

直接输入文本开始对话。按 Ctrl+C 可随时中断。

## 测试对话示例

```
> 你好

> 帮我创建一个 hello.py，打印 hello world

> 读取 hello.py 的内容

> 把 hello world 改成 hello BY19Code

> 显示当前目录有哪些文件

> 运行 python hello.py

> /stats

> /cost

> /exit
```

## 已知问题

### 1. 中文显示乱码
**原因**：Windows cmd.exe 默认使用 GBK 编码

**解决方案**：
- 使用 Windows Terminal（推荐）
- 或在 cmd.exe 中执行：`chcp 65001`

### 2. 警告信息
```
DeprecationWarning: 'asyncio.WindowsSelectorEventLoopPolicy' is deprecated
```

**说明**：这是 Python 3.14 的警告，不影响功能。在 Python 3.16 之前都可以正常使用。

## 下一步

### 验收节点 B+C：能对话并操作文件

完成 T13 后，可以进行手动集成测试：

1. 启动 CLI：`python -m by19code.main`
2. 测试对话功能
3. 测试文件操作（创建、读取、编辑）
4. 测试命令执行
5. 测试模型切换
6. 测试费用统计

### 后续任务

- T14：Git 操作模块
- T15：集成测试
- 验收节点 D：终极验收

## 故障排查

### 问题：ModuleNotFoundError: No module named 'by19code'
**解决**：运行 `pip install -e .` 安装包

### 问题：API Key 无效
**解决**：检查 `.env` 文件中的 API Key 是否正确

### 问题：数据库初始化失败
**解决**：检查 `%USERPROFILE%\.by19code\` 目录权限

### 问题：rich 样式不显示
**解决**：使用 Windows Terminal 而不是 cmd.exe
