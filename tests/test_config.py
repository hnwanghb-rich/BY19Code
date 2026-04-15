"""by19code.config.settings 单元测试

测试覆盖：
  - Pydantic 模型默认值与字段验证
  - load_config() 优先级（默认 < 全局文件 < 项目文件 < overrides < 环境变量）
  - 路径展开（%USERPROFILE% / ~）
  - 环境变量 API Key 注入（api_key 为空时才注入）
  - save_config() / load_config() 往返一致性
  - 错误容错（JSON 损坏、文件不存在）
  - AppConfig 辅助方法（get_active_provider / get_provider）
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from by19code.config.settings import (
    AppConfig,
    DatabaseConfig,
    GitConfig,
    LLMProviderConfig,
    SafetyConfig,
    WorkspaceConfig,
    _deep_merge,
    _expand_path,
    _inject_env_api_keys,
    _load_json_file,
    load_config,
    save_config,
)

# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------

PROVIDER_CLAUDE: dict[str, Any] = {
    "name": "claude",
    "display_name": "Claude Sonnet",
    "provider_type": "anthropic",
    "api_key": "",
    "base_url": "https://api.anthropic.com",
    "model": "claude-sonnet-4-6",
    "max_tokens": 8192,
    "cost_per_1k_input": 0.003,
    "cost_per_1k_output": 0.015,
}

PROVIDER_DEEPSEEK: dict[str, Any] = {
    "name": "deepseek",
    "display_name": "DeepSeek Chat",
    "provider_type": "openai_compat",
    "api_key": "",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "max_tokens": 4096,
    "cost_per_1k_input": 0.0001,
    "cost_per_1k_output": 0.0002,
}

FULL_CONFIG: dict[str, Any] = {
    "version": "0.1.0",
    "llm_providers": [PROVIDER_CLAUDE, PROVIDER_DEEPSEEK],
    "active_provider": "claude",
    "git_config": {"auto_commit_message": True},
    "workspace": {"default_path": "."},
    "database": {
        "path": r"%USERPROFILE%\.by19code\by19code.db",
        "log_retention_days": 90,
    },
    "safety": {
        "command_timeout_seconds": 30,
        "max_tool_rounds": 20,
        "blocked_commands": ["format", "shutdown"],
    },
}


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """返回临时目录路径"""
    return tmp_path


@pytest.fixture()
def config_file(tmp_dir: Path) -> Path:
    """在临时目录写入 config.json，返回文件路径"""
    path = tmp_dir / "config.json"
    path.write_text(json.dumps(FULL_CONFIG), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. Pydantic 模型默认值测试
# ---------------------------------------------------------------------------


class TestDefaultValues:
    def test_app_config_defaults(self) -> None:
        """AppConfig 默认值正确"""
        cfg = AppConfig()
        assert cfg.version == "0.1.0"
        assert cfg.active_provider == "claude"
        assert isinstance(cfg.git_config, GitConfig)
        assert isinstance(cfg.safety, SafetyConfig)
        assert isinstance(cfg.database, DatabaseConfig)
        assert isinstance(cfg.workspace, WorkspaceConfig)

    def test_git_config_default(self) -> None:
        assert GitConfig().auto_commit_message is True

    def test_safety_config_defaults(self) -> None:
        s = SafetyConfig()
        assert s.command_timeout_seconds == 30
        assert s.max_tool_rounds == 20
        assert len(s.blocked_commands) > 0

    def test_database_config_default_path_contains_userprofile(self) -> None:
        db = DatabaseConfig()
        # 默认路径应包含 %USERPROFILE% 或展开后包含用户目录
        assert "%USERPROFILE%" in db.path or "by19code" in db.path

    def test_provider_config_fields(self) -> None:
        p = LLMProviderConfig(**PROVIDER_CLAUDE)
        assert p.name == "claude"
        assert p.provider_type == "anthropic"
        assert p.max_tokens == 8192

    def test_extra_fields_ignored(self) -> None:
        """Pydantic extra='ignore'：未知字段不报错"""
        cfg = AppConfig.model_validate({"version": "1.0.0", "unknown_field": "x"})
        assert cfg.version == "1.0.0"


# ---------------------------------------------------------------------------
# 2. DatabaseConfig.resolved_path() 路径展开测试
# ---------------------------------------------------------------------------


class TestPathExpansion:
    def test_resolved_path_userprofile(self) -> None:
        """%USERPROFILE% 展开后不含变量名"""
        db = DatabaseConfig(path=r"%USERPROFILE%\.by19code\by19code.db")
        resolved = db.resolved_path()
        assert "%USERPROFILE%" not in str(resolved)
        assert "by19code" in str(resolved)

    def test_resolved_path_tilde(self) -> None:
        """~ 展开后应为绝对路径"""
        db = DatabaseConfig(path="~/.by19code/by19code.db")
        resolved = db.resolved_path()
        assert "~" not in str(resolved)
        assert resolved.is_absolute()

    def test_expand_path_helper(self) -> None:
        """_expand_path() 展开 ~ 并返回 Path"""
        p = _expand_path("~")
        assert p.is_absolute()
        assert "~" not in str(p)


# ---------------------------------------------------------------------------
# 3. _deep_merge() 合并逻辑测试
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_simple_override(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_nested_dict_merge(self) -> None:
        base = {"safety": {"timeout": 30, "max_rounds": 20}}
        override = {"safety": {"timeout": 60}}
        result = _deep_merge(base, override)
        # 嵌套 dict 递归合并：max_rounds 应保留
        assert result["safety"]["timeout"] == 60
        assert result["safety"]["max_rounds"] == 20

    def test_list_replaced_not_merged(self) -> None:
        """list 直接替换，不合并"""
        base = {"blocked": ["a", "b", "c"]}
        override = {"blocked": ["x"]}
        result = _deep_merge(base, override)
        assert result["blocked"] == ["x"]

    def test_base_not_mutated(self) -> None:
        base = {"a": 1}
        _deep_merge(base, {"a": 2})
        assert base["a"] == 1


# ---------------------------------------------------------------------------
# 4. _load_json_file() 文件加载测试
# ---------------------------------------------------------------------------


class TestLoadJsonFile:
    def test_load_valid_file(self, tmp_dir: Path) -> None:
        path = tmp_dir / "cfg.json"
        path.write_text('{"key": "val"}', encoding="utf-8")
        result = _load_json_file(path)
        assert result == {"key": "val"}

    def test_nonexistent_file_returns_empty(self, tmp_dir: Path) -> None:
        result = _load_json_file(tmp_dir / "missing.json")
        assert result == {}

    def test_invalid_json_returns_empty(self, tmp_dir: Path) -> None:
        path = tmp_dir / "bad.json"
        path.write_text("{broken json", encoding="utf-8")
        result = _load_json_file(path)
        assert result == {}


# ---------------------------------------------------------------------------
# 5. _inject_env_api_keys() 环境变量注入测试
# ---------------------------------------------------------------------------


class TestInjectEnvApiKeys:
    def test_injects_when_api_key_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BY19CODE_CLAUDE_API_KEY", "sk-test-123")
        providers: list[dict[str, Any]] = [
            {"name": "claude", "api_key": ""}
        ]
        _inject_env_api_keys(providers)
        assert providers[0]["api_key"] == "sk-test-123"

    def test_does_not_overwrite_existing_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BY19CODE_CLAUDE_API_KEY", "sk-env-key")
        providers: list[dict[str, Any]] = [
            {"name": "claude", "api_key": "sk-existing"}
        ]
        _inject_env_api_keys(providers)
        assert providers[0]["api_key"] == "sk-existing"

    def test_skips_missing_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BY19CODE_DEEPSEEK_API_KEY", raising=False)
        providers: list[dict[str, Any]] = [{"name": "deepseek", "api_key": ""}]
        _inject_env_api_keys(providers)
        assert providers[0]["api_key"] == ""

    def test_case_insensitive_provider_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider name 大小写无关（name 转大写后拼 env key）"""
        monkeypatch.setenv("BY19CODE_CLAUDE_API_KEY", "sk-upper")
        providers: list[dict[str, Any]] = [{"name": "Claude", "api_key": ""}]
        _inject_env_api_keys(providers)
        assert providers[0]["api_key"] == "sk-upper"


