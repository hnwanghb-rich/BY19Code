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

#### T04 LLM 适配层基类

```
当前任务：T04 LLM 适配层基类

阅读 CLAUDE.md 和 docs\BY19Code-PRD.md 的"LLM 适配层"和"技术栈"章节。

请实现 by19code\llm\base.py：
1. 定义数据模型（Pydantic v2 或 dataclass）：
   - Message：role（system/user/assistant/tool）、content、tool_calls（可选）、tool_call_id（可选）
   - ToolDefinition：name、description、parameters（JSON Schema dict）
   - TokenUsage：prompt_tokens、completion_tokens、total_tokens、estimated_cost
   - LLMResponse：content、tool_calls（可选）、usage（TokenUsage）、model、stop_reason
   - StreamEvent：event_type（text_delta/tool_call_start/tool_call_delta/tool_call_end/usage/done/error）、data
2. 定义抽象基类 LLMProvider（ABC）：
   - provider_name: str（只读属性）
   - async chat(messages, tools, model, temperature, max_tokens) → LLMResponse
   - async stream_chat(messages, tools, model, temperature, max_tokens) → AsyncGenerator[StreamEvent]
   - calculate_cost(usage: TokenUsage, model: str) → float
3. 定义自定义异常：
   - LLMError（基类）
   - LLMAuthError（API Key 无效）
   - LLMRateLimitError（请求频率限制）
   - LLMTimeoutError（请求超时）
   - LLMResponseError（响应解析失败）

设计原则：
- 基类与具体 Provider 零耦合，不引用 anthropic / openai 包
- 所有方法使用 async/await
- 所有类有完整 type hint 和中文注释
- 写单元测试验证数据模型的序列化/反序列化
```

#### T05 Claude Provider 实现

```
当前任务：T05 Claude Provider 实现

阅读 by19code\llm\base.py 了解基类定义。
阅读 docs\BY19Code-PRD.md 的"技术栈"章节。

请实现 by19code\llm\claude_provider.py：
1. 继承 LLMProvider，实现 ClaudeProvider 类
2. 构造函数：接收 api_key，初始化 anthropic.AsyncAnthropic 客户端
3. 实现 chat() 方法：
   - 将 Message 列表转换为 Anthropic API 格式
   - 处理 system message（Anthropic 的 system 参数是独立的，不在 messages 里）
   - 处理 tool_calls 的请求和响应（Anthropic 的 tool_use / tool_result 格式）
   - 解析响应为 LLMResponse，包含 TokenUsage
4. 实现 stream_chat() 方法：
   - 使用 client.messages.stream() 流式输出
   - 将 Anthropic 的流式事件映射为 StreamEvent：
     content_block_delta（text）→ text_delta
     content_block_start（tool_use）→ tool_call_start
     content_block_delta（input_json_delta）→ tool_call_delta
     content_block_stop → tool_call_end
     message_delta（usage）→ usage
     message_stop → done
   - 异常映射为 error 类型的 StreamEvent
5. 实现 calculate_cost()：
   - Claude 模型价格表（硬编码，后续可配置化）：
     claude-sonnet-4-20250514: input $3/MTok, output $15/MTok
     claude-haiku-4-5-20251001: input $0.80/MTok, output $4/MTok
   - 计算公式：(prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
6. 异常处理：
   - anthropic.AuthenticationError → 抛出 LLMAuthError
   - anthropic.RateLimitError → 抛出 LLMRateLimitError
   - anthropic.APITimeoutError → 抛出 LLMTimeoutError
   - 其他异常 → 抛出 LLMError

注意：
- 所有异常必须 try-except 并转为自定义异常
- stream_chat 中异常也要捕获并 yield error 类型 StreamEvent
- 写单元测试（mock anthropic 客户端）
```

#### T06 OpenAI 兼容 Provider 实现

