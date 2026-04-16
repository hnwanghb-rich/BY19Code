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

### 4.4 终端交互界面（CLI）

**模块**：`by19code/cli/`

**职责**：提供用户交互界面，处理命令输入，渲染 AI 回复和工具执行状态。

#### 4.4.1 架构设计

```
by19code/cli/
├── __init__.py
├── app.py          # 主应用逻辑（REPL 循环）
└── renderer.py     # 终端渲染器（rich 封装）
```

#### 4.4.2 渲染器（renderer.py）

使用 rich 库进行终端渲染，提供以下功能：

**1. 流式事件渲染**

```python
def render_stream(event: StreamEvent) -> None:
    """根据事件类型渲染不同样式"""
    match event.event_type:
        case "text_delta":
            # 流式打印文本（无换行）
            console.print(event.data, end="")
        case "tool_call_start":
            # 显示工具调用开始
            console.print(f"\n[工具] 调用: {event.data.name}", style="cyan")
        case "tool_call_end":
            # 显示工具参数（格式化 JSON）
            console.print(f"  参数: {json.dumps(event.data.arguments, ensure_ascii=False)}", style="dim")
        case "usage":
            # 显示 token 用量（灰色小字）
            console.print(f"\n[Token] {event.data.total_tokens} tokens", style="dim")
        case "done":
            # 换行结束
            console.print()
        case "error":
            # 红色错误信息
            console.print(f"\n[错误] {event.data}", style="bold red")
```

**2. 工具状态前缀（ASCII 兼容）**

```
[文件] 创建: app\main.py
[文件] 编辑: app\routers\auth.py
[命令] 执行: python hello.py
[Git]  提交: feat(auth): 添加用户注册接口
[完成] 项目创建完成
[错误] 文件路径超出项目范围
```

**3. 欢迎信息**

```python
def render_welcome() -> None:
    """显示欢迎信息和帮助"""
    console.print(Panel.fit(
        "[bold cyan]BY19Code v0.1.0[/bold cyan] - AI 编程助手\n\n"
        "命令列表：\n"
        "  /help     - 显示帮助\n"
        "  /clear    - 清空对话历史\n"
        "  /compact  - 压缩上下文\n"
        "  /stats    - 查看上下文统计\n"
        "  /cost     - 查看费用汇总\n"
        "  /switch <provider> - 切换模型\n"
        "  /exit     - 退出程序\n\n"
        "直接输入文本开始对话。按 Ctrl+C 可随时中断。",
        title="欢迎使用"
    ))
```

#### 4.4.3 主应用（app.py）

**CLIApp 类**：

```python
class CLIApp:
    def __init__(self, config: AppConfig, project_root: Path):
        self.config = config
        self.project_root = project_root
        self.engine = ChatEngine(config, project_root)
        self.renderer = Renderer()
    
    async def run(self) -> None:
        """主 REPL 循环"""
        self.renderer.render_welcome()
        
        while True:
            try:
                # 读取用户输入
                user_input = Prompt.ask("\n[bold green]>[/bold green]")
                
                # 处理命令或对话
                if user_input.startswith("/"):
                    await self._handle_command(user_input)
                else:
                    await self._handle_chat(user_input)
            
            except KeyboardInterrupt:
                console.print("\n[yellow]已中断[/yellow]")
                continue
            except EOFError:
                break
    
    async def _handle_command(self, command: str) -> None:
        """处理斜杠命令"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        match cmd:
            case "/help":
                self.renderer.render_welcome()
            case "/clear":
                result = self.engine.clear_history()
                console.print(result, style="green")
            case "/compact":
                result = self.engine.compact_context()
                console.print(result, style="green")
            case "/stats":
                result = self.engine.get_context_stats()
                console.print(result)
            case "/cost":
                result = await self.engine.get_cost_summary()
                console.print(result)
            case "/switch":
                if not args:
                    console.print("[错误] 请指定 provider 名称", style="red")
                    return
                result = await self.engine.switch_model(args)
                console.print(result, style="green")
            case "/exit" | "/quit":
                console.print("[yellow]再见！[/yellow]")
                raise EOFError
            case _:
                console.print(f"[错误] 未知命令: {cmd}", style="red")
    
    async def _handle_chat(self, user_input: str) -> None:
        """处理普通对话"""
        try:
            async for event in self.engine.chat(user_input):
                self.renderer.render_stream(event)
        except Exception as e:
            console.print(f"\n[错误] {e}", style="bold red")
```