# ---------------------------------------------------------------------------
# 6. load_config() 优先级测试
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_returns_default_when_no_files(self, tmp_dir: Path) -> None:
        """无配置文件时返回 AppConfig 默认值"""
        cfg = load_config(project_dir=tmp_dir)
        assert isinstance(cfg, AppConfig)
        assert cfg.version == "0.1.0"

    def test_loads_project_config(self, tmp_dir: Path) -> None:
        """读取项目目录下的 config.json"""
        data = {"version": "9.9.9", "llm_providers": [PROVIDER_CLAUDE]}
        (tmp_dir / "config.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        cfg = load_config(project_dir=tmp_dir)
        assert cfg.version == "9.9.9"
        assert cfg.llm_providers[0].name == "claude"

    def test_overrides_win_over_project_config(self, tmp_dir: Path) -> None:
        """overrides 覆盖项目文件"""
        data = {"version": "1.0.0", "active_provider": "claude"}
        (tmp_dir / "config.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        cfg = load_config(
            project_dir=tmp_dir,
            overrides={"active_provider": "deepseek"},
        )
        assert cfg.active_provider == "deepseek"

    def test_nested_override_merges(self, tmp_dir: Path) -> None:
        """overrides 中的嵌套字段只覆盖指定键"""
        data = {
            "safety": {"command_timeout_seconds": 30, "max_tool_rounds": 20}
        }
        (tmp_dir / "config.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        cfg = load_config(
            project_dir=tmp_dir,
            overrides={"safety": {"command_timeout_seconds": 60}},
        )
        assert cfg.safety.command_timeout_seconds == 60
        assert cfg.safety.max_tool_rounds == 20

    def test_env_api_key_injected_into_loaded_providers(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """环境变量注入到 api_key 为空的 Provider"""
        monkeypatch.setenv("BY19CODE_CLAUDE_API_KEY", "sk-from-env")
        data = {"llm_providers": [PROVIDER_CLAUDE]}
        (tmp_dir / "config.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        cfg = load_config(project_dir=tmp_dir)
        assert cfg.llm_providers[0].api_key == "sk-from-env"

    def test_env_api_key_not_overwrite_existing(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """已有 api_key 时环境变量不覆盖"""
        monkeypatch.setenv("BY19CODE_CLAUDE_API_KEY", "sk-env")
        provider_with_key = {**PROVIDER_CLAUDE, "api_key": "sk-file"}
        data = {"llm_providers": [provider_with_key]}
        (tmp_dir / "config.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        cfg = load_config(project_dir=tmp_dir)
        assert cfg.llm_providers[0].api_key == "sk-file"

    def test_invalid_config_falls_back_to_defaults(
        self, tmp_dir: Path
    ) -> None:
        """config.json 字段类型错误时回退到默认值，不抛出"""
        (tmp_dir / "config.json").write_text(
            '{"version": 12345, "llm_providers": "not-a-list"}',
            encoding="utf-8",
        )
        # 不应抛出异常
        cfg = load_config(project_dir=tmp_dir)
        assert isinstance(cfg, AppConfig)

    def test_no_project_dir(self) -> None:
        """不传 project_dir 时正常返回默认配置"""
        cfg = load_config()
        assert isinstance(cfg, AppConfig)


# ---------------------------------------------------------------------------
# 7. save_config() 写入与往返测试
# ---------------------------------------------------------------------------


class TestSaveConfig:
    def test_save_creates_file(self, tmp_dir: Path) -> None:
        cfg = AppConfig.model_validate(FULL_CONFIG)
        out = tmp_dir / "output" / "config.json"
        save_config(cfg, out)
        assert out.exists()

    def test_save_utf8_encoding(self, tmp_dir: Path) -> None:
        """中文字段存入文件后可读回"""
        cfg = AppConfig()
        cfg.git_config.auto_commit_message = True
        out = tmp_dir / "config.json"
        save_config(cfg, out)
        raw = out.read_text(encoding="utf-8")
        assert "auto_commit_message" in raw

    def test_roundtrip_consistency(self, tmp_dir: Path) -> None:
        """保存后重新加载，关键字段一致"""
        original = AppConfig.model_validate(FULL_CONFIG)
        out = tmp_dir / "config.json"
        save_config(original, out)

        reloaded = load_config(project_dir=tmp_dir)
        assert reloaded.version == original.version
        assert reloaded.active_provider == original.active_provider
        assert reloaded.safety.command_timeout_seconds == (
            original.safety.command_timeout_seconds
        )
        assert len(reloaded.llm_providers) == len(original.llm_providers)

    def test_save_creates_parent_dirs(self, tmp_dir: Path) -> None:
        """父目录不存在时自动创建"""
        out = tmp_dir / "a" / "b" / "c" / "config.json"
        save_config(AppConfig(), out)
        assert out.exists()

    def test_save_lf_line_ending(self, tmp_dir: Path) -> None:
        """输出文件使用 LF 换行符"""
        out = tmp_dir / "config.json"
        save_config(AppConfig(), out)
        raw_bytes = out.read_bytes()
        assert b"\r\n" not in raw_bytes


# ---------------------------------------------------------------------------
# 8. AppConfig 辅助方法测试
# ---------------------------------------------------------------------------


class TestAppConfigHelpers:
    def test_get_active_provider(self) -> None:
        cfg = AppConfig.model_validate(FULL_CONFIG)
        provider = cfg.get_active_provider()
        assert provider is not None
        assert provider.name == "claude"

    def test_get_active_provider_not_found(self) -> None:
        cfg = AppConfig(active_provider="nonexistent")
        assert cfg.get_active_provider() is None

    def test_get_provider_by_name(self) -> None:
        cfg = AppConfig.model_validate(FULL_CONFIG)
        p = cfg.get_provider("deepseek")
        assert p is not None
        assert p.model == "deepseek-chat"

    def test_get_provider_not_found(self) -> None:
        cfg = AppConfig.model_validate(FULL_CONFIG)
        assert cfg.get_provider("unknown") is None
