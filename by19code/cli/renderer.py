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


# 各厂商模型 Logo（ASCII 艺术字）及品牌颜色
MODEL_LOGOS = {
    "claude": {
        "logo": """
   _____ _                 _
  / ____| |               | |
 | |    | | __ _ _   _  __| | ___
 | |    | |/ _` | | | |/ _` |/ _ \\
 | |____| | (_| | |_| | (_| |  __/
  \\_____|_|\\__,_|\\__,_|\\__,_|\\___|
""",
        "color": "#CC785C"  # Anthropic 橙棕色
    },
    "deepseek": {
        "logo": """
  ____                 ____            _
 |  _ \\  ___  ___ _ __/ ___|  ___  ___| | __
 | | | |/ _ \\/ _ \\ '_ \\___ \\ / _ \\/ _ \\ |/ /
 | |_| |  __/  __/ |_) |__) |  __/  __/   <
 |____/ \\___|\\___| .__/____/ \\___|\\___|_|\\_\\
                 |_|
""",
        "color": "#1E90FF"  # DeepSeek 蓝色
    },
    "doubao": {
        "logo": """
  ____              ____
 |  _ \\  ___  _   _| __ )  __ _  ___
 | | | |/ _ \\| | | |  _ \\ / _` |/ _ \\
 | |_| | (_) | |_| | |_) | (_| | (_) |
 |____/ \\___/ \\__,_|____/ \\__,_|\\___/
""",
        "color": "#5B8FF9"  # 豆包蓝色
    },
    "kimi": {
        "logo": """
  _  ___           _
 | |/ (_)_ __ ___ (_)
 | ' /| | '_ ` _ \\| |
 | . \\| | | | | | | |
 |_|\\_\\_|_| |_| |_|_|
""",
        "color": "#8B5CF6"  # Kimi 紫色
    },
    "minimax": {
        "logo": """
  __  __ _       _ __  __
 |  \\/  (_)_ __ (_)  \\/  | __ ___  __
 | |\\/| | | '_ \\| | |\\/| |/ _` \\ \\/ /
 | |  | | | | | | | |  | | (_| |>  <
 |_|  |_|_|_| |_|_|_|  |_|\\__,_/_/\\_\\
""",
        "color": "#0EA5E9"  # MiniMax 蓝色
    },
    "glm": {
        "logo": """
   ____ _     __  __
  / ___| |   |  \\/  |
 | |  _| |   | |\\/| |
 | |_| | |___| |  | |
  \\____|_____|_|  |_|
""",
        "color": "#3B82F6"  # 智谱蓝色
    },
    "openai": {
        "logo": """
   ___                    _    ___
  / _ \\ _ __   ___ _ __ / \\  |_ _|
 | | | | '_ \\ / _ \\ '_ / _ \\  | |
 | |_| | |_) |  __/ | / ___ \\ | |
  \\___/| .__/ \\___|_|/_/   \\_\\___|
       |_|
""",
        "color": "#10A37F"  # OpenAI 绿色
    },
    "qwen": {
        "logo": """
   ___
  / _ \\__      _____ _ __
 | | | \\ \\ /\\ / / _ \\ '_ \\
 | |_| |\\ V  V /  __/ | | |
  \\__\\_\\ \\_/\\_/ \\___|_| |_|
""",
        "color": "#A855F7"  # 通义千问紫色
    },
    "gemini": {
        "logo": """
   ____                _       _
  / ___| ___ _ __ ___ (_)_ __ (_)
 | |  _ / _ \\ '_ ` _ \\| | '_ \\| |
 | |_| |  __/ | | | | | | | | | |
  \\____|\___|_| |_| |_|_|_| |_|_|
""",
        "color": "#4285F4"  # Google 蓝色
    },
}


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
        self._tool_timer_live = None
        self._tool_timer_start_time = None
        self._tool_timer_thread = None

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

        elif event.event_type == "tool_executing_start":
            # 工具开始执行，启动计时器
            tool_name = event.data
            self.start_tool_timer(tool_name)

        elif event.event_type == "tool_executing_end":
            # 工具执行结束，停止计时器
            self.stop_tool_timer()

        elif event.event_type == "processing":
            # 显示处理中提示并启动等待计时器
            message = event.data
            self.console.print(f"\n[dim]{message}[/dim]")
            self.start_waiting_timer()

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
            "  [cyan]/api[/cyan]      - API Key 管理（配置模型和密钥）\n"
            "  [cyan]/model[/cyan]    - 列出所有可用模型\n"
            "  [cyan]/model[/cyan] <名称> - 切换到指定模型（如：/model kimi）\n"
            "  [cyan]/switch[/cyan]   - 切换自动切换模式（超时是否自动换模型）\n"
            "  [cyan]/project[/cyan]  - 显示当前项目信息\n"
            "  [cyan]/path[/cyan] <目录> - 切换项目工作目录（如：/path D:\\MyProject）\n"
            "  [cyan]/clear[/cyan]    - 清空对话历史\n"
            "  [cyan]/compact[/cyan]  - 压缩上下文（保留最近 10 条消息）\n"
            "  [cyan]/stats[/cyan]    - 查看上下文统计\n"
            "  [cyan]/cost[/cyan]     - 查看费用汇总\n"
            "  [cyan]/exit[/cyan]     - 退出程序\n\n"
            "[dim]直接输入文本开始对话。按 Ctrl+C 可随时中断。[/dim]"
        )

        self.console.print(Panel.fit(welcome_text, title="[bold]欢迎使用[/bold]"))

    def render_project_info(self, project_root: str, project_name: str, project_desc: str = "", current_model: str = "", model_display_name: str = "", model_label: str = "", model_id: str = "") -> None:
        """显示当前项目信息。

        参数
        ----
        project_root : 项目根目录
        project_name : 项目名称
        project_desc : 项目描述（可选）
        current_model : 当前使用的模型名称（可选）
        model_display_name : 模型显示名称（可选）
        """
        self.console.print(f"\n[bold cyan]当前项目：[/bold cyan][bold]{project_name}[/bold]")
        if project_desc:
            self.console.print(f"[dim]项目描述：{project_desc}[/dim]")
        self.console.print(f"[dim]工作目录：{project_root}[/dim]")
        if current_model:
            if model_label:
                model_str = f"{current_model}【{model_label}】"
            elif model_id:
                model_str = f"{current_model}【{model_id}】"
            else:
                model_str = current_model
            self.console.print(f"[bold cyan]当前使用模型：[/bold cyan][bold]{model_str}[/bold]")
        self.console.print()

    def render_prompt(self) -> str:
        """显示输入提示符并读取用户输入。

        行为：
        - 手动输入：回车即执行
        - 粘贴多行文本：忽略文本中的回车，等用户手动按回车才执行
        """
        import msvcrt

        self.console.print("\n[bold green]>[/bold green] ", end="")
        sys.stdout.flush()

        # 读取第一行
        first_line = input()

        # 检查是否有更多输入（粘贴检测）
        # 粘贴时，控制台缓冲区会立即有更多数据
        if not msvcrt.kbhit():
            # 没有更多输入，手动输入，立即执行
            return first_line

        # 有更多输入，说明是粘贴操作，继续读取直到缓冲区清空
        lines = [first_line]
        while msvcrt.kbhit():
            line = input()
            lines.append(line)

        return "\n".join(lines)

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

    def render_model_logo(self, provider_name: str, model_label: str = "", model_id: str = "") -> None:
        """显示模型 Logo。

        参数
        ----
        provider_name : Provider 名称（如 "claude", "deepseek"）
        model_label : 模型标签（如 "Sonnet 4.6"）
        model_id : 模型 ID（如 "claude-sonnet-4-6"）
        """
        logo_data = MODEL_LOGOS.get(provider_name)
        if logo_data:
            logo = logo_data["logo"]
            color = logo_data["color"]
            self.console.print(f"[{color}]{logo}[/{color}]")

        # 显示模型信息
        if model_label:
            model_str = f"{provider_name}【{model_label}】"
        elif model_id:
            model_str = f"{provider_name}【{model_id}】"
        else:
            model_str = provider_name

        self.console.print(f"[bold green]✓ 已切换到：{model_str}[/bold green]\n")

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

    def start_tool_timer(self, tool_name: str) -> None:
        """启动工具执行计时器。

        参数
        ----
        tool_name : 工具名称
        """
        if self._tool_timer_live is None:
            self._tool_timer_start_time = time.time()
            from rich.text import Text

            # 创建一个可更新的 Live 显示
            self._tool_timer_live = Live(
                Text(f"[工具执行] {tool_name}: 0 秒", style="yellow"),
                console=self.console,
                refresh_per_second=2
            )
            self._tool_timer_live.start()

            # 启动后台任务更新计时器
            import threading
            self._tool_timer_thread = threading.Thread(
                target=self._update_tool_timer,
                args=(tool_name,),
                daemon=True
            )
            self._tool_timer_thread.start()

    def _update_tool_timer(self, tool_name: str) -> None:
        """更新工具执行计时器（后台线程）。

        参数
        ----
        tool_name : 工具名称
        """
        from rich.text import Text

        while self._tool_timer_live is not None and self._tool_timer_start_time is not None:
            elapsed = int(time.time() - self._tool_timer_start_time)
            if self._tool_timer_live is not None:
                try:
                    self._tool_timer_live.update(
                        Text(f"[工具执行] {tool_name}: {elapsed} 秒", style="yellow")
                    )
                except Exception:
                    # Live 可能已经停止
                    break
            time.sleep(0.5)

    def stop_tool_timer(self) -> None:
        """停止工具执行计时器。"""
        if self._tool_timer_live is not None:
            try:
                self._tool_timer_live.stop()
            except Exception:
                pass
            self._tool_timer_live = None
            self._tool_timer_start_time = None
