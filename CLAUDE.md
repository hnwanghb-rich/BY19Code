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
- [x] T01 项目脚手架
- [x] T02 配置管理
- [x] T03 数据库初始化
- [x] T04 LLM 适配层基类
- [x] T05 Claude Provider 实现
- [x] T06 OpenAI 兼容 Provider 实现
- [x] T07 Provider 工厂与注册
- [x] 验收节点 A：能说话（T01-T07 全部通过）
- [x] T08 文件操作模块
- [x] T09 命令执行沙箱
- [x] T10 工具定义与注册
- [ ] T11 对话引擎
- [ ] T12 上下文管理器
- [ ] 验收节点 B+C：能对话并操作文件
- [ ] T14 Git 操作模块
- [ ] T15 集成测试
- [ ] 验收节点 D：终极验收