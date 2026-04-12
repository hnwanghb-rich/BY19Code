# BY19Code - AI驱动的全栈开发与部署工具

## 产品概述

BY19Code 是一个基于 Windows 的本地可执行程序（.exe），通过自然语言交互实现项目开发、部署、测试和持续优化的全流程自动化工具。

## 核心功能

### 0. 本地数据库与日志系统

**功能描述**
- 为每个项目维护完整的开发历史记录
- 记录所有代码修改、测试结果、发布操作
- 提供查询和分析能力

**数据库设计**

**项目表（Projects）**
```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at DATETIME,
    last_modified DATETIME
);
```

**修改日志表（ChangeLogs）**
```sql
CREATE TABLE change_logs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    timestamp DATETIME,
    change_type TEXT, -- 'code', 'config', 'doc'
    file_path TEXT,
    content_md TEXT, -- Markdown 格式的修改内容
    ai_summary TEXT, -- AI 生成的修改摘要
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

**发布日志表（DeploymentLogs）**
```sql
CREATE TABLE deployment_logs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    timestamp DATETIME,
    platform TEXT, -- 'web', 'windows', 'android', etc.
    status TEXT, -- 'success', 'failed'
    git_commit_hash TEXT,
    system_output TEXT, -- 系统返回的完整信息
    error_message TEXT,
    duration_seconds INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

**测试报告表（TestReports）**
```sql
CREATE TABLE test_reports (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    timestamp DATETIME,
    test_type TEXT, -- 'unit', 'integration', 'e2e'
    total_tests INTEGER,
    passed INTEGER,
    failed INTEGER,
    report_content TEXT, -- 完整测试报告
    ai_analysis TEXT, -- AI 分析结果
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

**Token 使用统计表（TokenUsage）**
```sql
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    provider_name TEXT, -- 模型提供商名称
    model_name TEXT, -- 具体模型名称
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd REAL, -- 本次调用费用（美元）
    project_id INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

**费用统计索引**
```sql
CREATE INDEX idx_token_usage_timestamp ON token_usage(timestamp);
CREATE INDEX idx_token_usage_provider ON token_usage(provider_name);
CREATE INDEX idx_token_usage_project ON token_usage(project_id);
```

**技术要求**
- 使用 SQLite 作为本地数据库
- 每个项目的修改内容以 Markdown 格式存储
- Git 上传和发布的所有系统返回信息（成功/失败）都记录
- 提供日志查询 API
- 定期清理过期日志（可配置保留时长）

**日志记录规则**
- 代码修改：记录文件路径、修改前后对比、修改原因
- Git 操作：记录 commit hash、push 结果、远程响应
- 部署操作：记录目标平台、构建输出、部署结果、错误堆栈
- 测试执行：记录测试框架、用例数量、失败详情、性能数据
- **Token 使用：每次 LLM 调用记录输入/输出 token 数量和费用**

### 1. AI 对话式开发引擎

**功能描述**
- 通过自然语言对话完成项目开发
- **完全复制 Claude Code 的交互形式和用户体验**
- 支持多种大模型 API 配置和实时切换
- 内置中国和美国主流大模型配置

**技术要求**
- 可配置的 LLM API 接口（OpenAI、Claude、国内大模型等）
- API Key、Base URL、模型名称可配置
- 支持流式输出和上下文管理
- 文件读写、代码生成、项目结构管理
- **异步处理机制**：大模型分析时 UI 不阻塞，可继续操作

**内置大模型配置**

国内主流模型：
- 智谱 AI（GLM-4）
- 百度文心一言（ERNIE）
- 阿里通义千问（Qwen）
- 讯飞星火（Spark）
- 月之暗面（Kimi）
- 深度求索（DeepSeek）

国际主流模型：
- Anthropic Claude（Opus/Sonnet/Haiku）
- OpenAI（GPT-4/GPT-4o/GPT-3.5）
- Google Gemini（Pro/Ultra）
- Meta Llama

**模型配置管理**
- 所有大模型参数可在界面上编辑修改
- 支持测试连接功能（验证 API Key 和网络连通性）
- 配置修改实时生效，无需重启
- 支持导入/导出配置文件

