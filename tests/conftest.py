"""pytest 全局配置

限制 anyio 后端为 asyncio（aiosqlite 不兼容 trio）。
"""
import pytest


@pytest.fixture(params=["asyncio"])
def anyio_backend() -> str:
    """仅使用 asyncio 后端运行异步测试"""
    return "asyncio"
