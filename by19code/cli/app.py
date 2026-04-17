"""BY19Code CLI 主应用【T13】

提供交互式 REPL 循环、命令处理、对话管理等功能。
"""
from __future__ import annotations

import logging
from pathlib import Path

from by19code.config.settings import AppConfig
from by19code.core.engine import ChatEngine
from by19code.cli.renderer import Renderer
from by19code.core.project_init import check_and_init_project

logger = logging.getLogger(__name__)

# 各厂商模型产品矩阵：(model_id, label, 简介)
MODEL_MATRIX: dict[str, list[tuple[str, str, str]]] = {
    "claude": [
        ("claude-haiku-4-5-20251001", "Haiku 4.5",  "快速轻量，适合简单任务"),
        ("claude-sonnet-4-6",         "Sonnet 4.6", "均衡性能，推荐日常使用"),
        ("claude-opus-4-5-20251101",  "Opus 4.5",   "强推理，复杂编程首选"),
        ("claude-opus-4-6",           "Opus 4.6",   "最强模型，顶级推理能力"),
    ],
    "deepseek": [
        ("deepseek-chat",     "DeepSeek-V3", "通用对话/编程，性价比极高"),
        ("deepseek-reasoner", "DeepSeek-R1", "推理增强，适合复杂逻辑"),
    ],
    "doubao": [
        ("", "Doubao-Seed-2.0 Code", "编程专用，需填写 Endpoint ID"),
        ("", "Doubao-Seed-2.0 Pro",  "通用模型，需填写 Endpoint ID"),
    ],
    "kimi": [
        ("moonshot-v1-8k",   "Kimi 8K",   "8K 上下文"),
        ("moonshot-v1-32k",  "Kimi 32K",  "32K 上下文"),
        ("moonshot-v1-128k", "Kimi 128K", "128K 长文本"),
    ],
    "minimax": [
        ("abab6.5-chat", "MiniMax abab6.5", "通用对话"),
    ],
    "glm": [
        ("glm-4-plus", "GLM-4 Plus", "旗舰模型"),
        ("glm-4-air",  "GLM-4 Air",  "轻量快速"),
    ],
    "openai": [
        ("gpt-4o",      "GPT-4o",      "多模态旗舰"),
        ("gpt-4o-mini", "GPT-4o Mini", "轻量低价"),
    ],
    "qwen": [
        ("qwen-max",  "Qwen-Max",  "通义千问旗舰"),
        ("qwen-plus", "Qwen-Plus", "均衡性能"),
    ],
    "gemini": [
        ("gemini-2.0-flash", "Gemini 2.0 Flash", "快速响应"),
        ("gemini-2.5-pro",   "Gemini 2.5 Pro",   "顶级推理"),
    ],
}