**配置参数**
```json
{
  "llm_providers": [
    {
      "name": "Claude",
      "api_key": "sk-xxx",
      "base_url": "https://api.anthropic.com",
      "model": "claude-sonnet-4-6",
      "max_tokens": 8192,
      "cost_per_1k_input": 0.003,
      "cost_per_1k_output": 0.015
    },
    {
      "name": "OpenAI",
      "api_key": "sk-xxx",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4o",
      "max_tokens": 4096,
      "cost_per_1k_input": 0.005,
      "cost_per_1k_output": 0.015
    },
    {
      "name": "Gemini",
      "api_key": "xxx",
      "base_url": "https://generativelanguage.googleapis.com/v1",
      "model": "gemini-pro",
      "max_tokens": 8192,
      "cost_per_1k_input": 0.00025,
      "cost_per_1k_output": 0.0005
    },
    {
      "name": "智谱AI",
      "api_key": "xxx",
      "base_url": "https://open.bigmodel.cn/api/paas/v4",
      "model": "glm-4",
      "max_tokens": 8192,
      "cost_per_1k_input": 0.001,
      "cost_per_1k_output": 0.001
    },
    {
      "name": "通义千问",
      "api_key": "sk-xxx",
      "base_url": "https://dashscope.aliyuncs.com/api/v1",
      "model": "qwen-max",
      "max_tokens": 6000,
      "cost_per_1k_input": 0.0008,
      "cost_per_1k_output": 0.002
    },
    {
      "name": "DeepSeek",
      "api_key": "sk-xxx",
      "base_url": "https://api.deepseek.com",
      "model": "deepseek-chat",
      "max_tokens": 4096,
      "cost_per_1k_input": 0.0001,
      "cost_per_1k_output": 0.0002
    }
  ],
  "active_provider": "Claude",
  "allow_runtime_switch": true
}
```

### 2. Git 一键发布

**功能描述**
- 开发完成后一键推送到 Git 仓库
- 支持 GitHub、GitLab、Gitee 等平台
- 自动生成 commit message
- 支持分支管理和 PR 创建

**技术要求**
- Git 命令行集成
- SSH/HTTPS 认证支持
- 自动化 commit、push、tag 操作
- 可选的 PR/MR 创建

**配置参数**
```json
{
  "git_config": {
    "remote_url": "https://github.com/hnwanghb-rich/BY19Code.git",
    "branch": "main",
    "auth_type": "ssh",
    "ssh_key_path": "~/.ssh/id_rsa",
    "auto_commit_message": true,
    "create_pr": false
  }
}
```

### 3. 多平台一键部署

**功能描述**
支持以下平台的自动化部署：
- **Web 云端项目**：部署到云服务器、容器平台
- **Windows 桌面应用**：打包为 .exe 可执行文件
- **macOS 桌面应用**：打包为 .app 或 .dmg
- **Android App**：打包为 .apk 或 .aab
- **iOS App**：打包为 .ipa（需 macOS 环境）

**技术要求**

**Web 部署**
- Docker 容器化支持
- SSH 远程部署
- 支持 Vercel、Netlify、云服务器等
- 自动化 CI/CD 流程

**桌面应用打包**
- Electron 应用打包（Windows/Mac）
- .NET 应用打包（Windows）
- 代码签名支持

**移动应用打包**
- Android：Gradle 构建、签名、发布
- iOS：Xcode 构建、签名（需 Apple 证书）

**配置参数**
```json
{
  "deployment": {
    "web": {
      "type": "docker",
      "registry": "docker.io/username",
      "server": {
        "host": "192.168.1.100",
        "port": 22,
        "username": "deploy",
        "ssh_key": "~/.ssh/deploy_key"
      }
    },
    "windows": {
      "build_tool": "electron-builder",
      "output_path": "./dist",
      "sign_certificate": "./cert.pfx"
    },
    "android": {
      "build_tool": "gradle",
      "keystore": "./release.keystore",
      "keystore_password": "xxx",
      "output_path": "./app/build/outputs/apk"
    }
  }
}
```

### 4. 自动化测试与迭代

**功能描述**
- 根据项目类型自动生成测试计划
- 执行自动化测试并生成报告
- AI 分析测试结果并自动修复问题
- 支持多轮迭代直到测试通过

**测试类型**
- **Web 项目**：UI 自动化测试（Playwright/Selenium）、API 测试
- **桌面应用**：功能测试、UI 测试
- **移动应用**：Appium 自动化测试

