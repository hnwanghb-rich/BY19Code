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
@click.option("--project", help="项目根目录", default=".")
@click.version_option(version="0.1.0", prog_name="BY19Code")
def main(config: str | None, project: str):
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

        # 加载配置
        logger.info("[主程序] 加载配置: config_path=%s", config)
        app_config = load_config(config_path=config)
        logger.info("[主程序] 配置加载完成: active_provider=%s", app_config.active_provider)

        # 初始化数据库
        logger.info("[主程序] 初始化数据库: %s", app_config.database.path)
        asyncio.run(init_db(app_config.database.path))
        logger.info("[主程序] 数据库初始化完成")

        # 解析项目根目录
        project_root = Path(project).resolve()
        logger.info("[主程序] 项目根目录: %s", project_root)

        # 创建并运行 CLI 应用
        app = CLIApp(app_config, project_root)
        asyncio.run(app.run())

    except KeyboardInterrupt:
        print("\n再见！")
        sys.exit(0)

    except Exception as e:
        logger.error("[主程序] 启动失败: %s", e, exc_info=True)
        print(f"\n[错误] 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
