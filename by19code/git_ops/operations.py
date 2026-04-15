"""BY19Code Git 操作模块【T14】

提供安全的 Git 命令封装，包括：
1. git_commit - 提交更改
2. git_diff - 查看差异
3. git_log - 查看提交历史
4. git_status - 查看仓库状态
5. git_create_branch - 创建分支

Windows 关键点
--------------
- subprocess 调用 git 时设置 encoding="utf-8"
- 设置环境变量 LANG=C.UTF-8 确保 git 输出 UTF-8
- git commit -m 的消息如果含中文，在 Windows 上 cmd.exe 默认支持
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitOperationError(Exception):
    """Git 操作异常基类"""
    pass


class GitNotFoundError(GitOperationError):
    """Git 未安装或不在 PATH 中"""
    pass


class GitRepositoryError(GitOperationError):
    """不是有效的 Git 仓库"""
    pass


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _run_git_command(
    args: list[str],
    cwd: str | Path,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """执行 Git 命令。

    参数
    ----
    args  : Git 命令参数列表（不包含 'git'）
    cwd   : 工作目录
    check : 是否检查返回码（True 时非零返回码会抛出异常）

    返回
    ----
    subprocess.CompletedProcess : 命令执行结果

    异常
    ----
    GitNotFoundError      : Git 未安装
    GitRepositoryError    : 不是有效的 Git 仓库
    GitOperationError     : 其他 Git 操作错误
    """
    try:
        # 构造完整命令
        cmd = ["git"] + args

        # 设置环境变量，确保 UTF-8 输出
        env = os.environ.copy()
        env["LANG"] = "C.UTF-8"
        env["LC_ALL"] = "C.UTF-8"

        # 执行命令
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            encoding="utf-8",
            env=env,
            check=False,  # 手动检查返回码
        )

        # 检查返回码
        if check and result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()

            # 判断错误类型
            if "not a git repository" in error_msg.lower():
                raise GitRepositoryError(f"不是有效的 Git 仓库: {cwd}")
            else:
                raise GitOperationError(f"Git 命令执行失败: {error_msg}")

        logger.debug("[Git] 命令执行: git %s (返回码: %d)", " ".join(args), result.returncode)
        return result

    except FileNotFoundError:
        raise GitNotFoundError("Git 未安装或不在 PATH 中，请先安装 Git")
    except Exception as e:
        if isinstance(e, (GitNotFoundError, GitRepositoryError, GitOperationError)):
            raise
        raise GitOperationError(f"执行 Git 命令时发生异常: {e}") from e


def _validate_git_repo(project_root: str | Path) -> None:
    """验证是否是有效的 Git 仓库。

    参数
    ----
    project_root : 项目根目录

    异常
    ----
    GitRepositoryError : 不是有效的 Git 仓库
    """
    git_dir = Path(project_root) / ".git"
    if not git_dir.exists():
        raise GitRepositoryError(f"不是有效的 Git 仓库: {project_root}")


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def git_commit(message: str, project_root: str | Path) -> str:
    """提交当前更改到 Git 仓库。

    参数
    ----
    message      : 提交信息
    project_root : 项目根目录

    返回
    ----
    str : 成功消息

    异常
    ----
    GitNotFoundError   : Git 未安装
    GitRepositoryError : 不是有效的 Git 仓库
    GitOperationError  : Git 操作失败
    """
    try:
        # 验证 Git 仓库
        _validate_git_repo(project_root)

        # 检查是否有更改
        status_result = _run_git_command(["status", "--porcelain"], project_root)
        if not status_result.stdout.strip():
            return "[Git] 没有需要提交的更改"

        # 添加所有更改
        _run_git_command(["add", "-A"], project_root)
        logger.info("[Git] 已添加所有更改")

        # 提交更改
        _run_git_command(["commit", "-m", message], project_root)
        logger.info("[Git] 提交成功: %s", message)

        return f"[Git] 提交成功: {message}"

    except (GitNotFoundError, GitRepositoryError, GitOperationError):
        raise
    except Exception as e:
        raise GitOperationError(f"提交失败: {e}") from e


def git_diff(project_root: str | Path) -> str:
    """查看当前工作区的修改内容。

    参数
    ----
    project_root : 项目根目录

    返回
    ----
    str : diff 输出

    异常
    ----
    GitNotFoundError   : Git 未安装
    GitRepositoryError : 不是有效的 Git 仓库
    GitOperationError  : Git 操作失败
    """
    try:
        # 验证 Git 仓库
        _validate_git_repo(project_root)

        # 获取 diff
        result = _run_git_command(["diff", "HEAD"], project_root, check=False)

        if not result.stdout.strip():
            return "[Git] 没有未提交的更改"

        logger.info("[Git] 获取 diff 成功")
        return f"[Git] 当前更改:\n\n{result.stdout}"

    except (GitNotFoundError, GitRepositoryError, GitOperationError):
        raise
    except Exception as e:
        raise GitOperationError(f"获取 diff 失败: {e}") from e


def git_log(count: int, project_root: str | Path) -> str:
    """查看 Git 提交历史。

    参数
    ----
    count        : 显示的提交数量
    project_root : 项目根目录

    返回
    ----
    str : log 输出

    异常
    ----
    GitNotFoundError   : Git 未安装
    GitRepositoryError : 不是有效的 Git 仓库
    GitOperationError  : Git 操作失败
    """
    try:
        # 验证 Git 仓库
        _validate_git_repo(project_root)

        # 获取 log（格式化输出）
        result = _run_git_command(
            ["log", f"-{count}", "--pretty=format:%h - %s (%an, %ar)"],
            project_root,
            check=False,
        )

        if not result.stdout.strip():
            return "[Git] 没有提交历史"

        logger.info("[Git] 获取 log 成功 (显示 %d 条)", count)
        return f"[Git] 最近 {count} 次提交:\n\n{result.stdout}"

    except (GitNotFoundError, GitRepositoryError, GitOperationError):
        raise
    except Exception as e:
        raise GitOperationError(f"获取 log 失败: {e}") from e


def git_status(project_root: str | Path) -> str:
    """查看 Git 仓库状态。

    参数
    ----
    project_root : 项目根目录

    返回
    ----
    str : status 输出

    异常
    ----
    GitNotFoundError   : Git 未安装
    GitRepositoryError : 不是有效的 Git 仓库
    GitOperationError  : Git 操作失败
    """
    try:
        # 验证 Git 仓库
        _validate_git_repo(project_root)

        # 获取 status
        result = _run_git_command(["status"], project_root)

        logger.info("[Git] 获取 status 成功")
        return f"[Git] 仓库状态:\n\n{result.stdout}"

    except (GitNotFoundError, GitRepositoryError, GitOperationError):
        raise
    except Exception as e:
        raise GitOperationError(f"获取 status 失败: {e}") from e


def git_create_branch(branch_name: str, project_root: str | Path) -> str:
    """创建新的 Git 分支。

    参数
    ----
    branch_name  : 分支名称
    project_root : 项目根目录

    返回
    ----
    str : 成功消息

    异常
    ----
    GitNotFoundError   : Git 未安装
    GitRepositoryError : 不是有效的 Git 仓库
    GitOperationError  : Git 操作失败
    """
    try:
        # 验证 Git 仓库
        _validate_git_repo(project_root)

        # 创建并切换到新分支
        _run_git_command(["checkout", "-b", branch_name], project_root)

        logger.info("[Git] 创建并切换到分支: %s", branch_name)
        return f"[Git] 已创建并切换到分支: {branch_name}"

    except (GitNotFoundError, GitRepositoryError, GitOperationError):
        raise
    except Exception as e:
        raise GitOperationError(f"创建分支失败: {e}") from e