**技术要求**
- 测试框架集成（Jest、Pytest、Playwright 等）
- 测试用例自动生成
- 测试报告解析
- 失败用例的 AI 分析和代码修复

**配置参数**
```json
{
  "testing": {
    "web": {
      "url": "https://example.com",
      "username": "test@example.com",
      "password": "testpass",
      "test_framework": "playwright",
      "browsers": ["chromium", "firefox"]
    },
    "desktop": {
      "executable_path": "C:/Program Files/MyApp/app.exe",
      "test_framework": "pywinauto"
    },
    "mobile": {
      "platform": "android",
      "device": "emulator-5554",
      "app_package": "com.example.app"
    },
    "auto_fix": true,
    "max_iterations": 5
  }
}
```

**测试流程**
1. AI 分析项目结构和功能
2. 生成测试计划（测试场景、用例）
3. 执行自动化测试
4. 生成测试报告（通过率、失败详情）
5. AI 分析失败原因
6. 自动修改代码
7. 重新测试直到通过或达到最大迭代次数

### 5. 自我学习与知识沉淀

**功能描述**
- 从每次测试报告中提取经验教训
- 总结为"关键要求"并写入 CLAUDE.md
- 持续优化开发和测试策略
- **综合分析项目修改日志、测试报告、发布日志生成学习总结**
- **归纳需要改进的问题和值得坚持的经验**

**学习内容**
- 常见错误模式和修复方案
- 项目特定的最佳实践
- 测试覆盖的盲点
- 性能优化建议
- 部署失败的常见原因
- 代码修改的有效模式

**技术要求**
- 测试报告的 NLP 分析
- 知识提取和结构化
- CLAUDE.md 文件的增量更新
- 避免重复记录相同问题
- **跨日志类型的关联分析**（修改→测试→发布的因果关系）

**CLAUDE.md 格式示例**
```markdown
# 项目开发关键要求

## 测试相关
- [2026-04-11] 登录功能必须测试 session 过期场景
- [2026-04-10] API 响应时间应 < 200ms，超时需优化

## 代码规范
- [2026-04-09] 所有异步操作必须有错误处理
- [2026-04-08] 数据库查询必须使用参数化防止 SQL 注入

## 部署注意事项
- [2026-04-07] Docker 镜像需包含时区配置
- [2026-04-06] 生产环境禁用 debug 模式

## 值得坚持的经验
- [2026-04-05] 使用 TypeScript 严格模式减少了 40% 的运行时错误
- [2026-04-04] 增量部署策略使回滚时间从 10 分钟降至 30 秒

## 需要改进的问题
- [2026-04-03] 数据库迁移脚本缺少回滚机制，导致部署失败后难以恢复
- [2026-04-02] 前端打包体积过大（5MB+），需要引入代码分割
```

### 6. 自动生成 README 文档

**功能描述**
- 读取项目最新代码自动生成 README.md
- 包含项目介绍、功能特性、安装说明、使用方法
- 根据代码结构自动识别技术栈

**生成内容**
- 项目名称和简介
- 技术栈（从 package.json、requirements.txt 等识别）
- 目录结构
- 安装步骤
- 运行命令
- API 文档（如果是后端项目）
- 配置说明
- 贡献指南

**技术要求**
- 代码结构分析
- 依赖文件解析
- Markdown 生成
- 可自定义模板

**README 模板示例**
```markdown
# {项目名称}

{AI 生成的项目简介}

## 技术栈

- {识别的技术栈列表}

## 功能特性

- {从代码分析得出的功能列表}

## 安装

\`\`\`bash
{根据项目类型生成的安装命令}
\`\`\`

## 使用

\`\`\`bash
{运行命令}
\`\`\`

## 配置

{配置文件说明}

## API 文档

{如果是后端项目，列出主要 API}

## 项目结构

\`\`\`
{目录树}
\`\`\`

## 贡献

欢迎提交 Issue 和 Pull Request

## 许可证

{识别的许可证类型}
```

### 7. Token 使用统计与费用分析

**功能描述**
- 实时统计所有大模型的 Token 使用情况
- 计算和展示 API 调用费用
- 多维度数据可视化
- 支持按模型、时间、项目过滤

**统计维度**
- Token 数量统计（输入/输出/总计）
- 费用统计（按美元计算）
- 按模型分类统计
- 按项目分类统计
- 按时间段统计

**可视化图表**