```
当前任务：T06 OpenAI 兼容 Provider 实现

阅读 by19code\llm\base.py 和 by19code\llm\claude_provider.py 了解已有实现。

请实现 by19code\llm\openai_provider.py：
1. 继承 LLMProvider，实现 OpenAICompatibleProvider 类
2. 构造函数：接收 api_key、base_url、provider_name
   - 初始化 openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
   - 通过 base_url 兼容 DeepSeek 等 OpenAI 格式的 API
3. 实现 chat() 方法：
   - 将 Message 列表转换为 OpenAI API 格式
   - system message 放在 messages 列表第一条
   - 处理 function_call / tool_calls 的请求和响应
   - 解析响应为 LLMResponse
4. 实现 stream_chat() 方法：
   - 使用 client.chat.completions.create(stream=True)
   - 将 OpenAI 的流式 chunk 映射为 StreamEvent：
     chunk.choices[0].delta.content → text_delta
     chunk.choices[0].delta.tool_calls（首次出现）→ tool_call_start
     chunk.choices[0].delta.tool_calls（后续 arguments）→ tool_call_delta
     chunk.choices[0].finish_reason == "tool_calls" → tool_call_end
     chunk.usage（如有）→ usage
     stream 结束 → done
   - 注意：流式模式下 usage 可能不返回，需要在非流式备用方案中获取
5. 实现 calculate_cost()：
   - DeepSeek 价格表：
     deepseek-chat: input ¥1/MTok, output ¥2/MTok（约 $0.14/$0.28）
   - 可扩展支持其他模型
6. 异常处理：
   - openai.AuthenticationError → LLMAuthError
   - openai.RateLimitError → LLMRateLimitError
   - openai.APITimeoutError → LLMTimeoutError
   - 其他 → LLMError

注意：
- base_url 是关键参数，DeepSeek 的 base_url 为 https://api.deepseek.com
- 写单元测试（mock openai 客户端）
- 测试中验证 Claude Provider 和 OpenAI Provider 的接口一致性
```

#### T07 Provider 工厂与注册

```
当前任务：T07 Provider 工厂与注册

阅读 by19code\llm\ 下的 base.py、claude_provider.py、openai_provider.py。
阅读 by19code\config\settings.py 了解配置结构。

请实现 by19code\llm\factory.py：
1. 实现 LLMFactory 类：
   - _providers: dict[str, type[LLMProvider]]（类级别注册表）
   - @classmethod register(name, provider_class) → 注册 Provider
   - @classmethod create(config: AppConfig) → LLMProvider
     根据 config.provider 字段选择对应 Provider 并实例化：
     - "claude" → ClaudeProvider(api_key=config.claude_api_key)
     - "deepseek" → OpenAICompatibleProvider(
         api_key=config.deepseek_api_key,
         base_url="https://api.deepseek.com",
         provider_name="deepseek"
       )
     - 未注册的 provider → 抛出 ValueError
   - @classmethod list_providers() → list[str]（返回所有已注册名称）
2. 模块加载时自动注册默认 Provider：
   LLMFactory.register("claude", ClaudeProvider)
   LLMFactory.register("deepseek", OpenAICompatibleProvider)
3. 实现运行时切换功能：
   - switch_provider(name, config) → LLMProvider
     切换当前使用的 Provider，供 /model 命令调用
4. 更新 by19code\llm\__init__.py：
   - 导出 LLMProvider, LLMFactory, ClaudeProvider, OpenAICompatibleProvider
   - 导出所有数据模型和异常类

写单元测试：
- 测试工厂创建 Claude Provider
- 测试工厂创建 DeepSeek Provider
- 测试未注册 Provider 抛出异常
- 测试 list_providers 返回正确列表
- 测试运行时切换 Provider
```

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

#### T10 工具定义与注册

