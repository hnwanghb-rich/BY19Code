"""BY19Code 终端渲染器【T13】

使用 rich 库进行终端渲染，提供流式输出、工具状态显示等功能。
"""
from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from by19code.llm.base import StreamEvent


class Renderer:
    """终端渲染器

    职责
    ----
    - 渲染流式事件（文本、工具调用、token 用量等）
    - 显示欢迎信息和帮助
    - 提供输入提示符
    - Windows 兼容（ASCII 前缀，不使用 emoji）
    """

    def __init__(self):
        """初始化渲染器。"""
        # force_terminal=True 确保在管道中也能正常渲染
        self.console = Console(force_terminal=True)

    def render_stream(self, event: StreamEvent) -> None:
        """渲染流式事件。

        参数
        ----
        event : StreamEvent
        """
        if event.event_type == "text_delta":
            # 流式打印文本（无换行）
            self.console.print(event.data, end="")
            # 强制刷新输出缓冲区（Windows 兼容）
            sys.stdout.flush()

        elif event.event_type == "tool_call_start":
            # 显示工具调用开始
            tool_call = event.data
            self.console.print(f"\n[cyan][工具] 调用: {tool_call.name}[/cyan]")

        elif event.event_type == "tool_call_end":
            # 显示工具参数（格式化 JSON）
            tool_call = event.data
            args_json = json.dumps(tool_call.arguments, ensure_ascii=False, indent=2)
            self.console.print(f"[dim]  参数: {args_json}[/dim]")

        elif event.event_type == "usage":
            # 显示 token 用量（灰色小字）
            usage = event.data
            self.console.print(
                f"\n[dim][Token] {usage.total_tokens} tokens "
                f"(输入: {usage.prompt_tokens}, 输出: {usage.completion_tokens})[/dim]"
            )

        elif event.event_type == "done":
            # 换行结束
            self.console.print()

        elif event.event_type == "error":
            # 红色错误信息
            self.console.print(f"\n[bold red][错误] {event.data}[/bold red]")

    def render_welcome(self) -> None:
        """显示欢迎信息和帮助。"""
        welcome_text = (
            "[bold cyan]BY19Code v0.1.0[/bold cyan] - AI 编程助手\n\n"
            "[bold]命令列表：[/bold]\n"
            "  [cyan]/help[/cyan]     - 显示此帮助\n"
            "  [cyan]/model[/cyan]    - 列出所有可用模型\n"
            "  [cyan]/model[/cyan] <名称> - 切换到指定模型（如：/model kimi）\n"
            "  [cyan]/clear[/cyan]    - 清空对话历史\n"
            "  [cyan]/compact[/cyan]  - 压缩上下文（保留最近 10 条消息）\n"
            "  [cyan]/stats[/cyan]    - 查看上下文统计\n"
            "  [cyan]/cost[/cyan]     - 查看费用汇总\n"
            "  [cyan]/exit[/cyan]     - 退出程序\n\n"
            "[dim]直接输入文本开始对话。按 Ctrl+C 可随时中断。[/dim]"
        )

        self.console.print(Panel.fit(welcome_text, title="[bold]欢迎使用[/bold]"))

    def render_prompt(self) -> str:
        """显示输入提示符并读取用户输入。

        返回
        ----
        str : 用户输入的文本
        """
        return Prompt.ask("\n[bold green]>[/bold green]")

    def print_success(self, message: str) -> None:
        """打印成功消息。

        参数
        ----
        message : 消息内容
        """
        self.console.print(f"[green]{message}[/green]")

    def print_info(self, message: str) -> None:
        """打印信息消息。

        参数
        ----
        message : 消息内容
        """
        self.console.print(message)

    def print_error(self, message: str) -> None:
        """打印错误消息。

        参数
        ----
        message : 消息内容
        """
        self.console.print(f"[bold red]{message}[/bold red]")

    def print_warning(self, message: str) -> None:
        """打印警告消息。

        参数
        ----
        message : 消息内容
        """
        self.console.print(f"[yellow]{message}[/yellow]")
