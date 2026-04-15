"""BY19Code 数据库 CRUD 操作【T03】

三张表的操作函数，全部接收显式 conn 参数（便于测试注入内存数据库）：

  projects    → create_project / get_project_by_path /
                get_or_create_project / update_last_modified
  change_logs → add_change_log / get_recent_logs
  token_usage → add_token_usage / get_usage_summary / get_total_cost

日志记录时机（由上层模块调用）：
  write_file / edit_file 成功 → add_change_log(change_type="file_create/file_edit")
  run_command 成功           → add_change_log(change_type="command")
  git_commit / git_push      → add_change_log(change_type="git")
  LLM chat() 完成            → add_token_usage(...)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _normalize_path(path: str | Path) -> str:
    """将路径统一转为正斜杠字符串（数据库存储规范：Path.as_posix()）"""
    return Path(path).as_posix()


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    """将 sqlite3.Row 转换为普通 dict"""
    return {key: row[key] for key in row.keys()}


# ---------------------------------------------------------------------------
# projects 表
# ---------------------------------------------------------------------------


async def create_project(
    conn: aiosqlite.Connection,
    name: str,
    path: str | Path,
) -> int:
    """
    新建项目记录，返回自增主键 id。
    path 统一转为正斜杠存储；路径重复时抛出 aiosqlite.IntegrityError。
    """
    posix_path = _normalize_path(path)
    try:
        cursor = await conn.execute(
            "INSERT INTO projects (name, path) VALUES (?, ?)",
            (name, posix_path),
        )
        await conn.commit()
        row_id: int = cursor.lastrowid  # type: ignore[assignment]
        logger.debug("[数据库] 创建项目: id=%d name=%s path=%s", row_id, name, posix_path)
        return row_id
    except aiosqlite.IntegrityError:
        logger.warning("[数据库] 项目路径已存在: %s", posix_path)
        raise


async def get_project_by_path(
    conn: aiosqlite.Connection,
    path: str | Path,
) -> aiosqlite.Row | None:
    """按路径查找项目行，未找到返回 None。path 自动转为正斜杠后匹配。"""
    posix_path = _normalize_path(path)
    cursor = await conn.execute(
        "SELECT * FROM projects WHERE path = ?",
        (posix_path,),
    )
    return await cursor.fetchone()


async def get_or_create_project(
    conn: aiosqlite.Connection,
    name: str,
    path: str | Path,
) -> int:
    """
    按路径查找项目；若不存在则以 name 新建。返回 project id。
    适用于程序启动时"注册当前工作目录"场景。
    """
    row = await get_project_by_path(conn, path)
    if row is not None:
        return int(row["id"])
    return await create_project(conn, name, path)


async def update_last_modified(
    conn: aiosqlite.Connection,
    project_id: int,
) -> None:
    """将指定项目的 last_modified 更新为当前时间（CURRENT_TIMESTAMP）"""
    await conn.execute(
        "UPDATE projects SET last_modified = CURRENT_TIMESTAMP WHERE id = ?",
        (project_id,),
    )
    await conn.commit()
    logger.debug("[数据库] 更新 last_modified: project_id=%d", project_id)


# ---------------------------------------------------------------------------
# change_logs 表
# ---------------------------------------------------------------------------


async def add_change_log(
    conn: aiosqlite.Connection,
    project_id: int,
    change_type: str,
    file_path: str | Path | None = None,
    content_md: str | None = None,
    ai_summary: str | None = None,
) -> int:
    """
    追加一条修改日志，返回新行 id。

    参数
    ----
    change_type : "file_create" / "file_edit" / "file_delete" / "command" / "git"
    file_path   : 受影响的文件路径（自动转正斜杠）；命令/Git 操作可为 None。
    content_md  : Markdown 格式的修改内容或命令输出。
    ai_summary  : AI 生成的修改摘要（可选）。
    """
    posix_file: str | None = (
        _normalize_path(file_path) if file_path is not None else None
    )
    cursor = await conn.execute(
        """
        INSERT INTO change_logs
            (project_id, change_type, file_path, content_md, ai_summary)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, change_type, posix_file, content_md, ai_summary),
    )
    await conn.commit()
    row_id: int = cursor.lastrowid  # type: ignore[assignment]
    logger.debug(
        "[数据库] 记录变更: id=%d type=%s project=%d",
        row_id, change_type, project_id,
    )
    return row_id


