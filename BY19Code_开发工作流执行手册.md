# BY19Code — Claude Code 开发工作流执行手册（Windows 版）

> **本文档是一份可执行的操作手册**，不是理论指南。  
> **开发环境：Windows 10/11 + PowerShell**  
> 所有命令均为 PowerShell 语法。按顺序做，做一步勾一步。

---

## Phase 0：环境准备与项目初始化（第 1 天）

### 0.0 安装开发工具

打开 PowerShell（管理员权限），执行：

```powershell
# 安装 Python 3.12（如未安装）
winget install Python.Python.3.12

# 安装 Git for Windows（如未安装）
winget install Git.Git

# 安装 Node.js（Claude Code 依赖）
winget install OpenJS.NodeJS.LTS

# 安装 Claude Code
npm install -g @anthropic-ai/claude-code

# 验证安装
python --version        # 应显示 3.12.x
git --version           # 应显示 2.4x.x
node --version          # 应显示 v18+ 或 v20+
claude --version        # 应显示版本号
```

**配置 Git 编码**（重要，只需执行一次）：

```powershell
git config --global core.autocrlf true
git config --global i18n.commitEncoding utf-8
git config --global i18n.logOutputEncoding utf-8
```

**设置 API Key 环境变量**：

```powershell
# 永久设置（重启终端后仍生效）
[Environment]::SetEnvironmentVariable("BY19CODE_CLAUDE_API_KEY", "你的Claude API Key", "User")
[Environment]::SetEnvironmentVariable("BY19CODE_DEEPSEEK_API_KEY", "你的DeepSeek API Key", "User")

# 设置完后重启 PowerShell 使环境变量生效
```

### 0.1 创建仓库

```powershell
# 选择你的项目目录（示例用 D:\Projects）
cd D:\Projects
mkdir BY19Code
cd BY19Code
git init

# 创建目录结构
mkdir docs, tests
mkdir by19code
cd by19code
mkdir cli, core, llm, file_ops, git_ops, db, config
cd ..
```

### 0.2 创建 CLAUDE.md

在项目根目录创建 `CLAUDE.md`，内容如下：

```markdown
# BY19Code 开发约束

## 项目定位
终端交互式 AI 编程助手。MVP 阶段为纯命令行工具，不做 GUI。

## 运行环境
- **操作系统：Windows 10/11**
- 终端：PowerShell 7 / Windows Terminal
- 所有文件读写必须显式指定 encoding="utf-8"
- 路径处理必须使用 pathlib.Path，禁止硬编码分隔符

## 技术栈
- Python 3.12
- click + rich（CLI 与终端渲染）
- anthropic SDK / openai SDK（LLM 调用）
- aiosqlite（异步 SQLite）
- pydantic v2（配置校验）
- subprocess 调用 git CLI（Git 操作）

## 架构原则
- LLM 调用必须经过统一适配层（LLMProvider 基类），新增模型只需实现接口
- 文件操作必须有沙箱限制，禁止操作项目目录外的文件
- 所有外部调用（API / 文件 / Git / shell）必须 try-except
- 每次 LLM 调用自动记录 token 用量到 SQLite
- subprocess 调用必须设置 encoding="utf-8"，避免 Windows GBK 编码问题
- asyncio 入口必须设置 WindowsSelectorEventLoopPolicy

## 代码规范
- 所有函数必须有 type hint
- LLM 调用使用 async/await
- 使用 logging 模块，禁止 print
- 注释使用中文
- 工具状态输出使用 [文件]/[命令]/[Git] 等 ASCII 前缀，不用 emoji

## 当前进度
- [x] PRD 完成
- [ ] T01 项目脚手架
- [ ] T02 配置管理
- ...（随开发进度更新）
```

### 0.3 放入 PRD

```powershell
Copy-Item BY19Code-PRD.md docs\BY19Code-PRD.md
```

### 0.4 首次提交

```powershell
git add -A
git commit -m "chore: 项目初始化，添加 CLAUDE.md 和 MVP PRD"
```

---

## Phase 1：任务拆分（第 1 天）