#### 4.4.4 程序入口（main.py）

```python
import asyncio
import click
from pathlib import Path

from by19code.config.settings import load_config
from by19code.db.database import init_db
from by19code.cli.app import CLIApp

@click.command()
@click.option("--config", help="配置文件路径")
@click.option("--project", help="项目根目录", default=".")
def main(config: str | None, project: str):
    """BY19Code - AI 编程助手"""
    
    # Windows 事件循环策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 加载配置
    app_config = load_config(config_path=config)
    
    # 初始化数据库
    asyncio.run(init_db(app_config.database.path))
    
    # 创建并运行 CLI 应用
    project_root = Path(project).resolve()
    app = CLIApp(app_config, project_root)
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\n再见！")

if __name__ == "__main__":
    main()
```

#### 4.4.5 Windows 兼容性

| 特性 | Windows Terminal | cmd.exe |
|------|------------------|---------|
| UTF-8 输入输出 | ✅ 完整支持 | ✅ 支持（需设置 chcp 65001） |
| Rich 样式渲染 | ✅ 完整支持 | ⚠️ 部分降级 |
| Emoji | ✅ 支持 | ❌ 不支持（用 ASCII 前缀） |
| 流式输出 | ✅ 流畅 | ✅ 流畅 |
| Ctrl+C 中断 | ✅ 支持 | ✅ 支持 |

**推荐使用 Windows Terminal 以获得最佳体验。**

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

## 5. 用户体验增强功能

### 5.1 交互式模型选择

**功能描述**：使用 `/model` 命令时，显示交互式下拉列表，用户通过数字选择模型，无需手动输入模型名称。

**实现方式**：
- 使用 `rich.prompt.Prompt` 的 `choices` 参数实现数字选择
- 显示模型编号、名称、API Key 状态、费用信息
- 标记当前使用的模型（带 * 标识）

**用户交互流程**：
```
> /model

[可用模型]
  1. claude - Claude (Anthropic) [OK]
    模型: claude-sonnet-4-20250514 | 费用: 3.00/15.00 元/1K tokens
* 2. deepseek - DeepSeek [OK]
    模型: deepseek-chat | 费用: 0.14/0.28 元/1K tokens
  3. openai - OpenAI GPT-4o [OK]
    模型: gpt-4o | 费用: 2.50/10.00 元/1K tokens

请选择模型编号: 3
[成功] 已切换到 openai
```

**代码位置**：`by19code/cli/app.py` - `_select_and_switch_model()` 方法

---

### 5.2 等待处理动画

**功能描述**：在等待 LLM 响应时显示动画标识（如 `处理中...`），提供视觉反馈，避免用户误以为程序卡死。

**实现方式**：
- 使用 `rich.spinner.Spinner` 和 `rich.live.Live` 实现动画效果
- 在发起 LLM 请求前启动 spinner
- 收到第一个响应事件后停止 spinner

**动画样式**：
```
[cyan]处理中...[/cyan]  (带旋转点动画)
```

**代码位置**：
- `by19code/cli/renderer.py` - `start_spinner()` / `stop_spinner()` 方法
- `by19code/cli/app.py` - 在 `_handle_chat()` 中调用

---

### 5.3 模型超时自动切换

**功能描述**：当模型响应超过指定时间（默认 60 秒）无输出时，自动切换到下一个可用模型并重试当前请求。

**配置参数**：
- 配置项：`safety.change_model_time`
- 默认值：60 秒
- 可在 `config.json` 中修改