async def get_recent_logs(
    conn: aiosqlite.Connection,
    project_id: int,
    limit: int = 20,
) -> list[aiosqlite.Row]:
    """
    返回指定项目最近 N 条修改日志（按 timestamp 倒序）。

    参数
    ----
    limit : 最多返回的条数，默认 20（PRD §4.3 规定）。
    """
    cursor = await conn.execute(
        """
        SELECT * FROM change_logs
        WHERE project_id = ?
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
        """,
        (project_id, limit),
    )
    return await cursor.fetchall()


# ---------------------------------------------------------------------------
# token_usage 表
# ---------------------------------------------------------------------------


async def add_token_usage(
    conn: aiosqlite.Connection,
    provider_name: str,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    project_id: int | None = None,
) -> int:
    """
    记录一次 LLM 调用的 token 用量，返回新行 id。
    total_tokens 自动计算为 input_tokens + output_tokens。

    参数
    ----
    cost_usd    : 本次调用费用（美元），计算公式见 PRD §7：
                  (input/1000) * cost_1k_in + (output/1000) * cost_1k_out
    project_id  : 关联项目；跨项目统计时可为 None。
    """
    total_tokens = input_tokens + output_tokens
    cursor = await conn.execute(
        """
        INSERT INTO token_usage
            (project_id, provider_name, model_name,
             input_tokens, output_tokens, total_tokens, cost_usd)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id, provider_name, model_name,
            input_tokens, output_tokens, total_tokens, cost_usd,
        ),
    )
    await conn.commit()
    row_id: int = cursor.lastrowid  # type: ignore[assignment]
    logger.debug(
        "[数据库] 记录 token: id=%d provider=%s tokens=%d cost=$%.6f",
        row_id, provider_name, total_tokens, cost_usd,
    )
    return row_id


async def get_usage_summary(
    conn: aiosqlite.Connection,
    project_id: int | None = None,
) -> dict[str, Any]:
    """
    返回 token 用量汇总字典。

    project_id 为 None 时统计全部项目；否则只统计指定项目。

    返回结构
    --------
    {
        "total_tokens":   int,
        "total_cost_usd": float,
        "by_provider": [
            {
                "provider_name": str,
                "model_name":    str,
                "total_input":   int,
                "total_output":  int,
                "total_tokens":  int,
                "total_cost_usd": float,
                "call_count":    int,
            },
            ...
        ]
    }
    """
    if project_id is not None:
        where_clause = "WHERE project_id = ?"
        params: tuple[Any, ...] = (project_id,)
    else:
        where_clause = ""
        params = ()

    # 全局总计
    cur_total = await conn.execute(
        f"SELECT SUM(total_tokens), SUM(cost_usd) FROM token_usage {where_clause}",
        params,
    )
    total_row = await cur_total.fetchone()
    total_tokens: int = int(total_row[0] or 0)
    total_cost: float = float(total_row[1] or 0.0)

    # 按 provider + model 分组
    cur_group = await conn.execute(
        f"""
        SELECT
            provider_name,
            model_name,
            SUM(input_tokens)  AS total_input,
            SUM(output_tokens) AS total_output,
            SUM(total_tokens)  AS total_tokens,
            SUM(cost_usd)      AS total_cost_usd,
            COUNT(*)           AS call_count
        FROM token_usage
        {where_clause}
        GROUP BY provider_name, model_name
        ORDER BY total_cost_usd DESC
        """,
        params,
    )
    rows = await cur_group.fetchall()

    return {
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "by_provider": [_row_to_dict(r) for r in rows],
    }


async def get_total_cost(conn: aiosqlite.Connection) -> float:
    """返回所有项目、所有 Provider 的 LLM 调用累计总费用（美元）"""
    cursor = await conn.execute("SELECT SUM(cost_usd) FROM token_usage")
    row = await cursor.fetchone()
    return float(row[0] or 0.0)