（任务卡片和依赖关系与上一版完全一致，此处不重复。）

```
T01-T15 共 15 张卡片，4 个验收节点：
A：能说话（T01-T07）
B：能改文件（T08-T12）
C：能交互（T13）
D：能提交（T14-T15）
```

---

## Phase 2：逐任务开发（第 2 天起）

### 核心纪律

```
铁律 1：一次对话只做一张卡片
铁律 2：先设计再实现（复杂模块分两轮对话）
铁律 3：做完一张卡片就提交 Git
铁律 4：到达验收节点必须停下来验证
```

### 每张卡片的 Claude Code 操作流程（Windows 版）

```powershell
# 1. 创建 Git 分支
git checkout -b feat/t01-scaffold

# 2. 启动 Claude Code
claude

# 3. 在 Claude Code 中输入任务提示词（见下方）

# 4. 确认代码正确后
git add -A
git commit -m "feat: 完成 T01 项目脚手架"
git checkout main
git merge feat/t01-scaffold
git branch -d feat/t01-scaffold

# 5. 更新 CLAUDE.md 中的进度
```

---

### 各任务卡片的 Claude Code 提示词

#### T01 项目脚手架

```
阅读 CLAUDE.md 和 docs\BY19Code-PRD.md 的"项目结构"和"Windows 平台编码规范"章节。

请完成项目脚手架搭建：
1. 按 PRD 中的目录结构创建所有包和 __init__.py
2. 创建 pyproject.toml，包含依赖：
   click, rich, anthropic, openai, aiosqlite, pydantic>=2.0, python-dotenv
3. 创建 .gitignore（Python + IDE + .env + config.json + *.db）
4. 创建 .env.example，包含：
   BY19CODE_CLAUDE_API_KEY=
   BY19CODE_DEEPSEEK_API_KEY=
5. 创建 config.example.json（从 PRD 中的配置管理章节复制）
6. 在 main.py 中写一个最简启动入口：打印 "BY19Code v0.1.0" 然后退出

重要：
- 这是 Windows 项目，所有路径使用 pathlib.Path
- main.py 入口处添加 asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
- 不要写业务逻辑，只搭骨架
```

#### T02 配置管理

```
当前任务：T02 配置管理模块

阅读 docs\BY19Code-PRD.md 的"配置管理"章节。

请实现 by19code\config\settings.py：
1. 用 Pydantic v2 定义配置模型（同 PRD 定义）
2. 实现配置加载逻辑：
   - load_config() → 按优先级加载：
     命令行参数 > 项目目录 config.json > %USERPROFILE%\.by19code\config.json > 环境变量 > 默认值
   - 路径展开：支持 %USERPROFILE% 和 ~ 两种写法
   - API Key 从环境变量读取（BY19CODE_{PROVIDER}_API_KEY）
3. 实现 save_config() → 保存到文件（UTF-8 编码）
4. 写单元测试
```

#### T03 数据库初始化

```
当前任务：T03 数据库初始化

阅读 docs\BY19Code-PRD.md 的"数据库与日志"章节。

请实现 by19code\db\ 模块：
1. database.py：
   - async init_db(db_path) → 创建数据库文件和所有表
   - 自动创建父目录（如 %USERPROFILE%\.by19code\）
   - async get_db() → 返回连接（单例模式）
2. models.py：三张表的 CRUD 操作，全部 async
3. SQL 建表语句直接使用 PRD 中定义的
4. 路径存储统一用正斜杠（Path.as_posix()）
5. 写单元测试（使用内存数据库 :memory:）
```

#### T04-T07 LLM 相关

（提示词与上一版相同，此处不重复。LLM 适配层与平台无关。）

---

### 🔴 验收节点 A：能说话（T01-T07 完成后）

**停下来，做验收测试。不要继续做 T08。**

在 PowerShell 中执行：

```powershell
python test_talk.py
```

`test_talk.py` 内容（与上一版相同）。