```
当前任务：T10 工具定义与注册

阅读 docs\BY19Code-PRD.md 的"工具定义与执行"章节（4.3 节）。
阅读 by19code\file_ops\operations.py 和 by19code\core\sandbox.py 了解已有实现。

请实现 by19code\core\tools.py：
1. 定义工具注册表 TOOL_DEFINITIONS: list[ToolDefinition]，包含以下 5 个工具：
   a. read_file：
      - 参数：path（string，必填）
      - 描述："读取指定文件的内容"
      - JSON Schema：{ "type": "object", "properties": { "path": { "type": "string" } }, "required": ["path"] }
   b. write_file：
      - 参数：path（string，必填）、content（string，必填）
      - 描述："创建或覆盖写入文件"
   c. edit_file：
      - 参数：path（string，必填）、old_text（string，必填）、new_text（string，必填）
      - 描述："查找并替换文件中的指定文本"
   d. run_command：
      - 参数：command（string，必填）
      - 描述："在项目目录下执行 shell 命令（Windows cmd.exe）"
   e. list_directory：
      - 参数：path（string，可选，默认 "."）、depth（integer，可选，默认 2）
      - 描述："列出目录结构"

2. 实现工具执行分发函数 async execute_tool(tool_name, arguments, project_root, config) → str：
   - 根据 tool_name 分发到对应的实现函数
   - read_file → 调用 file_ops.read_file(path, project_root)
   - write_file → 调用 file_ops.write_file(path, content, project_root)
   - edit_file → 调用 file_ops.edit_file(path, old_text, new_text, project_root)
   - run_command → 调用 sandbox.run_command(command, project_root, config)
   - list_directory → 调用 file_ops.list_directory(path, project_root, depth)
   - 未知工具名 → 返回错误信息字符串
   - 所有调用 try-except，异常转为友好错误信息返回

3. 预留 Git 工具的 TODO 占位：
   - git_commit：参数 message（string，必填）
   - git_diff：无参数
   - git_log：参数 count（integer，可选，默认 10）
   - git_status：无参数
   - git_create_branch：参数 branch_name（string，必填）
   （这些工具定义先写好 JSON Schema，execute_tool 中返回 "TODO: 待 T14 实现"）

4. 实现 get_tool_definitions() → list[dict] 函数：
   - 将 ToolDefinition 列表转换为 LLM API 所需的工具描述格式
   - Claude 格式：{ "name", "description", "input_schema" }
   - OpenAI 格式：{ "type": "function", "function": { "name", "description", "parameters" } }
   - 通过参数 format="claude" 或 format="openai" 切换

注意：
- 工具描述要用中文，让 LLM 更好理解
- 所有路径参数在执行前都要经过安全检查
- 写单元测试验证工具定义的完整性和执行分发
```

#### T11 对话引擎

```
当前任务：T11 对话引擎核心

阅读 docs\BY19Code-PRD.md 的"对话引擎"章节（4.2 节），特别注意 Windows 环境信息注入。
阅读 by19code\llm\base.py、by19code\llm\factory.py、by19code\core\tools.py 了解依赖。
阅读 by19code\db\models.py 了解数据库记录接口。

请实现 by19code\core\engine.py：
1. 实现 ChatEngine 类：
   - 构造函数：接收 config（AppConfig）、project_root（Path）
   - 内部持有：
     provider: LLMProvider（通过 LLMFactory.create(config) 创建）
     context: ContextManager（T12 实现，此处先用简单列表代替）
     messages: list[Message]（对话历史）
     project_root: Path（当前项目根目录）

2. 初始化 System Prompt（Windows 版本，按 PRD 4.2 节）：
   构建 system_message 内容，必须包含：
   ```
   你是 BY19Code，一个运行在 Windows 系统上的 AI 编程助手。

   ## 运行环境
   - 操作系统：Windows
   - Shell：PowerShell / cmd.exe
   - 执行命令时请使用 Windows 兼容语法
   - 文件路径使用 pathlib 或正斜杠，避免反斜杠转义问题
   - 所有文件读写使用 UTF-8 编码

   ## 当前项目
   - 项目路径：{project_root}
   - 你可以使用以下工具：read_file, write_file, edit_file, run_command, list_directory, git_commit, git_diff, git_log, git_status, git_create_branch

   ## 工作原则
   - 修改文件前先读取确认内容
   - 一次只修改一个文件
   - 修改后说明做了什么改动
   - 执行命令前说明要执行什么
   ```

3. 实现 async chat(user_input: str) → AsyncGenerator[StreamEvent]：
   核心对话循环：
   a. 将 user_input 追加到 messages
   b. 调用 provider.stream_chat(messages, tools=get_tool_definitions())
   c. 收集流式事件并 yield 给调用方
   d. 如果响应中包含 tool_calls：
      - 逐个执行工具：await execute_tool(name, args, project_root, config)
      - 将工具结果作为 tool_result Message 追加到 messages
      - 递归调用 provider.stream_chat() 继续对话
      - 重复直到 LLM 不再调用工具（stop_reason != "tool_use"）
   e. 将 assistant 最终回复追加到 messages
   f. 记录 token 用量到数据库（调用 db.models 的记录函数）

4. 实现 async switch_model(provider_name: str)：
   - 调用 LLMFactory.create() 创建新 Provider
   - 替换当前 self.provider
   - 保留对话历史（messages 不清空）

5. 实现 get_cost_summary() → str：
   - 从数据库查询当前会话的累计 token 用量和费用
   - 格式化为可读字符串

6. 工具调用循环的安全限制：
   - 单次对话最多执行 20 轮工具调用（防止无限循环）
   - 超过限制后停止并告知用户

Windows 关键点：
- System Prompt 中必须注入 Windows 环境信息
- project_root 使用 Path.resolve() 确保为绝对路径
- 所有异常必须 try-except，LLM 异常要区分类型给出友好提示：
  LLMAuthError → "API Key 无效，请检查配置"
  LLMRateLimitError → "请求频率限制，请稍后重试"
  LLMTimeoutError → "请求超时，请检查网络"

写单元测试（mock LLMProvider）：
- 测试普通对话（无工具调用）
- 测试带工具调用的对话（mock 工具执行结果）
- 测试工具调用循环（多轮工具调用直到 LLM 给出最终回复）
- 测试工具调用次数限制
- 测试模型切换
```

