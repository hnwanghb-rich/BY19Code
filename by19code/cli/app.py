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
        project_name = self.project_root.name
        self.renderer.render_project_info(str(self.project_root), project_name)

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
                project_name = self.project_root.name
                self.renderer.render_project_info(str(self.project_root), project_name)

            elif cmd == "/switch":
                if not args:
                    self.renderer.print_error("[错误] 请指定 provider 名称（如：claude, deepseek）")
                    return

                result = await self.engine.switch_model(args)
                self.renderer.print_success(result)

            elif cmd == "/model":
                # 列出所有可用模型或切换模型
                if not args:
                    # 显示交互式选择菜单
                    await self._select_and_switch_model()
                else:
                    # 切换到指定模型
                    result = await self.engine.switch_model(args)
                    self.renderer.print_success(result)

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
            self.renderer.console.print(
                f"    模型: {provider.model} | "
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
                self.renderer.print_success(result)

    async def _handle_chat(self, user_input: str) -> None:
        """处理普通对话。

        参数
        ----
        user_input : 用户输入的文本
        """
        logger.info("[CLI] 用户输入: %s", user_input[:50])

        try:
            # 调用引擎并流式渲染响应
            async for event in self.engine.chat(user_input):
                self.renderer.render_stream(event)

        except Exception as e:
            logger.error("[CLI] 对话处理失败: %s", e, exc_info=True)
            self.renderer.print_error(f"\n[错误] 对话处理失败: {e}")
