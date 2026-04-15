"""BY19Code 数据库初始化与连接管理【T03】

公开接口：
  init_db(db_path)  → 展开路径 / 建目录 / 建表 / 设置单例连接
  get_db()          → 返回单例连接（必须先调用 init_db）
  close_db()        → 关闭并重置单例连接
  _create_tables()  → 供测试直接调用
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 模块级单例连接
# ---------------------------------------------------------------------------

_db: aiosqlite.Connection | None = None

# ---------------------------------------------------------------------------
# DDL：严格按 PRD §4.2 定义
# ---------------------------------------------------------------------------

_DDL_PROJECTS = """
CREATE TABLE IF NOT EXISTS projects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    path          TEXT    NOT NULL UNIQUE,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

_DDL_CHANGE_LOGS = """
CREATE TABLE IF NOT EXISTS change_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER  NOT NULL,
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
    change_type TEXT     NOT NULL,
    file_path   TEXT,
    content_md  TEXT,
    ai_summary  TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
"""

_DDL_TOKEN_USAGE = """
CREATE TABLE IF NOT EXISTS token_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER,
    timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP,
    provider_name TEXT     NOT NULL,
    model_name    TEXT     NOT NULL,
    input_tokens  INTEGER  NOT NULL,
    output_tokens INTEGER  NOT NULL,
    total_tokens  INTEGER  NOT NULL,
    cost_usd      REAL     NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
"""

# PRD 指定的索引
_DDL_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_token_timestamp ON token_usage(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_token_provider  ON token_usage(provider_name)",
]


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


async def _create_tables(conn: aiosqlite.Connection) -> None:
    """在指定连接上创建所有表与索引（幂等：IF NOT EXISTS）"""
    await conn.execute(_DDL_PROJECTS)
    await conn.execute(_DDL_CHANGE_LOGS)
    await conn.execute(_DDL_TOKEN_USAGE)
    for sql in _DDL_INDEXES:
        await conn.execute(sql)
    await conn.commit()
    logger.debug("[数据库] 表结构已就绪")


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------


async def init_db(db_path: Path | str) -> aiosqlite.Connection:
    """
    初始化数据库，返回并设置全局单例连接。

    步骤：
    1. 展开 %USERPROFILE% / ~ 路径变量
    2. 自动创建父目录（如 %USERPROFILE%\\.by19code\\）
    3. 打开 aiosqlite 连接，启用 WAL 模式和外键约束
    4. 创建所有表与索引
    5. 设置全局单例 _db 并返回

    参数
    ----
    db_path : 数据库文件路径，支持 %USERPROFILE% 和 ~ 展开。

    返回
    ----
    aiosqlite.Connection : 已初始化的数据库连接。
    """
    global _db

    # 路径展开与规范化
    expanded = os.path.expandvars(str(db_path))
    resolved = Path(expanded).expanduser().resolve()

    # 自动建父目录
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("[数据库] 目录就绪: %s", resolved.parent)
    except OSError as exc:
        logger.error("[数据库] 创建目录失败 %s: %s", resolved.parent, exc)
        raise

    # 打开连接
    try:
        conn = await aiosqlite.connect(resolved)
        conn.row_factory = aiosqlite.Row
        # WAL 模式：并发读性能更好，写操作不阻塞读
        await conn.execute("PRAGMA journal_mode=WAL")
        # 强制外键约束
        await conn.execute("PRAGMA foreign_keys=ON")
        await _create_tables(conn)
        _db = conn
        logger.info("[数据库] 已初始化: %s", resolved)
        return conn
    except Exception as exc:
        logger.error("[数据库] 初始化失败: %s", exc)
        raise


async def get_db() -> aiosqlite.Connection:
    """
    返回全局单例数据库连接。

    异常
    ----
    RuntimeError : 若 init_db() 尚未调用则抛出。
    """
    if _db is None:
        raise RuntimeError("[数据库] 未初始化，请先调用 init_db()")
    return _db


async def close_db() -> None:
    """
    关闭全局单例连接并将其重置为 None。
    重复调用是安全的（空操作）。
    """
    global _db
    if _db is not None:
        try:
            await _db.close()
            logger.info("[数据库] 连接已关闭")
        except Exception as exc:
            logger.warning("[数据库] 关闭时出错: %s", exc)
        finally:
            _db = None
