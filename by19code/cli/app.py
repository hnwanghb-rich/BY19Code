"""BY19Code CLI 主应用【T13】

提供交互式 REPL 循环、命令处理、对话管理等功能。
"""
from __future__ import annotations

import logging
from pathlib import Path

from by19code.config.settings import AppConfig
from by19code.core.engine import ChatEngine
from by19code.cli.renderer import Renderer

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

        logger.info("[CLI] 初始化完成: project=%s", project_root)

    async def run(self) -> None:
        """主 REPL 循环。"""
        # 显示欢迎信息
        self.renderer.render_welcome()

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

            elif cmd == "/switch":
                if not args:
                    self.renderer.print_error("[错误] 请指定 provider 名称（如：claude, deepseek）")
                    return

                result = await self.engine.switch_model(args)
                self.renderer.print_success(result)

            elif cmd in ["/exit", "/quit"]:
                self.renderer.print_warning("再见！")
                raise EOFError

            else:
                self.renderer.print_error(f"[错误] 未知命令: {cmd}")
                self.renderer.print_info("输入 /help 查看可用命令")

        except Exception as e:
            logger.error("[CLI] 命令执行失败: %s - %s", cmd, e)
            self.renderer.print_error(f"[错误] 命令执行失败: {e}")

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