#### T12 上下文管理器

```
当前任务：T12 上下文管理器

阅读 by19code\core\engine.py 了解对话引擎如何使用上下文。
阅读 by19code\llm\base.py 中的 Message 和 TokenUsage 定义。

请实现 by19code\core\context.py：
1. 实现 ContextManager 类：
   - 构造函数：接收 max_tokens（int，上下文窗口上限，默认 100000）
   - 内部持有：
     messages: list[Message]（完整对话历史）
     system_message: Message（system prompt，始终保留）
     max_tokens: int

2. 实现 add_message(message: Message)：
   - 追加消息到 messages
   - 调用 _check_and_trim() 检查是否需要裁剪

3. 实现 get_messages() → list[Message]：
   - 返回 [system_message] + messages
   - 供 engine 传给 LLM API

4. 实现 _estimate_tokens(messages: list[Message]) → int：
   - 简易 token 估算：中文按 1 字符 ≈ 2 tokens，英文按 4 字符 ≈ 1 token
   - 遍历所有 message 的 content 计算总 token 数
   - 工具调用的参数 JSON 也计入
   - 不需要精确，用于粗略判断是否超出窗口

5. 实现 _check_and_trim()：
   - 估算当前总 token 数
   - 如果超过 max_tokens 的 80%（预留 20% 给回复）：
     策略一（简单裁剪）：保留 system_message + 最近 N 条消息
     从最早的消息开始删除，直到总 token 数低于 60%
   - 裁剪时注意保持 tool_call 和 tool_result 的配对完整性：
     如果删除了 assistant 的 tool_calls 消息，对应的 tool_result 也必须删除
     反之亦然

6. 实现 clear()：
   - 清空 messages（保留 system_message）

7. 实现 compact() → str：
   - 供 /compact 命令调用
   - 将当前对话历史压缩为摘要：
     a. 统计当前消息数和估算 token 数
     b. 保留最近 10 条消息
     c. 将更早的消息丢弃（MVP 阶段不做 AI 摘要，直接丢弃）
     d. 返回 "已压缩：从 {old_count} 条消息压缩到 {new_count} 条，释放约 {saved_tokens} tokens"

8. 实现 get_stats() → dict：
   - 返回 {"message_count": int, "estimated_tokens": int, "max_tokens": int, "usage_percent": float}

注意：
- tool_call 和 tool_result 的配对完整性是关键，裁剪时不能破坏
- MVP 阶段不使用 tiktoken 等精确计算库，简易估算即可
- 写单元测试：
  - 测试消息添加和获取
  - 测试 token 估算（中文/英文/混合）
  - 测试自动裁剪触发
  - 测试 tool_call/tool_result 配对保护
  - 测试 compact 压缩
  - 测试 clear 清空

完成 T12 后，回到 engine.py 将简单列表替换为 ContextManager：
- self.context = ContextManager(max_tokens=config.max_context_tokens)
- 所有 self.messages 操作改为 self.context.add_message() / self.context.get_messages()
```

#### T13 CLI 交互界面