**Token 统计图**
- 纵轴：Token 数量
- 横轴：时间（可切换视图）
  - 年视图：每个月为横轴坐标
  - 月视图：每天为横轴坐标
  - 日视图：每小时为横轴坐标
- 支持堆叠柱状图（区分输入/输出 Token）
- 支持折线图（显示趋势）

**费用统计图**
- 纵轴：费用金额（美元）
- 横轴：时间（可切换视图）
  - 年视图：每个月为横轴坐标
  - 月视图：每天为横轴坐标
  - 日视图：每小时为横轴坐标
- 支持饼图（按模型占比）
- 支持柱状图（按时间段对比）

**过滤功能**
- 全部模型 / 指定模型
- 全部项目 / 指定项目
- 自定义时间范围
- 导出统计报表（CSV/Excel）

**技术要求**
- 每次 LLM 调用自动记录 Token 使用
- 根据模型配置的单价自动计算费用
- 使用图表库（如 Chart.js、ECharts）
- 数据聚合查询优化（使用索引）
- 支持数据导出

**统计界面布局**
```
┌─────────────────────────────────────────┐
│  Token 使用统计与费用分析                │
├─────────────────────────────────────────┤
│  过滤器：                                │
│  [模型选择▼] [项目选择▼] [时间范围▼]    │
│  [年视图] [月视图] [日视图]              │
├─────────────────────────────────────────┤
│  总览卡片：                              │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │总Token│总费用│今日Token│今日费用│    │
│  └─────┘ └─────┘ └─────┘ └─────┘       │
├─────────────────────────────────────────┤
│  Token 使用趋势图                        │
│  [柱状图/折线图切换]                     │
│  ┌───────────────────────────────────┐  │
│  │                                   │  │
│  │      [图表显示区域]               │  │
│  │                                   │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  费用统计图                              │
│  [柱状图/饼图切换]                       │
│  ┌───────────────────────────────────┐  │
│  │                                   │  │
│  │      [图表显示区域]               │  │
│  │                                   │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  详细数据表格                            │
│  时间 | 模型 | 输入Token | 输出Token |   │
│       费用 | 项目                        │
│  [导出 CSV] [导出 Excel]                │
└─────────────────────────────────────────┘
```

**费用计算公式**
```
单次调用费用 = (输入Token数 / 1000) × 输入单价 + (输出Token数 / 1000) × 输出单价
```

**数据聚合查询示例**
```sql
-- 按天统计某模型的 Token 使用
SELECT 
    DATE(timestamp) as date,
    SUM(input_tokens) as total_input,
    SUM(output_tokens) as total_output,
    SUM(total_tokens) as total,
    SUM(cost_usd) as total_cost
FROM token_usage
WHERE provider_name = 'Claude'
    AND timestamp >= '2026-04-01'
    AND timestamp < '2026-05-01'
GROUP BY DATE(timestamp)
ORDER BY date;

-- 按模型统计总费用
SELECT 
    provider_name,
    model_name,
    SUM(total_tokens) as total_tokens,
    SUM(cost_usd) as total_cost,
    COUNT(*) as call_count
FROM token_usage
GROUP BY provider_name, model_name
ORDER BY total_cost DESC;
```

## 技术架构

### 核心开发规则（固定约束）

系统内置三条不可违反的开发规则，确保项目开发的一致性和可控性：

**规则 1：读取 PRD 文件定位修改范围**
- 每次项目代码更新前，必须读取项目根目录下的 `{项目名称}-PRD.md` 文件
- 理解当前修改在整个项目中的位置和作用
- 避免超出需求范围的多余修改
- 确保修改符合项目整体架构

**规则 2：更新 PRD 文件记录新需求**
- 每次项目代码更新后，将新增的功能需求补充到 `{项目名称}-PRD.md`
- 保持 PRD 文档与实际代码的同步
- 记录需求变更的时间和原因
- 便于后续开发人员理解项目演进历史

**规则 3：遵守 CLAUDE.md 约束条件**
- 每次启动 AI 自动编码前，必须读取项目根目录下的 `CLAUDE.md`
- 严格遵守文件中规定的开发约束和最佳实践
- 不得违反已记录的规则和经验
- 如果 AI 分析发现 CLAUDE.md 中的要求不合理：
  - 必须向用户提出修改建议并说明理由
  - 等待用户确认是否修改
  - 用户同意后才能修改 CLAUDE.md
  - 用户不同意则必须继续遵守原有规则

