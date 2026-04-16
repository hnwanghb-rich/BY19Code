"""BY19Code 终端渲染器【T13】

使用 rich 库进行终端渲染，提供流式输出、工具状态显示等功能。
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live

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
        self._spinner_live = None
        self._waiting_timer_live = None
        self._waiting_start_time = None

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
            "  [cyan]/project[/cyan]  - 显示当前项目信息\n"
            "  [cyan]/switch-project[/cyan] - 切换项目工作目录\n"
            "  [cyan]/clear[/cyan]    - 清空对话历史\n"
            "  [cyan]/compact[/cyan]  - 压缩上下文（保留最近 10 条消息）\n"
            "  [cyan]/stats[/cyan]    - 查看上下文统计\n"
            "  [cyan]/cost[/cyan]     - 查看费用汇总\n"
            "  [cyan]/exit[/cyan]     - 退出程序\n\n"
            "[dim]直接输入文本开始对话。按 Ctrl+C 可随时中断。[/dim]"
        )

        self.console.print(Panel.fit(welcome_text, title="[bold]欢迎使用[/bold]"))

    def render_project_info(self, project_root: str, project_name: str, project_desc: str = "") -> None:
        """显示当前项目信息。

        参数
        ----
        project_root : 项目根目录
        project_name : 项目名称
        project_desc : 项目描述（可选）
        """
        self.console.print(f"\n[bold cyan]当前项目：[/bold cyan][bold]{project_name}[/bold]")
        if project_desc:
            self.console.print(f"[dim]项目描述：{project_desc}[/dim]")
        self.console.print(f"[dim]工作目录：{project_root}[/dim]\n")

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

    def start_spinner(self, text: str = "处理中") -> None:
        """启动等待动画。

        参数
        ----
        text : 显示的文本
        """
        if self._spinner_live is None:
            spinner = Spinner("dots", text=f"[cyan]{text}...[/cyan]")
            self._spinner_live = Live(spinner, console=self.console, refresh_per_second=10)
            self._spinner_live.start()

    def stop_spinner(self) -> None:
        """停止等待动画。"""
        if self._spinner_live is not None:
            self._spinner_live.stop()
            self._spinner_live = None

    def start_waiting_timer(self) -> None:
        """启动等待计时器。"""
        if self._waiting_timer_live is None:
            self._waiting_start_time = time.time()
            from rich.text import Text

            # 创建一个可更新的 Live 显示
            self._waiting_timer_live = Live(
                Text("等待响应: 0 秒", style="cyan"),
                console=self.console,
                refresh_per_second=2
            )
            self._waiting_timer_live.start()

            # 启动后台任务更新计时器
            import threading
            self._timer_thread = threading.Thread(target=self._update_waiting_timer, daemon=True)
            self._timer_thread.start()

    def _update_waiting_timer(self) -> None:
        """更新等待计时器（后台线程）。"""
        from rich.text import Text

        while self._waiting_timer_live is not None and self._waiting_start_time is not None:
            elapsed = int(time.time() - self._waiting_start_time)
            if self._waiting_timer_live is not None:
                try:
                    self._waiting_timer_live.update(
                        Text(f"等待响应: {elapsed} 秒", style="cyan")
                    )
                except Exception:
                    # Live 可能已经停止
                    break
            time.sleep(0.5)

    def stop_waiting_timer(self) -> None:
        """停止等待计时器。"""
        if self._waiting_timer_live is not None:
            try:
                self._waiting_timer_live.stop()
            except Exception:
                pass
            self._waiting_timer_live = None
            self._waiting_start_time = None
