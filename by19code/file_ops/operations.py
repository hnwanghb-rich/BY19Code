"""BY19Code 文件操作模块【T08】

提供安全的文件读写、编辑、目录列表、内容搜索等功能。

安全机制
--------
- 所有路径操作必须在 project_root 范围内（沙箱限制）
- 使用 Path.resolve() 处理相对路径和符号链接
- Windows 平台：处理盘符大小写差异
- 防止路径穿越攻击（../ 和绝对路径）

编码规范
--------
- 所有文件读写使用 UTF-8 编码
- 换行符统一使用 \n（跨平台兼容）
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# 忽略的目录列表（用于 list_directory 和 search_files）
IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".pytest_cache"}

# 忽略的文件扩展名（用于 search_files）
IGNORED_EXTENSIONS = {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".db", ".sqlite"}


class FileOperationError(Exception):
    """文件操作异常基类"""
    pass


class PathSecurityError(FileOperationError):
    """路径安全检查失败异常"""
    pass


class FileNotFoundError(FileOperationError):
    """文件不存在异常"""
    pass


class FileReadError(FileOperationError):
    """文件读取失败异常"""
    pass


class FileWriteError(FileOperationError):
    """文件写入失败异常"""
    pass


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _validate_path(path: str | Path, project_root: str | Path) -> Path:
    """验证路径是否在 project_root 范围内。

    参数
    ----
    path         : 待验证的路径（相对或绝对）
    project_root : 项目根目录（必须是绝对路径）

    返回
    ----
    Path : 解析后的绝对路径

    异常
    ----
    PathSecurityError : 路径不在 project_root 范围内

    安全机制
    --------
    1. 相对路径基于 project_root 解析
    2. 使用 Path.resolve() 解析符号链接、.. 等
    3. Windows 平台：resolve() 会统一盘符大小写
    4. 检查解析后的路径是否以 project_root 开头
    """
    try:
        # 转换为 Path 对象
        target_path = Path(str(path))
        root_path = Path(project_root).resolve()

        # 自动修正：以 / 开头的伪绝对路径（如 /src/main.py）转为相对路径
        path_str = str(path)
        if path_str.startswith("/") and not Path(path_str).drive:
            target_path = Path(path_str.lstrip("/"))
            logger.warning("[文件操作] 自动修正路径: '%s' -> '%s'", path_str, target_path)

        # 如果是相对路径，基于 project_root 解析
        if not target_path.is_absolute():
            target_path = root_path / target_path

        # 解析为绝对路径（处理 .., 符号链接等）
        resolved_target = target_path.resolve()

        # 检查是否在项目根目录范围内
        try:
            resolved_target.relative_to(root_path)
        except ValueError:
            raise PathSecurityError(
                f"路径 '{path}' 不在项目根目录 '{project_root}' 范围内"
            )

        logger.debug("[文件操作] 路径验证通过: %s", resolved_target)
        return resolved_target

    except PathSecurityError:
        raise
    except Exception as e:
        raise PathSecurityError(f"路径验证失败: {e}") from e


def _format_tree(
    path: Path,
    prefix: str = "",
    is_last: bool = True,
    current_depth: int = 0,
    max_depth: int = 2,
) -> List[str]:
    """递归生成树形目录结构。

    参数
    ----
    path          : 当前目录路径
    prefix        : 当前行的前缀（用于绘制树形结构）
    is_last       : 是否是同级最后一个
    current_depth : 当前递归深度
    max_depth     : 最大递归深度

    返回
    ----
    List[str] : 树形结构的文本行列表
    """
    lines: List[str] = []

    # 当前项的连接符
    connector = "└── " if is_last else "├── "

    # 添加当前项
    if current_depth == 0:
        lines.append(f"{path.name}/")
    else:
        lines.append(f"{prefix}{connector}{path.name}/")

    # 达到最大深度，停止递归
    if current_depth >= max_depth:
        return lines

    # 获取子项（排序：目录在前，文件在后）
    try:
        children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        lines.append(f"{prefix}    [权限不足]")
        return lines

    # 过滤忽略的目录
    children = [c for c in children if c.name not in IGNORED_DIRS]

    # 递归处理子项
    for i, child in enumerate(children):
        is_last_child = (i == len(children) - 1)

        if child.is_dir():
            # 递归处理子目录
            new_prefix = prefix + ("    " if is_last else "│   ")
            lines.extend(_format_tree(
                child,
                prefix=new_prefix,
                is_last=is_last_child,
                current_depth=current_depth + 1,
                max_depth=max_depth,
            ))
        else:
            # 添加文件
            file_connector = "└── " if is_last_child else "├── "
            file_prefix = prefix + ("    " if is_last else "│   ")
            lines.append(f"{file_prefix}{file_connector}{child.name}")

    return lines


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def read_file(path: str | Path, project_root: str | Path) -> str:
    """读取文件内容。

    参数
    ----
    path         : 文件路径（相对或绝对）
    project_root : 项目根目录

    返回
    ----
    str : 文件内容

    异常
    ----
    PathSecurityError : 路径不在项目范围内
    FileNotFoundError : 文件不存在
    FileReadError     : 文件读取失败
    """
    try:
        # 验证路径安全性
        file_path = _validate_path(path, project_root)

        # 检查文件是否存在
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if not file_path.is_file():
            raise FileReadError(f"路径不是文件: {file_path}")

        # 读取文件内容
        content = file_path.read_text(encoding="utf-8")
        logger.info("[文件操作] 读取文件: %s (%d 字符)", file_path, len(content))
        return content

    except (PathSecurityError, FileNotFoundError, FileReadError):
        raise
    except Exception as e:
        raise FileReadError(f"读取文件失败: {e}") from e


def write_file(path: str | Path, content: str, project_root: str | Path) -> str:
    """创建或覆盖写入文件。

    参数
    ----
    path         : 文件路径（相对或绝对）
    content      : 文件内容
    project_root : 项目根目录

    返回
    ----
    str : 成功消息

    异常
    ----
    PathSecurityError : 路径不在项目范围内
    FileWriteError    : 文件写入失败
    """
    try:
        # 验证路径安全性
        file_path = _validate_path(path, project_root)

        # 自动创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件（UTF-8 编码，换行符统一为 \n）
        file_path.write_text(content, encoding="utf-8", newline="\n")

        logger.info("[文件操作] 写入文件: %s (%d 字符)", file_path, len(content))
        return f"文件写入成功: {file_path.name} ({len(content)} 字符)"

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileWriteError(f"写入文件失败: {e}") from e


def edit_file(
    path: str | Path,
    old_text: str,
    new_text: str,
    project_root: str | Path,
) -> str:
    """查找并替换文件中的文本。

    参数
    ----
    path         : 文件路径（相对或绝对）
    old_text     : 要替换的文本
    new_text     : 替换后的文本
    project_root : 项目根目录

    返回
    ----
    str : 成功消息（包含替换次数）

    异常
    ----
    PathSecurityError : 路径不在项目范围内
    FileNotFoundError : 文件不存在
    FileReadError     : 文件读取失败
    FileWriteError    : 文件写入失败
    """
    try:
        # 读取原文件内容
        content = read_file(path, project_root)

        # 检查是否存在要替换的文本
        if old_text not in content:
            return f"未找到要替换的文本: {old_text[:50]}..."

        # 执行替换
        new_content = content.replace(old_text, new_text)
        count = content.count(old_text)

        # 写回文件
        file_path = _validate_path(path, project_root)
        file_path.write_text(new_content, encoding="utf-8", newline="\n")

        logger.info("[文件操作] 编辑文件: %s (替换 %d 处)", file_path, count)
        return f"文件编辑成功: {file_path.name} (替换 {count} 处)"

    except (PathSecurityError, FileNotFoundError, FileReadError):
        raise
    except Exception as e:
        raise FileWriteError(f"编辑文件失败: {e}") from e


def list_directory(
    path: str | Path,
    project_root: str | Path,
    depth: int = 2,
) -> str:
    """列出目录结构（树形格式）。

    参数
    ----
    path         : 目录路径（相对或绝对）
    project_root : 项目根目录
    depth        : 递归深度（默认 2）

    返回
    ----
    str : 树形目录结构文本

    异常
    ----
    PathSecurityError : 路径不在项目范围内
    FileNotFoundError : 目录不存在
    """
    try:
        # 验证路径安全性
        dir_path = _validate_path(path, project_root)

        # 检查目录是否存在
        if not dir_path.exists():
            raise FileNotFoundError(f"目录不存在: {dir_path}")

        if not dir_path.is_dir():
            raise FileOperationError(f"路径不是目录: {dir_path}")

        # 生成树形结构
        lines = _format_tree(dir_path, max_depth=depth)
        result = "\n".join(lines)

        logger.info("[文件操作] 列出目录: %s (深度 %d)", dir_path, depth)
        return result

    except (PathSecurityError, FileNotFoundError):
        raise
    except Exception as e:
        raise FileOperationError(f"列出目录失败: {e}") from e


def search_files(
    pattern: str,
    path: str | Path,
    project_root: str | Path,
) -> str:
    """在目录中搜索包含指定文本的文件。

    参数
    ----
    pattern      : 搜索模式（支持正则表达式）
    path         : 搜索起始目录（相对或绝对）
    project_root : 项目根目录

    返回
    ----
    str : 搜索结果（文件路径 + 匹配行）

    异常
    ----
    PathSecurityError : 路径不在项目范围内
    FileNotFoundError : 目录不存在
    """
    try:
        # 验证路径安全性
        search_path = _validate_path(path, project_root)

        # 检查目录是否存在
        if not search_path.exists():
            raise FileNotFoundError(f"目录不存在: {search_path}")

        if not search_path.is_dir():
            raise FileOperationError(f"路径不是目录: {search_path}")

        # 编译正则表达式
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise FileOperationError(f"无效的正则表达式: {e}") from e

        # 搜索文件
        results: List[str] = []
        file_count = 0
        match_count = 0

        for file_path in search_path.rglob("*"):
            # 跳过目录
            if not file_path.is_file():
                continue

            # 跳过忽略的目录
            if any(ignored in file_path.parts for ignored in IGNORED_DIRS):
                continue

            # 跳过忽略的文件扩展名
            if file_path.suffix in IGNORED_EXTENSIONS:
                continue

            # 读取文件内容并搜索
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()

                matched_lines: List[str] = []
                for line_num, line in enumerate(lines, start=1):
                    if regex.search(line):
                        matched_lines.append(f"  {line_num}: {line.strip()}")
                        match_count += 1

                if matched_lines:
                    relative_path = file_path.relative_to(search_path)
                    results.append(f"\n{relative_path}:")
                    results.extend(matched_lines)
                    file_count += 1

            except (UnicodeDecodeError, PermissionError):
                # 跳过无法读取的文件
                continue

        # 格式化结果
        if not results:
            return f"未找到匹配 '{pattern}' 的文件"

        header = f"搜索结果: 在 {file_count} 个文件中找到 {match_count} 处匹配\n"
        return header + "\n".join(results)

    except (PathSecurityError, FileNotFoundError):
        raise
    except Exception as e:
        raise FileOperationError(f"搜索文件失败: {e}") from e