class CLIApp:
    """CLI 主应用

    职责
    ----
    - 管理 REPL 循环
    - 处理用户输入（命令或对话）
    - 调用 ChatEngine 并渲染响应
    - 异常处理和友好提示
    """

    def __init__(self, config: AppConfig, project_root: Path):
        """初始化 CLI 应用。

        参数
        ----
        config       : 应用配置
        project_root : 项目根目录
        """
        self.config = config
        self.project_root = project_root
        self.engine = ChatEngine(config, project_root)
        self.renderer = Renderer()

        # 检查并初始化项目（生成 BY19Code.md）
        check_and_init_project(project_root)

        logger.info("[CLI] 初始化完成: project=%s", project_root)

    async def run(self) -> None:
        """主 REPL 循环。"""
        # 显示欢迎信息
        self.renderer.render_welcome()

        # 显示当前项目信息
        await self._show_project_info()

        try:
            while True:
                try:
                    # 读取用户输入
                    user_input = self.renderer.render_prompt()

                    # 跳过空输入
                    if not user_input.strip():
                        continue

                    # 处理命令或对话
                    if user_input.startswith("/"):
                        await self._handle_command(user_input)
                    else:
                        await self._handle_chat(user_input)

                except KeyboardInterrupt:
                    # Ctrl+C 中断
                    self.renderer.print_warning("\n已中断")
                    continue

                except EOFError:
                    # Ctrl+D 或 /exit 退出
                    break

                except Exception as e:
                    # 未预期的异常
                    logger.error("[CLI] 未预期的异常: %s", e, exc_info=True)
                    self.renderer.print_error(f"\n[错误] 发生未预期的异常: {e}")

        finally:
            # 清理资源
            logger.info("[CLI] 清理资源...")

            # 保存最后使用的项目路径
            try:
                self._save_last_project_path()
            except Exception as e:
                logger.warning("[CLI] 保存项目路径时出错: %s", e)

            try:
                # 关闭数据库连接
                from by19code.db.database import close_db
                await close_db()
                logger.info("[CLI] 数据库连接已关闭")
            except Exception as e:
                logger.warning("[CLI] 关闭数据库时出错: %s", e)

            try:
                # 关闭 HTTP 客户端
                if hasattr(self.engine.provider, '_client'):
                    client = self.engine.provider._client
                    if hasattr(client, 'close'):
                        await client.close()
                        logger.info("[CLI] HTTP 客户端已关闭")
            except Exception as e:
                logger.warning("[CLI] 关闭 HTTP 客户端时出错: %s", e)

    async def _handle_command(self, command: str) -> None:
        """处理斜杠命令。

        参数
        ----
        command : 命令字符串（以 / 开头）
        """
        # 分割命令和参数
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        logger.info("[CLI] 执行命令: %s, 参数: %s", cmd, args)

        try:
            if cmd == "/help":
                self.renderer.render_welcome()

            elif cmd == "/clear":
                result = self.engine.clear_history()
                self.renderer.print_success(result)

            elif cmd == "/compact":
                result = self.engine.compact_context()
                self.renderer.print_success(result)

            elif cmd == "/stats":
                result = self.engine.get_context_stats()
                self.renderer.print_info(result)

            elif cmd == "/cost":
                result = await self.engine.get_cost_summary()
                self.renderer.print_info(result)

            elif cmd == "/project":
                # 显示当前项目信息
                await self._show_project_info()

            elif cmd in ["/switch-project", "/path"]:
                # 切换项目目录
                if args:
                    # 如果提供了路径参数，直接切换
                    await self._switch_project_directory(args)
                else:
                    # 否则交互式询问
                    await self._switch_project_directory()

            elif cmd == "/switch":
                # 切换自动切换模式
                await self._toggle_auto_switch_mode()

            elif cmd == "/model":
                # 列出所有可用模型或切换模型
                if not args:
                    await self._select_and_switch_model()
                else:
                    result = await self.engine.switch_model(args)
                    # 显示模型 logo
                    provider_cfg = self.config.get_active_provider()
                    if provider_cfg:
                        self.renderer.render_model_logo(
                            args,
                            model_label=provider_cfg.model_label,
                            model_id=provider_cfg.model
                        )
                    else:
                        self.renderer.print_success(result)
                    await self._test_connection()

            elif cmd == "/api":
                await self._manage_api_keys()

            elif cmd in ["/exit", "/quit"]:
                self.renderer.print_warning("再见！")
                raise EOFError

            else:
                self.renderer.print_error(f"[错误] 未知命令: {cmd}")
                self.renderer.print_info("输入 /help 查看可用命令")

        except EOFError:
            # 重新抛出 EOFError，让外层处理退出
            raise
        except Exception as e:
            logger.error("[CLI] 命令执行失败: %s - %s", cmd, e)
            self.renderer.print_error(f"[错误] 命令执行失败: {e}")

    async def _select_and_switch_model(self) -> None:
        """显示交互式模型选择菜单并切换。"""
        from rich.prompt import Prompt

        current_provider = self.config.active_provider

        # 构建选择列表
        self.renderer.print_info("\n[可用模型]")
        choices = []
        choice_map = {}

        for idx, provider in enumerate(self.config.llm_providers, 1):
            # 标记当前使用的模型
            marker = "[cyan]*[/cyan] " if provider.name == current_provider else "  "

            # 检查 API Key 是否配置
            has_key = provider.api_key and provider.api_key != f"${{BY19CODE_{provider.name.upper()}_API_KEY}}"
            key_status = "[green][OK][/green]" if has_key else "[red][NO][/red]"

            # 检查是否支持工具调用
            supports_tools = provider.supports_tools if hasattr(provider, 'supports_tools') else True
            tools_status = "" if supports_tools else " [yellow][仅对话][/yellow]"

            self.renderer.console.print(
                f"{marker}[bold]{idx}.[/bold] [bold]{provider.name}[/bold] - {provider.display_name} {key_status}{tools_status}"
            )
            model_show = provider.model_label if provider.model_label else provider.model
            self.renderer.console.print(
                f"    模型: {model_show} | "
                f"费用: {provider.cost_per_1k_input:.2f}/{provider.cost_per_1k_output:.2f} 元/1K tokens"
            )

            choices.append(str(idx))
            choice_map[str(idx)] = (provider.name, has_key)

        # 提示用户选择
        self.renderer.console.print()
        choice = Prompt.ask(
            "[bold green]请选择模型编号[/bold green]",
            choices=choices,
            default=None,
            show_choices=False
        )

        # 切换模型
        if choice in choice_map:
            selected_name, has_key = choice_map[choice]

            # 检查是否已配置 API Key
            if not has_key:
                self.renderer.print_error(f"\n[错误] 模型 {selected_name} 未配置 API Key")
                self.renderer.print_info(f"\n请配置环境变量: BY19CODE_{selected_name.upper()}_API_KEY")
                self.renderer.print_info(f"或在 config.json 中添加 api_key 字段")
                self.renderer.print_info(f"\n参考文档: API_KEY_GUIDE.md")
                return

            if selected_name == current_provider:
                self.renderer.print_info(f"[信息] 已经在使用 {selected_name}")
            else:
                result = await self.engine.switch_model(selected_name)
                # 显示模型 logo
                provider_cfg = self.config.get_active_provider()
                if provider_cfg:
                    self.renderer.render_model_logo(
                        selected_name,
                        model_label=provider_cfg.model_label,
                        model_id=provider_cfg.model
                    )
                else:
                    self.renderer.print_success(result)
                await self._test_connection()

    async def _test_connection(self) -> None:
        """测试当前模型连接是否正常（发送极短消息，超时 10s）。"""
        import asyncio
        from by19code.llm.base import Message, LLMError

        self.renderer.print_info("[连接测试] 正在测试当前模型连接...")
        try:
            response = await asyncio.wait_for(
                self.engine.provider.chat(
                    messages=[Message(role="user", content="hi")],
                    max_tokens=10,
                    temperature=0.0,
                ),
                timeout=10.0,
            )
            self.renderer.print_success(f"[连接测试] 连接正常 (stop_reason={response.stop_reason})")
        except asyncio.TimeoutError:
            self.renderer.print_error("[连接测试] 连接超时（10s）")
        except LLMError as e:
            self.renderer.print_error(f"[连接测试] 连接失败: {e}")
        except Exception as e:
            self.renderer.print_error(f"[连接测试] 未知错误: {e}")

    async def _manage_api_keys(self) -> None:
        """API Key 管理：表单式选择厂商、子模型、输入 API Key。"""
        from rich.prompt import Prompt
        from pathlib import Path
        from by19code.config.settings import save_config, LLMProviderConfig

        self.renderer.console.print("\n[bold cyan]=== API Key 管理 ===[/bold cyan]")

        # 列出所有厂商
        providers = list(MODEL_MATRIX.keys())
        for idx, name in enumerate(providers, 1):
            cfg = self.config.get_provider(name)
            has_key = bool(cfg and cfg.api_key)
            key_status = "[green][OK][/green]" if has_key else "[red][NO][/red]"
            self.renderer.console.print(f"  [bold]{idx}.[/bold] {name:12s} {key_status}")

        self.renderer.console.print()
        choice = Prompt.ask("请选择厂商编号", choices=[str(i) for i in range(1, len(providers) + 1)])
        provider_name = providers[int(choice) - 1]

        # 显示模型矩阵
        models = MODEL_MATRIX[provider_name]
        self.renderer.console.print(f"\n[bold cyan]--- {provider_name} 产品矩阵 ---[/bold cyan]")
        for idx, (model_id, label, desc) in enumerate(models, 1):
            mid = model_id if model_id else "[需填写 Endpoint ID]"
            self.renderer.console.print(f"  [bold]{idx}.[/bold] {label:30s} {mid}")
            self.renderer.console.print(f"       [dim]{desc}[/dim]")

        self.renderer.console.print()
        model_choice = Prompt.ask("请选择产品编号", choices=[str(i) for i in range(1, len(models) + 1)])
        selected_model_id, selected_label, _ = models[int(model_choice) - 1]

        # doubao 需要手动输入 Endpoint ID
        if not selected_model_id:
            selected_model_id = Prompt.ask(f"请输入 {selected_label} 的 Endpoint ID").strip()

        # 输入 API Key
        cfg = self.config.get_provider(provider_name)
        current_key = cfg.api_key if cfg else ""
        masked = f"{current_key[:8]}..." if len(current_key) > 8 else ("已配置" if current_key else "未配置")
        new_key = Prompt.ask(f"请输入 API Key（当前: {masked}，回车跳过）", default="").strip()

        # 更新配置
        if cfg:
            if new_key:
                cfg.api_key = new_key
            cfg.model = selected_model_id
            cfg.model_label = selected_label
        else:
            # 新增 provider 配置
            from by19code.config.settings import LLMProviderConfig
            new_cfg = LLMProviderConfig(
                name=provider_name,
                display_name=provider_name,
                provider_type="anthropic" if provider_name == "claude" else "openai_compat",
                api_key=new_key,
                base_url="",
                model=selected_model_id,
                model_label=selected_label,
            )
            self.config.llm_providers.append(new_cfg)

        # 保存到全局配置
        global_config_path = Path.home() / ".by19code" / "config.json"
        try:
            save_config(self.config, global_config_path)
            self.renderer.print_success(f"[成功] 已保存 {provider_name}【{selected_label}】配置")
        except Exception as e:
            self.renderer.print_error(f"[错误] 保存失败: {e}")
            return

        # 询问是否立即切换
        switch = Prompt.ask("是否立即切换到该模型？", choices=["y", "n"], default="y")
        if switch == "y":
            result = await self.engine.switch_model(provider_name)
            # 显示模型 logo
            provider_cfg = self.config.get_active_provider()
            if provider_cfg:
                self.renderer.render_model_logo(
                    provider_name,
                    model_label=provider_cfg.model_label,
                    model_id=provider_cfg.model
                )
            else:
                self.renderer.print_success(result)
            await self._test_connection()

    async def _toggle_auto_switch_mode(self) -> None:

        current_mode = self.config.safety.auto_switch_on_timeout
        current_timeout = self.config.safety.change_model_time

        self.renderer.print_info("\n[自动切换模式设置]")
        self.renderer.print_info(f"当前状态: {'启用' if current_mode else '禁用'}")
        self.renderer.print_info(f"超时阈值: {current_timeout} 秒")
        self.renderer.print_info("\n说明：")
        self.renderer.print_info("  - 启用后，模型超时将自动切换到超时次数最少的模型")
        self.renderer.print_info("  - 禁用后，模型超时将保持等待")
        self.renderer.print_info("\n请选择：")
        self.renderer.print_info("  0. 禁用自动切换（保持等待）")
        self.renderer.print_info("  1. 启用自动切换（超时自动换模型）")

        choice = Prompt.ask("\n请选择", choices=["0", "1"], default="0" if not current_mode else "1")

        new_mode = (choice == "1")

        if new_mode != current_mode:
            self.config.safety.auto_switch_on_timeout = new_mode

            # 保存到全局配置
            try:
                from by19code.config.settings import save_config
                from pathlib import Path

                global_config_dir = Path.home() / ".by19code"
                global_config_dir.mkdir(parents=True, exist_ok=True)
                global_config_path = global_config_dir / "config.json"

                save_config(self.config, global_config_path)
                logger.info("[CLI] 已保存自动切换模式: %s", new_mode)
            except Exception as e:
                logger.error("[CLI] 保存配置失败: %s", e)

            status = "启用" if new_mode else "禁用"
            self.renderer.print_success(f"\n[成功] 已{status}自动切换模式")

            if new_mode:
                self.renderer.print_info(f"模型超过 {current_timeout} 秒无响应时将自动切换")
                self.renderer.print_info("优先选择历史超时次数最少的模型")
            else:
                self.renderer.print_info("模型超时时将保持等待")
        else:
            self.renderer.print_info(f"\n[信息] 保持当前设置：{'启用' if current_mode else '禁用'}")

    async def _show_project_info(self) -> None:
        """显示当前项目信息（包括项目描述和当前使用的模型）。"""
        project_name = self.project_root.name

        # 搜索项目描述文件
        project_desc = self._find_project_description()

        # 获取当前使用的模型信息
        current_provider = self.config.active_provider
        provider_config = self.config.get_active_provider()
        model_display_name = provider_config.display_name if provider_config else current_provider
        model_label = provider_config.model_label if provider_config and provider_config.model_label else ""
        model_id = provider_config.model if provider_config else ""

        self.renderer.render_project_info(
            str(self.project_root),
            project_name,
            project_desc,
            current_provider,
            model_display_name,
            model_label,
            model_id,
        )

    def _find_project_description(self) -> str:
        """搜索项目目录下的 MD 文件或 README 文件，提取项目描述。

        返回
        ----
        str : 项目描述，未找到返回空字符串
        """
        # 优先级：BY19Code.md > README.md > CLAUDE.md > 其他 .md 文件
        priority_files = [
            "BY19Code.md",
            "README.md",
            "CLAUDE.md",
        ]

        # 先检查优先级文件
        for filename in priority_files:
            file_path = self.project_root / filename
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    # 提取第一行标题或前 200 个字符
                    lines = content.strip().split('\n')
                    if lines:
                        first_line = lines[0].strip()
                        # 如果是 Markdown 标题，去掉 # 号
                        if first_line.startswith('#'):
                            return first_line.lstrip('#').strip()
                        # 否则返回前 200 个字符
                        return content[:200].strip()
                except Exception as e:
                    logger.warning("[CLI] 读取项目描述文件失败: %s - %s", filename, e)

        # 如果没有找到优先级文件，搜索其他 .md 文件
        try:
            md_files = list(self.project_root.glob("*.md"))
            if md_files:
                # 使用第一个找到的 .md 文件
                file_path = md_files[0]
                content = file_path.read_text(encoding="utf-8")
                lines = content.strip().split('\n')
                if lines:
                    first_line = lines[0].strip()
                    if first_line.startswith('#'):
                        return first_line.lstrip('#').strip()
                    return content[:200].strip()
        except Exception as e:
            logger.warning("[CLI] 搜索 .md 文件失败: %s", e)

        return ""

    async def _switch_project_directory(self, path: str = "") -> None:
        """切换项目工作目录。

        参数
        ----
        path : 新的项目目录路径（可选）
        """
        from rich.prompt import Prompt

        # 如果没有提供路径，交互式询问
        if not path:
            self.renderer.print_info("\n[切换项目目录]")
            self.renderer.print_info(f"当前目录: {self.project_root}")

            # 询问新目录
            path = Prompt.ask("\n请输入新的项目目录路径")

        new_project_root = Path(path).resolve()

        # 验证目录是否存在
        if not new_project_root.exists():
            self.renderer.print_error(f"\n[错误] 目录不存在: {new_project_root}")
            return

        if not new_project_root.is_dir():
            self.renderer.print_error(f"\n[错误] 路径不是目录: {new_project_root}")
            return

        # 切换目录
        old_root = self.project_root
        self.project_root = new_project_root

        # 更新引擎的项目根目录
        self.engine.project_root = new_project_root

        # 重新初始化 System Prompt（包含新的项目路径）
        self.engine._init_system_prompt()

        # 更新配置
        self.config.workspace.default_path = str(new_project_root)

        logger.info("[CLI] 切换项目目录: %s → %s", old_root, new_project_root)

        # 显示切换成功和新项目信息
        self.renderer.print_success(f"\n[成功] 已切换到: {new_project_root}\n")

        # 显示详细的项目信息
        project_name = new_project_root.name
        project_desc = self._find_project_description()

        # 检查目录是否为空
        try:
            has_files = any(new_project_root.iterdir())
        except Exception:
            has_files = False

        if has_files and project_desc:
            # 有文件且找到项目描述
            self.renderer.console.print(f"[bold cyan]当前工作目录：[/bold cyan]{new_project_root}")
            self.renderer.console.print(f"[bold cyan]属于项目：[/bold cyan][bold]{project_name}[/bold]")
            self.renderer.console.print(f"[dim]项目描述：{project_desc}[/dim]\n")
        elif has_files:
            # 有文件但没有找到项目描述
            self.renderer.console.print(f"[bold cyan]当前工作目录：[/bold cyan]{new_project_root}")
            self.renderer.console.print(f"[dim]（未找到项目描述文件）[/dim]\n")
        else:
            # 空目录
            self.renderer.console.print(f"[bold cyan]当前工作目录：[/bold cyan]{new_project_root}")
            self.renderer.console.print(f"[yellow]（目录为空）[/yellow]\n")

    def _save_last_project_path(self) -> None:
        """保存最后使用的项目路径到全局配置。"""
        try:
            from by19code.config.settings import save_config

            # 更新配置中的最后项目路径
            self.config.workspace.last_project_path = str(self.project_root)

            # 保存到全局配置文件
            global_config_dir = Path.home() / ".by19code"
            global_config_dir.mkdir(parents=True, exist_ok=True)
            global_config_path = global_config_dir / "config.json"

            save_config(self.config, global_config_path)
            logger.info("[CLI] 已保存最后项目路径: %s", self.project_root)

        except Exception as e:
            logger.error("[CLI] 保存项目路径失败: %s", e)

    async def _handle_chat(self, user_input: str) -> None:
        """处理普通对话。

        参数
        ----
        user_input : 用户输入的文本
        """
        logger.info("[CLI] 用户输入: %s", user_input[:50])

        try:
            # 启动等待计时器
            self.renderer.start_waiting_timer()

            # 调用引擎并流式渲染响应
            async for event in self.engine.chat(user_input):
                # 只在收到实际 LLM 响应时停止等待计时器
                if event.event_type in ("text_delta", "tool_call_start", "error", "done"):
                    self.renderer.stop_waiting_timer()

                # 渲染事件
                self.renderer.render_stream(event)

            # 确保计时器已停止
            self.renderer.stop_waiting_timer()

        except Exception as e:
            # 停止计时器
            self.renderer.stop_waiting_timer()

            logger.error("[CLI] 对话处理失败: %s", e, exc_info=True)
            self.renderer.print_error(f"\n[错误] 对话处理失败: {e}")
