# BY19Code MVP — 产品需求文档

> **版本**：MVP v1.1（Windows 适配版）  
> **定位**：终端交互式 AI 编程助手  
> **技术栈**：Python 3.12  
> **开发与运行环境**：Windows 10/11  
> **目标工期**：6-8 周  
> **完整版 PRD**：见 `docs\BY19Code-PRD-FULL.md`（后续迭代参考）

---

## 1. 产品定位

BY19Code MVP 是一个**终端命令行工具**，通过自然语言对话驱动项目开发。用户在 Windows 终端（推荐 Windows Terminal 或 PowerShell 7）输入自然语言指令，AI 自动完成代码生成、文件操作、Git 提交等开发任务。

**MVP 只做四件事**：能对话、能改代码、能提交 Git、能记日志。

**MVP 不做的事**：GUI 界面、多平台部署打包、自动化测试、自动修复、知识提取、README 生成、iOS/Android 打包。这些留给后续迭代。

---

## 2. 技术栈

| 层 | 选型 | 理由 |
|-----|------|------|
| 语言 | Python 3.12 | Claude 最擅长、LLM SDK 生态最好、原型速度最快 |
| CLI 框架 | click + rich | 成熟稳定，rich 提供语法高亮和流式渲染 |
| LLM SDK | anthropic（Claude）、openai（兼容 DeepSeek 等） | 官方 SDK，流式输出原生支持 |
| 数据库 | SQLite + aiosqlite | 轻量无依赖，异步支持 |
| 数据模型 | Pydantic v2 | 配置校验、类型安全 |
| Git 操作 | subprocess 调用 git CLI | 比 gitpython 更可靠，兼容性更好 |
| 异步框架 | asyncio | Python 原生，配合 async/await |
| 打包 | PyInstaller | 打包为 Windows .exe |

### 2.1 Windows 开发环境要求

| 工具 | 版本要求 | 安装方式 |
|------|----------|----------|
| Python | 3.12+ | python.org 或 `winget install Python.Python.3.12` |
| Git for Windows | 2.40+ | git-scm.com 或 `winget install Git.Git` |
| Node.js | 18+（用于安装 Claude Code） | nodejs.org 或 `winget install OpenJS.NodeJS.LTS` |
| Windows Terminal | 最新版 | Microsoft Store（推荐，Unicode 渲染更好） |

### 2.2 Windows 平台编码规范

以下规范贯穿所有模块，是 Windows 开发的硬性要求：

**编码**：所有文件统一 UTF-8。Python 文件操作必须显式 `encoding="utf-8"`，避免 Windows 默认 GBK 乱码。

**路径**：统一使用 `pathlib.Path`。禁止硬编码 `/` 或 `\\`。数据库中存储路径时使用 `Path.as_posix()` 统一为正斜杠。

**换行符**：Git 配置 `core.autocrlf=true`。代码写入文件统一 `\n`。

**命令执行**：`subprocess.run()` 在 Windows 上默认通过 `cmd.exe /c` 执行。设置 `encoding="utf-8"` 捕获输出。

**终端渲染**：工具状态使用 `[文件]`、`[命令]`、`[Git]` 等 ASCII 前缀替代 emoji，保证 cmd.exe 兼容。Rich 在 Windows Terminal 中表现完整。

---

## 3. 项目结构

```
BY19Code\
├── CLAUDE.md
├── docs\
│   ├── BY19Code-PRD.md
│   └── BY19Code-PRD-FULL.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── config.example.json
├── by19code\
│   ├── __init__.py
│   ├── main.py
│   ├── cli\
│   │   ├── __init__.py
│   │   ├── app.py
│   │   └── renderer.py
│   ├── core\
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── context.py
│   │   ├── tools.py
│   │   └── sandbox.py
│   ├── llm\
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── claude_provider.py
│   │   ├── openai_provider.py
│   │   └── factory.py
│   ├── file_ops\
│   │   ├── __init__.py
│   │   └── operations.py
│   ├── git_ops\
│   │   ├── __init__.py
│   │   └── operations.py
│   ├── db\
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── models.py
│   └── config\
│       ├── __init__.py
│       └── settings.py
└── tests\
    ├── __init__.py
    ├── test_llm.py
    ├── test_engine.py
    ├── test_file_ops.py
    ├── test_git_ops.py
    └── test_db.py
```