**必须通过的检查项**：
- [ ] Claude 流式回复正常
- [ ] 切换配置到 DeepSeek 后回复正常
- [ ] SQLite 中有 token_usage 记录（检查 `%USERPROFILE%\.by19code\by19code.db`）
- [ ] 费用计算正确

---

#### T08 文件操作模块

```
当前任务：T08 文件操作模块

请实现 by19code\file_ops\operations.py：
1. read_file(path, project_root) → str
   - 使用 Path.resolve() 验证路径在 project_root 范围内
   - 读取时指定 encoding="utf-8"
2. write_file(path, content, project_root) → str
   - 路径安全检查（同上）
   - 自动创建父目录（Path.mkdir(parents=True, exist_ok=True)）
   - 写入时指定 encoding="utf-8"，换行符用 \n
3. edit_file(path, old_text, new_text, project_root) → str
   - 查找替换，encoding="utf-8"
4. list_directory(path, project_root, depth=2) → str
   - 返回树形目录结构文本
   - 忽略 .git / __pycache__ / node_modules / .venv
5. search_files(pattern, path, project_root) → str
   - 按内容搜索，encoding="utf-8"

Windows 关键点：
- 所有 Path 比较用 resolve() 后比较，处理盘符大小写差异
- 写完整的单元测试，包括路径穿越攻击测试（测试 ..\ 和 C:\Windows）
```

#### T09 命令执行沙箱

```
当前任务：T09 命令执行沙箱

请实现 by19code\core\sandbox.py：
1. async run_command(command, cwd, config: SafetyConfig) → CommandResult
   - 使用 subprocess.run(command, shell=True, cwd=cwd,
     capture_output=True, encoding="utf-8", timeout=config.command_timeout_seconds)
   - Windows 上 shell=True 默认通过 cmd.exe /c 执行
   - 捕获 stdout + stderr
2. Windows 安全黑名单：
   format, shutdown, reboot, del /s /q, rd /s /q, rmdir /s /q,
   Remove-Item -Recurse -Force C:\, reg delete, bcdedit, diskpart, net stop
3. 写单元测试：
   - 正常命令执行（如 echo hello）
   - 黑名单拦截（如 format）
   - 超时中断
   - 路径限制
```

#### T10-T12

（提示词与上一版基本相同。T10 中 system prompt 需注入 Windows 环境信息，见 PRD 4.2 节。）

---

### 🔴 验收节点 B+C：能对话并操作文件

在 PowerShell 中启动：

```powershell
python -m by19code.main
```

**测试脚本**（手动输入）：

```
> 你好

> 帮我创建一个 hello.py，打印 hello world

> 读取 hello.py 的内容

> 把 hello world 改成 hello BY19Code

> 显示当前目录有哪些文件

> 运行 python hello.py

> /model deepseek

> 你好，你是什么模型？

> /cost

> /exit
```

**必须通过的检查项**：
- [ ] 对话流畅，流式输出正常
- [ ] 文件正确创建/修改（UTF-8 编码，无乱码）
- [ ] 命令正确执行（`python hello.py` 输出正确）
- [ ] 模型切换成功
- [ ] /cost 显示正确的用量
- [ ] 路径穿越攻击被拒绝（测试：`读取 C:\Windows\System32\drivers\etc\hosts`）

---

#### T14 Git 操作模块

```
当前任务：T14 Git 操作模块

请实现 by19code\git_ops\operations.py：
1-5 同上一版的功能定义

Windows 关键点：
- subprocess 调用 git 时设置 encoding="utf-8"
- 设置环境变量 env={**os.environ, "LANG": "C.UTF-8"} 确保 git 输出 UTF-8
- git commit -m 的消息如果含中文，在 Windows 上 cmd.exe 默认支持

然后更新 tools.py 中 git 相关工具的实现（替换 TODO）。
```

#### T15 集成测试

（与上一版一致。）

---

### 🔴 验收节点 D：终极验收

在 PowerShell 中执行：

```powershell
cd D:\Projects
mkdir test-calc
cd test-calc
git init
python -m by19code.main
```

输入：

```
> 帮我创建一个 Python 计算器程序，
  支持加减乘除，有命令行交互界面。
  写完后提交到 Git。
```