**切换逻辑**：
1. 检测模型响应超时（超过 `change_model_time` 秒无事件）
2. 自动切换到下一个配置了 API Key 的可用模型
3. 使用相同的用户输入重新发起请求
4. 如果只有一个可用模型，则不切换，返回超时错误

**配置示例**：
```json
{
  "safety": {
    "command_timeout_seconds": 30,
    "max_tool_rounds": 20,
    "change_model_time": 60,
    "blocked_commands": [...]
  }
}
```

**实现细节**：
- 在 `ChatEngine` 中维护 `_last_event_time` 时间戳
- 每次收到事件时更新时间戳
- 在流式响应过程中检测超时
- 超时后调用 `_get_next_available_provider()` 获取下一个模型
- 自动切换并重试

**代码位置**：
- `by19code/config/settings.py` - `SafetyConfig.change_model_time`
- `by19code/core/engine.py` - 超时检测和切换逻辑
- `by19code/core/engine.py` - `_get_next_available_provider()` 方法

**用户体验**：
```
> 帮我分析这段代码

处理中...

[警告] 模型 deepseek 响应超时（60秒），自动切换到 openai
处理中...

[AI 响应内容...]
```

---

### 5.4 项目目录管理

**功能描述**：启动时询问或确认项目工作目录，支持在不同项目间切换，记录当前工作目录。

**启动流程**：
1. 如果未指定 `--project` 参数，询问用户选择：
   - 使用当前目录
   - 指定其他目录
2. 验证目录是否存在，不存在则创建
3. 保存工作目录到配置
4. 显示当前项目信息

**用户交互**：
```
欢迎使用 BY19Code

请指定项目工作目录：
  1. 使用当前目录
  2. 指定其他目录

请选择 [1/2] (1): 2
请输入项目目录路径: D:\Projects\MyApp

当前项目：MyApp
工作目录：D:\Projects\MyApp
```

**命令支持**：
- `/project` - 显示当前项目信息

**代码位置**：
- `by19code/main.py` - 启动时询问项目目录
- `by19code/cli/app.py` - `/project` 命令处理
- `by19code/cli/renderer.py` - `render_project_info()` 方法

---

### 5.5 自动生成 BY19Code.md

**功能描述**：在项目根目录首次使用 BY19Code 时，自动生成 `BY19Code.md` 文件，用于记录项目的设计约束、开发规范和架构决策。

**生成时机**：
- 首次在项目目录启动 BY19Code
- 检测到项目根目录不存在 `BY19Code.md` 文件

**文件内容**：
```markdown
# {项目名称} - BY19Code 项目约束

> 本文件由 BY19Code 自动生成
> 用于记录项目的设计约束、开发规范和架构决策

## 项目信息
- 项目名称
- 项目路径
- 创建时间

## 技术栈
## 开发规范
## 架构设计
## 开发约束
## API 设计
## 数据库设计
## 测试要求
## 部署说明
## 变更记录
```

**作用**：
- 类似 Claude 的 `CLAUDE.md` 文件
- 记录项目特定的约束和规范
- AI 可以读取此文件了解项目上下文
- 团队成员可以维护项目文档

**代码位置**：
- `by19code/core/project_init.py` - 生成逻辑
- `by19code/cli/app.py` - 初始化时调用

---

### 5.6 显示当前项目信息

**功能描述**：在启动时和使用 `/project` 命令时，显示当前工作的项目信息。

**显示内容**：
- 项目名称（目录名）
- 工作目录完整路径

**显示位置**：
1. 启动时，在欢迎信息后显示
2. 使用 `/project` 命令时显示

**用户体验**：
```
BY19Code v0.1.0 - AI 编程助手

当前项目：MyApp
工作目录：D:\Projects\MyApp

>
```

**代码位置**：
- `by19code/cli/renderer.py` - `render_project_info()` 方法
- `by19code/cli/app.py` - 启动和命令处理

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