---

## 4. 功能模块详细设计

### 4.1 LLM 适配层

（与平台无关，内容不变，此处省略——完整定义见上一版 PRD 4.1 节）

---

### 4.2 对话引擎

**System Prompt 中需注入 Windows 环境信息**：

```
你是 BY19Code，一个运行在 Windows 系统上的 AI 编程助手。

## 运行环境
- 操作系统：Windows
- Shell：PowerShell / cmd.exe
- 执行命令时请使用 Windows 兼容语法
- 文件路径使用 pathlib 或正斜杠，避免反斜杠转义问题
- 所有文件读写使用 UTF-8 编码
```

其余对话引擎设计与上一版一致。

---

### 4.3 工具定义与执行

**沙箱安全规则（Windows 版）**：
- 文件操作仅限项目目录及其子目录，禁止 `..` 路径穿越
- 路径安全检查使用 `Path.resolve()` 解析后比较，兼容 Windows 盘符（如 `D:\`）
- `run_command` 黑名单：

```python
BLOCKED_COMMANDS_WINDOWS = [
    "format",                          # 格式化磁盘
    "shutdown", "reboot",              # 关机重启
    "del /s /q C:\\",                  # 递归删除C盘
    "rd /s /q",                        # 递归删除目录
    "rmdir /s /q",                     # 同上
    "Remove-Item -Recurse -Force C:\\", # PowerShell 递归删除
    "reg delete",                      # 删除注册表
    "bcdedit",                         # 修改启动配置
    "diskpart",                        # 磁盘分区
    "net stop",                        # 停止系统服务
]
```

- `run_command` 使用 `subprocess.run(command, shell=True, encoding="utf-8")` 执行
- 超时 30 秒

---

### 4.4 终端交互界面

工具状态使用 ASCII 前缀保证兼容：

```
[文件] 创建: app\main.py
[文件] 编辑: app\routers\auth.py
[命令] 执行: python hello.py
[Git]  提交: feat(auth): 添加用户注册接口
[完成] 项目创建完成
[错误] 文件路径超出项目范围
```

---

### 4.5 配置管理

**配置文件路径**：
- 全局配置：`%USERPROFILE%\.by19code\config.json`
- 项目配置：项目根目录下的 `config.json`
- 路径中 `%USERPROFILE%` 和 `~` 均通过 `os.path.expandvars()` / `Path.home()` 展开

**数据库默认路径**：`%USERPROFILE%\.by19code\by19code.db`

**环境变量设置**（PowerShell）：
```powershell
# 临时设置（当前会话）
$env:BY19CODE_CLAUDE_API_KEY = "sk-ant-xxx"
$env:BY19CODE_DEEPSEEK_API_KEY = "sk-xxx"

# 永久设置（用户级）
[Environment]::SetEnvironmentVariable("BY19CODE_CLAUDE_API_KEY", "sk-ant-xxx", "User")
```

---

### 4.6 – 4.7 数据库与日志、Git 操作

（与上一版一致，此处不重复。关键 Windows 差异已在 2.2 节统一定义。）

---

## 5 – 8 核心开发规则、验收标准、迭代规划、风险

（与上一版一致，验收标准中的路径穿越测试使用 `C:\Windows\System32\config\SAM` 替代 `/etc/passwd`，终极验收路径使用 `D:\Projects\test-calc`。）

---

## 附录：Windows 特有风险与应对

| 风险 | 应对 |
|------|------|
| GBK 编码导致中文乱码 | 所有 `open()` / `subprocess.run()` 强制 `encoding="utf-8"` |
| cmd.exe 不支持 emoji | 工具状态用 `[文件]` 等 ASCII 前缀 |
| 路径反斜杠转义 | 全部使用 `pathlib.Path`，禁止字符串拼接路径 |
| Windows Defender 拦截 PyInstaller 打包物 | 后续打包时添加代码签名 |
| `asyncio` 在 Windows 上的 `ProactorEventLoop` 兼容性 | 程序入口设置 `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` |