**规则执行流程**
```
开始编码任务
    ↓
读取 {项目名称}-PRD.md
    ↓
读取 CLAUDE.md
    ↓
检查约束条件合理性
    ↓
[不合理] → 提出修改建议 → 等待用户确认
    ↓
[合理/用户拒绝修改] → 执行代码修改
    ↓
更新 {项目名称}-PRD.md
    ↓
完成任务
```

### 系统架构
```
┌─────────────────────────────────────────┐
│         BY19Code.exe (主程序)            │
├─────────────────────────────────────────┤
│  UI Layer (WPF/Electron)                │
│  - 对话界面（异步非阻塞）                │
│  - 配置管理界面                          │
│  - 测试报告查看                          │
│  - 日志查询界面                          │
├─────────────────────────────────────────┤
│  Core Engine                            │
│  - LLM 调用模块（异步）                 │
│  - 代码生成引擎                          │
│  - 项目管理器                            │
│  - 规则引擎（三大固定规则）              │
├─────────────────────────────────────────┤
│  Database Layer (SQLite)                │
│  - 项目管理                              │
│  - 修改日志（MD 格式）                   │
│  - 发布日志                              │
│  - 测试报告                              │
├─────────────────────────────────────────┤
│  Git Module                             │
│  - 版本控制                              │
│  - 远程推送（异步）                      │
├─────────────────────────────────────────┤
│  Deployment Module (异步)               │
│  - Web 部署器                           │
│  - 桌面打包器                            │
│  - 移动打包器                            │
├─────────────────────────────────────────┤
│  Testing Module (异步)                  │
│  - 测试计划生成                          │
│  - 测试执行引擎                          │
│  - 报告分析器                            │
│  - 自动修复引擎                          │
├─────────────────────────────────────────┤
│  Learning Module                        │
│  - 知识提取                              │
│  - CLAUDE.md 管理                       │
│  - README 自动生成                      │
└─────────────────────────────────────────┘
```

### 异步处理架构

**设计原则**
- 所有耗时操作（LLM 调用、远程发布、测试执行）必须异步执行
- UI 线程永不阻塞，用户可随时进行其他操作
- 后台任务进度实时显示
- 支持任务取消和暂停

**技术实现**
- C#：使用 async/await + Task
- Rust：使用 tokio 异步运行时
- UI 更新：通过消息队列或事件总线

**任务管理**
```
任务队列
├── LLM 分析任务（可并发多个）
├── Git 推送任务
├── 部署任务（可排队）
└── 测试任务（可排队）

状态显示
├── 任务名称
├── 进度百分比
├── 预计剩余时间
└── 取消按钮
```

### 技术栈建议

