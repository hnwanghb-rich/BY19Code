"""by19code.db 模块单元测试【T03】

测试分组：
  TestNormalizePath    - _normalize_path() 路径归一化
  TestCreateTables     - 建表幂等性、列名和外键约束
  TestInitDb           - init_db() 文件创建、目录自动建立、单例设置
  TestGetDb / CloseDb  - 单例生命周期
  TestProjects         - create / get_by_path / get_or_create / update_modified
  TestChangeLogs       - add / get_recent / limit / 路径存储
  TestTokenUsage       - add / get_summary / get_total_cost / 多 provider
  TestEdgeCases        - 空表统计 / 外键约束 / 重复路径

全部测试使用 :memory: 内存数据库，与磁盘状态无关。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite
import pytest

from by19code.db.database import _create_tables, close_db, get_db, init_db
from by19code.db.models import (
    _normalize_path,
    add_change_log,
    add_token_usage,
    create_project,
    get_or_create_project,
    get_project_by_path,
    get_recent_logs,
    get_total_cost,
    get_usage_summary,
    update_last_modified,
)

# Python 3.12 目标环境的 Windows 事件循环策略
# Python 3.14+ 已弃用 set_event_loop_policy，条件防护
if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass  # Python 3.16+ 移除后静默跳过

# 所有 async 测试由 anyio 驱动
pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------


@pytest.fixture
async def db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """每个测试使用独立的内存数据库（外键约束开启）"""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    await _create_tables(conn)
    yield conn
    await conn.close()


@pytest.fixture
async def project_id(db: aiosqlite.Connection) -> int:
    """在 db 中预建一个测试项目，返回其 id"""
    return await create_project(db, "测试项目", "D:/projects/test-app")


# ---------------------------------------------------------------------------
# 1. 路径归一化
# ---------------------------------------------------------------------------


class TestNormalizePath:
    def test_windows_backslash(self) -> None:
        """Windows 反斜杠转为正斜杠"""
        assert _normalize_path(r"D:\projects\app") == "D:/projects/app"

    def test_already_posix(self) -> None:
        assert _normalize_path("D:/projects/app") == "D:/projects/app"

    def test_path_object(self) -> None:
        p = Path(r"D:\projects\app\main.py")
        assert "/" in _normalize_path(p)
        assert "\\" not in _normalize_path(p)

    def test_nested_dirs(self) -> None:
        result = _normalize_path(r"C:\Users\admin\by19code\config.json")
        assert result == "C:/Users/admin/by19code/config.json"


# ---------------------------------------------------------------------------
# 2. 建表与 DDL 幂等性
# ---------------------------------------------------------------------------


class TestCreateTables:
    async def test_tables_exist(self, db: aiosqlite.Connection) -> None:
        """三张表全部存在"""
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert "projects" in tables
        assert "change_logs" in tables
        assert "token_usage" in tables

    async def test_indexes_exist(self, db: aiosqlite.Connection) -> None:
        """两个 token_usage 索引存在"""
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        assert "idx_token_timestamp" in indexes
        assert "idx_token_provider" in indexes

    async def test_idempotent_second_call(self, db: aiosqlite.Connection) -> None:
        """重复调用 _create_tables 不报错（IF NOT EXISTS），且用户表数量不变。
        注：SQLite AUTOINCREMENT 会生成内部 sqlite_sequence 表，需排除。"""
        await _create_tables(db)  # 第二次调用
        cursor = await db.execute(
            # 排除 sqlite_sequence 等内部表
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        rows = await cursor.fetchall()
        assert len(rows) == 3

    async def test_projects_columns(self, db: aiosqlite.Connection) -> None:
        """projects 表包含 PRD 定义的全部列"""
        cursor = await db.execute("PRAGMA table_info(projects)")
        cols = {row["name"] for row in await cursor.fetchall()}
        assert cols >= {"id", "name", "path", "created_at", "last_modified"}

    async def test_change_logs_columns(self, db: aiosqlite.Connection) -> None:
        """change_logs 表列完整"""
        cursor = await db.execute("PRAGMA table_info(change_logs)")
        cols = {row["name"] for row in await cursor.fetchall()}
        assert cols >= {
            "id", "project_id", "timestamp",
            "change_type", "file_path", "content_md", "ai_summary",
        }

    async def test_token_usage_columns(self, db: aiosqlite.Connection) -> None:
        """token_usage 表列完整"""
        cursor = await db.execute("PRAGMA table_info(token_usage)")
        cols = {row["name"] for row in await cursor.fetchall()}
        assert cols >= {
            "id", "project_id", "timestamp",
            "provider_name", "model_name",
            "input_tokens", "output_tokens", "total_tokens", "cost_usd",
        }


# ---------------------------------------------------------------------------
# 3. init_db() 文件创建与单例
# ---------------------------------------------------------------------------


class TestInitDb:
    async def test_creates_db_file(self, tmp_path: Path) -> None:
        """init_db 在指定路径创建 .db 文件"""
        db_path = tmp_path / "sub" / "test.db"
        conn = await init_db(db_path)
        try:
            assert db_path.exists()
        finally:
            await conn.close()
            await close_db()

    async def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """init_db 自动创建多级父目录"""
        db_path = tmp_path / "a" / "b" / "c" / "by19code.db"
        conn = await init_db(db_path)
        try:
            assert db_path.parent.exists()
        finally:
            await conn.close()
            await close_db()

    async def test_sets_singleton(self, tmp_path: Path) -> None:
        """init_db 后 get_db() 返回同一连接对象"""
        db_path = tmp_path / "test.db"
        conn = await init_db(db_path)
        try:
            singleton = await get_db()
            assert singleton is conn
        finally:
            await close_db()

    async def test_tables_created_in_file_db(self, tmp_path: Path) -> None:
        """文件数据库中三张表都存在"""
        db_path = tmp_path / "test.db"
        conn = await init_db(db_path)
        try:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in await cursor.fetchall()}
            assert {"projects", "change_logs", "token_usage"} <= tables
        finally:
            await close_db()


# ---------------------------------------------------------------------------
# 4. get_db / close_db 单例生命周期
# ---------------------------------------------------------------------------


class TestSingleton:
    async def test_get_db_raises_before_init(self) -> None:
        """未 init_db 时调用 get_db 抛出 RuntimeError"""
        # 确保没有残留连接
        await close_db()
        with pytest.raises(RuntimeError, match="未初始化"):
            await get_db()

    async def test_close_db_resets_singleton(self, tmp_path: Path) -> None:
        """close_db 后 get_db 再次抛出 RuntimeError"""
        conn = await init_db(tmp_path / "test.db")
        await close_db()
        with pytest.raises(RuntimeError):
            await get_db()

    async def test_close_db_safe_when_none(self) -> None:
        """连接为 None 时 close_db 是空操作，不抛出"""
        await close_db()
        await close_db()  # 第二次也安全


# ---------------------------------------------------------------------------
# 5. projects 表 CRUD
# ---------------------------------------------------------------------------


class TestProjects:
    async def test_create_returns_id(self, db: aiosqlite.Connection) -> None:
        pid = await create_project(db, "MyApp", "D:/projects/my-app")
        assert isinstance(pid, int)
        assert pid > 0

    async def test_create_multiple_increments_id(
        self, db: aiosqlite.Connection
    ) -> None:
        id1 = await create_project(db, "App1", "D:/p1")
        id2 = await create_project(db, "App2", "D:/p2")
        assert id2 > id1

    async def test_create_normalizes_path(self, db: aiosqlite.Connection) -> None:
        """Windows 路径存入时自动转为正斜杠"""
        await create_project(db, "App", r"D:\projects\app")
        row = await get_project_by_path(db, r"D:\projects\app")
        assert row is not None
        assert row["path"] == "D:/projects/app"

    async def test_duplicate_path_raises(self, db: aiosqlite.Connection) -> None:
        """路径 UNIQUE 约束：重复插入抛出 IntegrityError"""
        await create_project(db, "App", "D:/p")
        with pytest.raises(aiosqlite.IntegrityError):
            await create_project(db, "App2", "D:/p")

    async def test_get_by_path_found(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        row = await get_project_by_path(db, "D:/projects/test-app")
        assert row is not None
        assert row["id"] == project_id
        assert row["name"] == "测试项目"

    async def test_get_by_path_not_found(self, db: aiosqlite.Connection) -> None:
        row = await get_project_by_path(db, "D:/nonexistent")
        assert row is None

    async def test_get_by_path_normalizes_input(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """get_project_by_path 支持反斜杠输入"""
        row = await get_project_by_path(db, r"D:\projects\test-app")
        assert row is not None
        assert row["id"] == project_id

    async def test_get_or_create_creates_new(
        self, db: aiosqlite.Connection
    ) -> None:
        pid = await get_or_create_project(db, "NewApp", "D:/new")
        assert isinstance(pid, int)
        assert pid > 0

    async def test_get_or_create_returns_existing(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """已有项目时返回现有 id，不新建"""
        pid2 = await get_or_create_project(db, "任意名字", "D:/projects/test-app")
        assert pid2 == project_id

    async def test_update_last_modified(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """update_last_modified 执行后不抛出，数据库有更新"""
        await update_last_modified(db, project_id)
        row = await get_project_by_path(db, "D:/projects/test-app")
        assert row is not None
        # last_modified 不为空（具体值为当前时间，不做精确比较）
        assert row["last_modified"] is not None


# ---------------------------------------------------------------------------
# 6. change_logs 表 CRUD
# ---------------------------------------------------------------------------


class TestChangeLogs:
    async def test_add_returns_id(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        log_id = await add_change_log(
            db, project_id, "file_create", "D:/projects/test-app/main.py"
        )
        assert isinstance(log_id, int)
        assert log_id > 0

    async def test_add_file_path_normalized(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """file_path 存储时转为正斜杠"""
        await add_change_log(
            db, project_id, "file_edit", r"D:\projects\test-app\src\util.py"
        )
        rows = await get_recent_logs(db, project_id, limit=1)
        assert rows[0]["file_path"] == "D:/projects/test-app/src/util.py"

    async def test_add_without_file_path(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """命令/Git 日志 file_path 可为 None"""
        log_id = await add_change_log(db, project_id, "command")
        assert log_id > 0

    async def test_add_with_content_and_summary(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        await add_change_log(
            db, project_id, "file_create",
            content_md="```python\nprint('hello')\n```",
            ai_summary="新建 hello.py，输出 hello",
        )
        rows = await get_recent_logs(db, project_id, limit=1)
        assert "hello" in rows[0]["content_md"]
        assert rows[0]["ai_summary"] == "新建 hello.py，输出 hello"

    async def test_get_recent_logs_order(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """get_recent_logs 按时间倒序返回"""
        for change_type in ("file_create", "file_edit", "command"):
            await add_change_log(db, project_id, change_type)
        rows = await get_recent_logs(db, project_id)
        assert rows[0]["change_type"] == "command"
        assert rows[-1]["change_type"] == "file_create"

    async def test_get_recent_logs_limit(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """limit 参数有效"""
        for _ in range(10):
            await add_change_log(db, project_id, "file_edit")
        rows = await get_recent_logs(db, project_id, limit=3)
        assert len(rows) == 3

    async def test_get_recent_logs_empty(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        rows = await get_recent_logs(db, project_id)
        assert rows == []

    async def test_get_recent_logs_project_isolation(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """不同项目的日志互不干扰"""
        other_id = await create_project(db, "Other", "D:/other")
        await add_change_log(db, other_id, "git")
        rows = await get_recent_logs(db, project_id)
        # project_id 对应的项目无日志
        assert rows == []


# ---------------------------------------------------------------------------
# 7. token_usage 表 CRUD
# ---------------------------------------------------------------------------


class TestTokenUsage:
    async def test_add_returns_id(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        uid = await add_token_usage(
            db,
            provider_name="claude",
            model_name="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
            project_id=project_id,
        )
        assert isinstance(uid, int)
        assert uid > 0

    async def test_total_tokens_auto_calculated(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """total_tokens = input + output"""
        await add_token_usage(
            db, "claude", "claude-sonnet-4-6",
            input_tokens=1000, output_tokens=400, cost_usd=0.01,
            project_id=project_id,
        )
        cursor = await db.execute("SELECT total_tokens FROM token_usage")
        row = await cursor.fetchone()
        assert row["total_tokens"] == 1400

    async def test_add_without_project_id(self, db: aiosqlite.Connection) -> None:
        """project_id 可为 None（全局调用，不关联项目）"""
        uid = await add_token_usage(
            db, "deepseek", "deepseek-chat",
            input_tokens=500, output_tokens=200, cost_usd=0.001,
        )
        assert uid > 0

    async def test_get_total_cost_empty(self, db: aiosqlite.Connection) -> None:
        """空表时 get_total_cost 返回 0.0"""
        cost = await get_total_cost(db)
        assert cost == 0.0

    async def test_get_total_cost_sum(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        await add_token_usage(db, "claude", "m", 100, 50, 0.01, project_id)
        await add_token_usage(db, "deepseek", "m", 200, 80, 0.005, project_id)
        cost = await get_total_cost(db)
        assert abs(cost - 0.015) < 1e-9

    async def test_get_usage_summary_empty(self, db: aiosqlite.Connection) -> None:
        summary = await get_usage_summary(db)
        assert summary["total_tokens"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["by_provider"] == []

    async def test_get_usage_summary_all_projects(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        await add_token_usage(
            db, "claude", "claude-sonnet-4-6",
            input_tokens=1000, output_tokens=500, cost_usd=0.01,
            project_id=project_id,
        )
        summary = await get_usage_summary(db)
        assert summary["total_tokens"] == 1500
        assert abs(summary["total_cost_usd"] - 0.01) < 1e-9
        assert len(summary["by_provider"]) == 1
        assert summary["by_provider"][0]["provider_name"] == "claude"

    async def test_get_usage_summary_by_project(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """按 project_id 过滤统计"""
        other_id = await create_project(db, "Other", "D:/other2")
        await add_token_usage(
            db, "claude", "m", 1000, 500, 0.01, project_id=project_id
        )
        await add_token_usage(
            db, "deepseek", "m", 200, 80, 0.005, project_id=other_id
        )
        summary = await get_usage_summary(db, project_id=project_id)
        assert summary["total_tokens"] == 1500
        assert len(summary["by_provider"]) == 1
        assert summary["by_provider"][0]["provider_name"] == "claude"

    async def test_get_usage_summary_multiple_providers(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """多 provider 时 by_provider 按费用降序排列"""
        await add_token_usage(
            db, "deepseek", "deepseek-chat",
            input_tokens=100, output_tokens=50, cost_usd=0.001,
            project_id=project_id,
        )
        await add_token_usage(
            db, "claude", "claude-sonnet-4-6",
            input_tokens=1000, output_tokens=500, cost_usd=0.01,
            project_id=project_id,
        )
        summary = await get_usage_summary(db, project_id=project_id)
        assert len(summary["by_provider"]) == 2
        # 费用更高的 claude 排在第一
        assert summary["by_provider"][0]["provider_name"] == "claude"

    async def test_usage_summary_call_count(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """call_count 统计正确"""
        for _ in range(3):
            await add_token_usage(
                db, "claude", "claude-sonnet-4-6",
                input_tokens=100, output_tokens=50, cost_usd=0.001,
                project_id=project_id,
            )
        summary = await get_usage_summary(db, project_id=project_id)
        assert summary["by_provider"][0]["call_count"] == 3


# ---------------------------------------------------------------------------
# 8. 边界与完整性约束
# ---------------------------------------------------------------------------


class TestEdgeCases:
    async def test_foreign_key_change_logs(
        self, db: aiosqlite.Connection
    ) -> None:
        """change_logs.project_id 外键约束：非法 project_id 应拒绝"""
        with pytest.raises(aiosqlite.IntegrityError):
            await add_change_log(db, project_id=99999, change_type="file_create")

    async def test_change_log_all_types(
        self, db: aiosqlite.Connection, project_id: int
    ) -> None:
        """PRD 规定的五种 change_type 全部可插入"""
        for ct in ("file_create", "file_edit", "file_delete", "command", "git"):
            lid = await add_change_log(db, project_id, ct)
            assert lid > 0

    async def test_token_usage_null_project_id(
        self, db: aiosqlite.Connection
    ) -> None:
        """project_id 为 None 时不触发外键错误"""
        uid = await add_token_usage(
            db, "claude", "m", 100, 50, 0.001, project_id=None
        )
        assert uid > 0