**必须通过**：
- [ ] AI 创建了可运行的计算器代码
- [ ] 代码能通过 `python calculator.py` 在 Windows 上运行
- [ ] Git 中有正确的 commit 记录（中文 message 无乱码）
- [ ] `%USERPROFILE%\.by19code\by19code.db` 中有完整的 change_logs 和 token_usage

**全部通过 → MVP 完成。**

---

## Phase 3：Claude Code 使用技巧速查

### 启动方式

```powershell
# 在 BY19Code 项目根目录执行
cd D:\Projects\BY19Code
claude                                    # 交互模式
claude "实现 T05 Claude Provider"          # 单次执行
```

### 上下文管理

| 场景 | 操作 |
|------|------|
| 对话太长，Claude 开始遗忘 | 执行 `/compact` 压缩历史 |
| 要开始新任务 | 执行 `/clear` 清空 |
| 关键决策怕丢失 | 写入 CLAUDE.md（`/memory` 命令编辑） |
| 想让 Claude 了解现有代码 | "请先阅读 by19code\llm\base.py，然后..."  |

### Git 工作流（PowerShell）

```powershell
# 每张卡片一个分支
git checkout -b feat/t04-llm-base

# 开发完成
git add -A
git commit -m "feat(llm): T04 LLM 适配层基类实现"
git checkout main
git merge feat/t04-llm-base
git branch -d feat/t04-llm-base

# 推送
git push origin main
```

### 常用命令

| 命令 | 用途 |
|------|------|
| `claude` | 启动 Claude Code 交互模式 |
| `/compact` | 压缩对话历史 |
| `/clear` | 清空对话 |
| `/init` | 初始化 CLAUDE.md |
| `/memory` | 编辑 CLAUDE.md |
| `/cost` | 查看 token 用量 |

### Windows 常见问题排查

| 问题 | 解决方案 |
|------|----------|
| `python` 命令找不到 | 确认安装时勾选了 "Add to PATH"，或运行 `py` 替代 |
| Git 中文乱码 | 执行 `git config --global i18n.commitEncoding utf-8` |
| Rich 输出乱码 | 使用 Windows Terminal 替代 cmd.exe |
| `claude` 命令找不到 | 确认 Node.js 安装正确，`npm install -g @anthropic-ai/claude-code` |
| asyncio 报 `NotImplementedError` | 确认 main.py 入口设置了 `WindowsSelectorEventLoopPolicy` |
| SQLite 数据库找不到 | 检查 `%USERPROFILE%\.by19code\` 目录是否存在 |

---

## Phase 4：MVP 之后的迭代路线

| 轮次 | 时间 | 内容 |
|------|------|------|
| R2 | 4 周 | 更多 LLM（通义千问/智谱/Kimi/GPT-4o）、终端 UI 美化、PRD 自动更新 |
| R3 | 4 周 | GUI 界面（Electron / Tauri）、Token 统计图表、配置界面 |
| R4 | 4 周 | PyInstaller 打包 .exe + Inno Setup 安装程序 |
| R5 | 4 周 | 自动化测试生成与执行、测试报告、自动修复 |
| R6 | 4 周 | 知识提取 + CLAUDE.md 自动更新 + README 生成 |
| R7 | 4 周 | Web 部署 + 跨平台适配 + 性能优化 + 正式发布 |

---

## 执行清单：今天就做的事

```
□  1. 安装开发工具（按 Phase 0.0 执行）
      Python 3.12 + Git + Node.js + Claude Code

□  2. 配置 Git 编码和 API Key 环境变量
      （按 Phase 0.0 执行，重启 PowerShell）

□  3. 创建 Git 仓库 + CLAUDE.md + PRD
      （按 Phase 0.1 - 0.4 执行）

□  4. 启动 Claude Code，执行 T01
      cd D:\Projects\BY19Code
      claude
      → 输入 T01 的提示词

□  5. 完成 T01 后提交 Git，继续 T02
```

每天完成 1-2 张卡片，6-8 周内 MVP 上线。