```
当前任务：T13 CLI 交互界面

阅读 docs\BY19Code-PRD.md 的"终端交互界面"章节（4.4 节）。
阅读 by19code\core\engine.py 了解 ChatEngine 的接口。

请实现 by19code\cli\ 模块：

1. 实现 by19code\cli\renderer.py（终端渲染器）：
   - 使用 rich 库进行终端渲染
   - 实现 render_stream(event: StreamEvent)：
     根据事件类型渲染不同样式：
     - text_delta：流式打印文本（无换行）
     - tool_call_start：显示 "[工具] 调用: {tool_name}"
     - tool_call_end：显示工具参数（格式化 JSON）
     - usage：显示 token 用量（灰色小字）
     - done：换行结束
     - error：红色错误信息
   - 实现 render_welcome()：显示欢迎信息和帮助
   - 实现 render_prompt()：显示输入提示符 ">"
   - 工具状态使用 ASCII 前缀：[文件]/[命令]/[Git]/[完成]/[错误]

2. 实现 by19code\cli\app.py（主应用逻辑）：
   - 实现 CLIApp 类：
     - 构造函数：初始化 config、engine、renderer
     - async run()：主 REPL 循环
       a. 显示欢迎信息
       b. 循环读取用户输入（使用 rich.prompt）
       c. 处理命令（以 / 开头）或普通对话
       d. 调用 engine.chat() 并流式渲染响应
       e. 捕获异常并友好提示
   - 实现命令处理：
     - /help：显示帮助信息
     - /clear：清空对话历史
     - /compact：压缩上下文
     - /stats：显示上下文统计
     - /cost：显示费用汇总
     - /switch <provider>：切换模型
     - /exit 或 /quit：退出程序
   - 实现 Ctrl+C 优雅退出（捕获 KeyboardInterrupt）

3. 实现 by19code\main.py（程序入口）：
   - 使用 click 定义命令行参数：
     @click.command()
     @click.option("--config", help="配置文件路径")
     @click.option("--project", help="项目根目录", default=".")
   - 设置 Windows 事件循环策略：
     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
   - 加载配置（load_config）
   - 初始化数据库（init_db）
   - 创建 CLIApp 并运行

4. Windows 兼容性要点：
   - rich 在 Windows Terminal 中表现完整，cmd.exe 中部分样式降级
   - 输入使用 rich.prompt.Prompt，支持 UTF-8
   - 流式输出使用 rich.console.Console(force_terminal=True)
   - 工具状态不使用 emoji，用 ASCII 前缀

5. 帮助信息示例：
   ```
   BY19Code v0.1.0 - AI 编程助手

   命令列表：
   /help     - 显示此帮助
   /clear    - 清空对话历史
   /compact  - 压缩上下文（保留最近 10 条消息）
   /stats    - 查看上下文统计
   /cost     - 查看费用汇总
   /switch <provider> - 切换模型（claude/deepseek）
   /exit     - 退出程序

   直接输入文本开始对话。
   按 Ctrl+C 可随时中断。
   ```

写单元测试（可选，主要做手动测试）：
- 测试命令解析
- 测试渲染器输出格式
- 手动测试完整交互流程
```

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

---

## 产品迭代记录

### 迭代 V2 — API管理 + 模型矩阵 + 连接测试（2026-04-17）

**新增功能：**

1. **/api 命令 — API Key 管理**
   - 列出所有主流厂商（Claude/DeepSeek/Doubao/Kimi/MiniMax/GLM/OpenAI/Qwen/Gemini）
   - 表单式输入：选择厂商 → 选择子模型 → 输入/更新 API Key
   - 自动保存到全局配置 `%USERPROFILE%\.by19code\config.json`
   - 保存后可立即切换到该模型

2. **模型产品矩阵**
   - 内置各厂商子模型列表（含 model_id、友好名称、简介）
   - 选中子模型后显示产品概要
   - `model_label` 字段支持友好名称显示（如 `Doubao-Seed-2.0 Code`）

3. **切换模型后自动连接测试**
   - `/model` 和 `/api` 切换后自动发送测试请求
   - 超时 10s，返回连接正常/超时/失败结果

4. **兼容性修复**
   - 豆包等国产模型不传 `tool_choice` 参数（避免 400 错误）
   - 自动修正模型输出的绝对路径（`/file.py` → `file.py`）
   - 无工具调用时自动提取代码块写入文件

**涉及文件：**
- `by19code/cli/app.py` — 新增 `/api` 命令、`_manage_api_keys()`、`_test_connection()`
- `by19code/llm/openai_provider.py` — `tool_choice` 兼容性修复
- `by19code/file_ops/operations.py` — 路径自动修正
- `by19code/core/engine.py` — 代码块自动提取写文件
- `by19code/config/settings.py` — 新增 `model_label` 字段、`_deep_merge` 优化

每天完成 1-2 张卡片，6-8 周内 MVP 上线。
