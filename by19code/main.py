"""BY19Code 程序入口【T13】

命令行工具的主入口，负责：
1. 解析命令行参数
2. 加载配置
3. 初始化数据库
4. 启动 CLI 应用
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click

from by19code.config.settings import load_config
from by19code.db.database import init_db, get_db
from by19code.cli.app import CLIApp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("by19code.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


@click.command()
@click.option("--config", help="配置文件路径")
@click.option("--project", help="项目根目录", default=None)
@click.version_option(version="0.1.0", prog_name="BY19Code")
def main(config: str | None, project: str | None):
    """BY19Code - AI 编程助手

    一个运行在 Windows 系统上的终端交互式 AI 编程助手。
    通过自然语言对话驱动项目开发，自动完成代码生成、文件操作、Git 提交等任务。

    示例：

        by19code                    # 在当前目录启动

        by19code --project D:\\MyProject  # 指定项目目录

        by19code --config config.json    # 使用自定义配置
    """
    try:
        # Windows 事件循环策略
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            logger.info("[主程序] 已设置 Windows 事件循环策略")

        # 确定项目根目录
        if project is None:
            # 加载配置以获取最后使用的项目路径
            temp_config = load_config(project_dir=None)
            last_project = temp_config.workspace.last_project_path

            # 询问用户选择项目目录
            from rich.console import Console
            from rich.prompt import Prompt

            console = Console()
            console.print("\n[bold cyan]欢迎使用 BY19Code[/bold cyan]")

            if last_project and Path(last_project).exists():
                # 有最后使用的目录
                console.print(f"\n[dim]当前目录：{last_project}[/dim]")
                console.print("\n请选择项目工作目录：")
                console.print("  0. 继续使用当前目录")
                console.print("  1. 使用当前命令行目录")
                console.print("  2. 指定其他目录")

                choice = Prompt.ask("\n请选择", choices=["0", "1", "2"], default="0")

                if choice == "0":
                    project_root = Path(last_project).resolve()
                elif choice == "1":
                    project_root = Path.cwd()
                else:
                    project_path = Prompt.ask("请输入项目目录路径")
                    project_root = Path(project_path).resolve()

                    # 验证目录是否存在
                    if not project_root.exists():
                        console.print(f"[yellow]目录不存在，将创建: {project_root}[/yellow]")
                        project_root.mkdir(parents=True, exist_ok=True)
            else:
                # 没有最后使用的目录
                console.print("\n请指定项目工作目录：")
                console.print("  1. 使用当前目录")
                console.print("  2. 指定其他目录")

                choice = Prompt.ask("\n请选择", choices=["1", "2"], default="1")

                if choice == "1":
                    project_root = Path.cwd()
                else:
                    project_path = Prompt.ask("请输入项目目录路径")
                    project_root = Path(project_path).resolve()

                    # 验证目录是否存在
                    if not project_root.exists():
                        console.print(f"[yellow]目录不存在，将创建: {project_root}[/yellow]")
                        project_root.mkdir(parents=True, exist_ok=True)
        else:
            project_root = Path(project).resolve()

        # 加载配置
        logger.info("[主程序] 加载配置: config=%s, project=%s", config, project_root)

        # 如果指定了配置文件，需要特殊处理
        if config:
            # TODO: 支持自定义配置文件路径
            logger.warning("[主程序] --config 参数暂不支持，将使用默认配置")

        # 加载配置（从项目目录或全局配置）
        app_config = load_config(project_dir=project_root)
        logger.info("[主程序] 配置加载完成: active_provider=%s", app_config.active_provider)

        # 保存当前工作目录到配置
        app_config.workspace.default_path = str(project_root)

        # 初始化数据库
        logger.info("[主程序] 初始化数据库: %s", app_config.database.path)
        asyncio.run(init_db(app_config.database.path))
        logger.info("[主程序] 数据库初始化完成")

        logger.info("[主程序] 项目根目录: %s", project_root)

        # 创建并运行 CLI 应用
        app = CLIApp(app_config, project_root)
        asyncio.run(app.run())

        # 正常退出
        logger.info("[主程序] 程序正常退出")
        print("\n再见！")
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n再见！")
        sys.exit(0)

    except Exception as e:
        logger.error("[主程序] 启动失败: %s", e, exc_info=True)
        print(f"\n[错误] 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