**主程序**
- 语言：C# (.NET 8) 或 Rust
- UI 框架：WPF 或 Electron
- 配置管理：JSON/YAML
- 异步框架：async/await (C#) 或 tokio (Rust)

**数据库**
- SQLite（轻量级本地数据库）
- ORM：Entity Framework Core (C#) 或 Diesel (Rust)

**LLM 集成**
- HTTP 客户端库
- 流式响应处理
- Token 计数和管理
- 异步请求处理

**Git 集成**
- LibGit2Sharp (C#) 或 git2-rs (Rust)
- 或直接调用 git 命令行

**部署工具**
- Docker SDK
- SSH 客户端库
- 各平台构建工具的命令行调用

**测试框架**
- Playwright（Web）
- Appium（移动）
- PyWinAuto/WinAppDriver（桌面）

**内置大模型 SDK**
- Anthropic SDK
- OpenAI SDK
- 智谱 AI SDK
- 通义千问 SDK
- DeepSeek SDK

## 配置文件结构

**主配置文件：config.json**
```json
{
  "version": "1.0.0",
  "llm_providers": [
    {
      "name": "Claude",
      "api_key": "sk-xxx",
      "base_url": "https://api.anthropic.com",
      "model": "claude-sonnet-4-6",
      "max_tokens": 8192
    },
    {
      "name": "智谱AI",
      "api_key": "xxx",
      "base_url": "https://open.bigmodel.cn/api/paas/v4",
      "model": "glm-4",
      "max_tokens": 8192
    },
    {
      "name": "通义千问",
      "api_key": "sk-xxx",
      "base_url": "https://dashscope.aliyuncs.com/api/v1",
      "model": "qwen-max",
      "max_tokens": 6000
    },
    {
      "name": "DeepSeek",
      "api_key": "sk-xxx",
      "base_url": "https://api.deepseek.com",
      "model": "deepseek-chat",
      "max_tokens": 4096
    },
    {
      "name": "文心一言",
      "api_key": "xxx",
      "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1",
      "model": "ernie-4.0",
      "max_tokens": 2048
    },
    {
      "name": "Kimi",
      "api_key": "sk-xxx",
      "base_url": "https://api.moonshot.cn/v1",
      "model": "moonshot-v1-8k",
      "max_tokens": 8000
    }
  ],
  "active_provider": "Claude",
  "allow_runtime_switch": true,
  "git_config": {
    "remote_url": "https://github.com/hnwanghb-rich/BY19Code.git",
    "branch": "main",
    "auth_type": "ssh",
    "ssh_key_path": "~/.ssh/id_rsa",
    "auto_commit_message": true,
    "create_pr": false
  },
  "deployment": {...},
  "testing": {...},
  "learning": {
    "enabled": true,
    "claude_md_path": "./CLAUDE.md",
    "min_confidence": 0.7
  },
  "workspace": {
    "default_path": "C:/Projects",
    "auto_save": true
  },
  "database": {
    "path": "./data/by19code.db",
    "log_retention_days": 90
  },
  "core_rules": {
    "enforce_prd_read": true,
    "enforce_prd_update": true,
    "enforce_claude_md_check": true,
    "allow_rule_challenge": true
  },
  "async_settings": {
    "max_concurrent_llm_tasks": 3,
    "max_concurrent_deploy_tasks": 2,
    "task_timeout_minutes": 30
  }
}
```

## 用户界面设计

### 主界面
- 左侧：对话区域（完全复制 Claude Code 交互形式）
- 右侧：文件树和代码编辑器
- 底部：状态栏（当前模型、Git 状态、部署状态、后台任务进度）
- 顶部：模型切换下拉菜单（实时切换大模型）

### 配置界面
- LLM 配置标签页（内置主流模型配置）
- Git 配置标签页
- 部署配置标签页
- 测试配置标签页
- 数据库管理标签页

### 测试报告界面
- 测试结果概览
- 失败用例详情
- AI 分析建议
- 一键修复按钮

### 日志查询界面
- 修改日志查看（Markdown 格式）
- 发布日志查看（系统输出）
- 测试报告历史
- 学习总结查看
- 时间线视图
- 搜索和过滤功能

### 后台任务面板
- 当前运行任务列表
- 任务进度条
- 任务日志实时输出
- 取消/暂停按钮
- 任务历史记录

## 开发路线图

### Phase 0：数据库与日志系统（2 周）
- SQLite 数据库设计和实现
- 修改日志记录（Markdown 格式）
- 发布日志记录
- 测试报告存储
- 日志查询 API

### Phase 1：核心对话引擎（4 周）
- LLM API 集成（内置主流模型配置）
- 基础对话界面（复制 Claude Code 交互）
- 文件操作能力
- 配置管理
- 异步处理框架
- 模型实时切换功能

### Phase 2：核心规则引擎（2 周）
- PRD 文件读取和更新机制
- CLAUDE.md 约束检查
- 规则合理性分析
- 用户确认流程
- 规则执行日志

### Phase 3：Git 集成（2 周）
- Git 基础操作
- 远程推送（异步）
- 分支管理
- 操作日志记录

### Phase 4：部署功能（6 周）
- Web 部署（Docker + SSH，异步）
- Windows 桌面打包
- Android 打包
- macOS 和 iOS 打包（可选）
- 部署日志记录

### Phase 5：测试自动化（6 周）
- 测试计划生成
- Web 自动化测试
- 桌面/移动测试
- 测试报告生成和存储
- 异步测试执行

### Phase 6：自动修复与学习（4 周）
- 测试失败分析
- 代码自动修复
- 知识提取（跨日志分析）
- CLAUDE.md 管理
- 学习总结生成

### Phase 7：README 自动生成（1 周）
- 代码结构分析
- 技术栈识别
- Markdown 生成
- 模板定制

### Phase 8：优化与发布（2 周）
- 性能优化
- UI/UX 优化
- 用户文档
- 安装包制作

**总计：29 周（约 7 个月）**

## 成功指标

- 对话式开发效率提升 80%
- 完全复制 Claude Code 的交互体验
- 支持 6+ 主流大模型实时切换
- Git 发布操作减少到 1 次点击
- 部署成功率 > 95%
- 测试自动化覆盖率 > 70%
- 自动修复成功率 > 60%
- 知识沉淀有效性（减少重复错误）> 50%
- 所有日志完整记录率 100%
- UI 异步响应时间 < 100ms（不阻塞）
- 核心规则执行准确率 100%
- README 自动生成准确率 > 85%
- 数据库查询响应时间 < 50ms

## 风险与挑战

1. **LLM API 稳定性**：需要实现重试机制和降级策略
2. **跨平台打包复杂性**：iOS 打包需要 macOS 环境
3. **测试自动化准确性**：AI 生成的测试用例可能不完整
4. **自动修复风险**：可能引入新 bug，需要人工审核机制
5. **成本控制**：LLM API 调用成本需要监控和优化
6. **数据库性能**：大量日志记录可能影响性能，需要索引优化和定期清理
7. **异步任务管理**：多任务并发可能导致资源竞争，需要合理的任务调度
8. **规则冲突处理**：CLAUDE.md 中的规则可能相互矛盾，需要冲突检测机制
9. **多模型兼容性**：不同大模型的 API 格式和能力差异，需要统一适配层
10. **Claude Code 交互复制难度**：完全复制其交互体验需要深入研究其实现细节
11. **日志存储空间**：长期运行可能产生大量日志，需要压缩和归档策略
12. **README 生成质量**：自动生成的文档可能不够人性化，需要持续优化模板

## 附录

### 核心特性总结

**1. Claude Code 级别的交互体验**
- 完全复制 Claude Code 的对话式编程交互
- 自然语言即可完成项目开发
- 流式输出，实时反馈

**2. 多模型灵活切换**
- 内置 10+ 主流大模型配置（国内外）
- 运行时实时切换，无需重启
- 统一的 API 适配层

**3. 完整的开发历史追踪**
- SQLite 本地数据库
- 所有修改以 Markdown 格式记录
- Git 操作和部署的完整日志
- 测试报告持久化存储

**4. 智能规则引擎**
- 三条固定开发规则确保项目一致性
- 自动读取和更新 PRD 文档
- CLAUDE.md 约束检查和合理性分析
- 支持规则质疑和人工确认

**5. 全平台一键部署**
- Web、Windows、Mac、Android、iOS
- 异步部署，不阻塞 UI
- 完整的部署日志和错误追踪

**6. 智能测试与自动修复**
- AI 生成测试计划
- 自动化测试执行
- 失败分析和代码自动修复
- 多轮迭代直到通过

**7. 自我学习与知识沉淀**
- 跨日志类型的关联分析
- 提取经验教训写入 CLAUDE.md
- 区分"值得坚持"和"需要改进"
- 持续优化开发策略

**8. 异步非阻塞架构**
- 所有耗时操作异步执行
- UI 永不阻塞，随时可操作
- 后台任务进度实时显示
- 支持任务取消和暂停

**9. 自动文档生成**
- 读取最新代码自动生成 README
- 识别技术栈和项目结构
- 可自定义模板

**10. 一键 Git 发布**
- 自动 commit、push、tag
- 支持 PR/MR 创建
- 完整的操作日志

### 关键技术决策

**为什么选择 SQLite？**
- 轻量级，无需独立数据库服务
- 单文件存储，便于备份和迁移
- 性能足够支撑单用户场景
- 跨平台兼容性好

**为什么使用异步架构？**
- LLM 调用通常需要 5-30 秒
- 部署和测试可能需要数分钟
- 用户体验要求 UI 不能卡顿
- 支持多任务并行提高效率

**为什么需要固定规则？**
- 防止 AI 偏离项目目标
- 确保文档与代码同步
- 积累和传承项目经验
- 提供人工干预机制

**为什么内置多模型？**
- 不同模型擅长不同任务
- 成本和速度的平衡
- 避免单一 API 故障
- 国内外网络环境适配

### 参考项目
- Claude Code
- Cursor
- GitHub Copilot
- Jenkins/GitLab CI

### 相关技术文档
- Anthropic API Documentation
- OpenAI API Documentation
- Playwright Documentation
- Electron Documentation
