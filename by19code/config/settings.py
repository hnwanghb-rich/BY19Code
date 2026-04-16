"""BY19Code 配置管理模块【T02】

加载优先级（高 → 低）：
  1. overrides 参数（命令行参数）
  2. 项目目录 config.json
  3. %USERPROFILE%\\.by19code\\config.json（全局默认）
  4. 环境变量 BY19CODE_{PROVIDER}_API_KEY
  5. 内置默认值
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Windows 危险命令黑名单（默认值）
_DEFAULT_BLOCKED_COMMANDS: list[str] = [
    "format",
    "shutdown",
    "reboot",
    "del /s /q C:\\",
    "rd /s /q",
    "rmdir /s /q",
    "Remove-Item -Recurse -Force C:\\",
    "reg delete",
    "bcdedit",
    "diskpart",
    "net stop",
]


# ---------------------------------------------------------------------------
# Pydantic v2 配置模型
# ---------------------------------------------------------------------------


class LLMProviderConfig(BaseModel):
    """单个 LLM Provider 配置"""

    model_config = ConfigDict(extra="ignore")

    name: str
    display_name: str
    # "anthropic" 或 "openai_compat"
    provider_type: str
    # 为空时从环境变量 BY19CODE_{NAME}_API_KEY 读取
    api_key: str = ""
    base_url: str
    model: str
    max_tokens: int = 8192
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    # 是否支持工具调用（某些模型不支持 function calling）
    supports_tools: bool = True


class GitConfig(BaseModel):
    """Git 操作配置"""

    model_config = ConfigDict(extra="ignore")

    auto_commit_message: bool = True


class WorkspaceConfig(BaseModel):
    """工作空间配置"""

    model_config = ConfigDict(extra="ignore")

    default_path: str = "."


class SafetyConfig(BaseModel):
    """命令执行沙箱安全配置"""

    model_config = ConfigDict(extra="ignore")

    command_timeout_seconds: int = 30
    max_tool_rounds: int = 20
    change_model_time: int = 60  # 模型无响应超时时间（秒），超时后自动切换模型
    blocked_commands: list[str] = Field(
        default_factory=lambda: _DEFAULT_BLOCKED_COMMANDS.copy()
    )


class DatabaseConfig(BaseModel):
    """数据库配置"""

    model_config = ConfigDict(extra="ignore")

    # 支持 %USERPROFILE% 和 ~ 展开
    path: str = r"%USERPROFILE%\.by19code\by19code.db"
    log_retention_days: int = 90

    def resolved_path(self) -> Path:
        """展开环境变量与 ~ 后返回实际 Path 对象"""
        expanded = os.path.expandvars(self.path)
        return Path(expanded).expanduser().resolve()


class AppConfig(BaseModel):
    """应用全局配置根模型"""

    model_config = ConfigDict(extra="ignore")

    version: str = "0.1.0"
    llm_providers: list[LLMProviderConfig] = Field(default_factory=list)
    active_provider: str = "claude"
    git_config: GitConfig = Field(default_factory=GitConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    def get_active_provider(self) -> LLMProviderConfig | None:
        """返回当前激活的 Provider 配置，未找到返回 None"""
        for provider in self.llm_providers:
            if provider.name == self.active_provider:
                return provider
        return None

    def get_provider(self, name: str) -> LLMProviderConfig | None:
        """按名称返回指定 Provider 配置，未找到返回 None"""
        for provider in self.llm_providers:
            if provider.name == name:
                return provider
        return None


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _expand_path(path_str: str) -> Path:
    """展开 %USERPROFILE% / ~ 变量后返回 Path 对象"""
    expanded = os.path.expandvars(path_str)
    return Path(expanded).expanduser()


def _load_json_file(path: Path) -> dict[str, Any]:
    """
    读取 JSON 配置文件，返回解析后的 dict。
    文件不存在或格式错误时返回空 dict 并记录警告。
    """
    try:
        if path.exists() and path.is_file():
            with open(path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            logger.debug("[配置] 已加载: %s", path)
            return data
    except json.JSONDecodeError as e:
        logger.warning("[配置] JSON 解析失败 %s: %s", path, e)
    except OSError as e:
        logger.warning("[配置] 文件读取失败 %s: %s", path, e)
    return {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    深度合并两个字典，override 的值覆盖 base。
    嵌套 dict 递归合并；list 和其他类型直接替换。
    """
    result = base.copy()
    for key, val in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(val, dict)
        ):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _inject_env_api_keys(providers: list[dict[str, Any]]) -> None:
    """
    遍历 providers 列表，将环境变量 BY19CODE_{NAME}_API_KEY 的值
    注入到 api_key 为空的 Provider 中。
    """
    for provider in providers:
        if provider.get("api_key"):
            # 已有 key，跳过
            continue
        name_upper = provider.get("name", "").upper()
        env_key = f"BY19CODE_{name_upper}_API_KEY"
        env_val = os.environ.get(env_key, "").strip()
        if env_val:
            provider["api_key"] = env_val
            logger.debug("[配置] 环境变量注入 API Key: %s", env_key)


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------


def load_config(
    project_dir: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> AppConfig:
    """
    按优先级加载并合并配置，返回经 Pydantic 验证的 AppConfig 实例。

    参数
    ----
    project_dir : 项目根目录（可选）。若提供，优先读取该目录下的 config.json。
    overrides   : 最高优先级覆盖项（通常来自命令行参数），dict 结构与配置文件相同。

    加载顺序
    --------
    内置默认值
      ← BY19Code 安装目录的 config.json（如果存在）
        ← 全局配置 %USERPROFILE%\\.by19code\\config.json
          ← 项目配置 <project_dir>\\config.json
            ← overrides 参数
              ← 环境变量 BY19CODE_{PROVIDER}_API_KEY（仅填充 api_key 空值）
    """
    # 第一层：BY19Code 安装目录的默认配置
    by19code_root = Path(__file__).parent.parent.parent  # by19code/config/settings.py -> BY19Code/

    # 加载 .env 文件（优先级：BY19Code 安装目录 → 项目目录）
    try:
        from dotenv import load_dotenv

        # 1. 先加载 BY19Code 安装目录的 .env（全局 API Keys）
        by19code_env = by19code_root / ".env"
        if by19code_env.exists():
            load_dotenv(by19code_env)
            logger.debug("[配置] 已加载 BY19Code .env 文件: %s", by19code_env)

        # 2. 再加载项目目录的 .env（可覆盖全局配置）
        if project_dir:
            project_env = Path(project_dir) / ".env"
            if project_env.exists():
                load_dotenv(project_env, override=True)
                logger.debug("[配置] 已加载项目 .env 文件: %s", project_env)
    except ImportError:
        logger.debug("[配置] python-dotenv 未安装，跳过 .env 文件加载")
    merged: dict[str, Any] = _load_json_file(by19code_root / "config.json")

    # 如果没有找到，尝试 config.example.json
    if not merged:
        merged = _load_json_file(by19code_root / "config.example.json")

    # 第二层：全局配置文件
    global_dir = _expand_path(r"%USERPROFILE%\.by19code")
    global_config = _load_json_file(global_dir / "config.json")
    if global_config:
        merged = _deep_merge(merged, global_config)

    # 第三层：项目配置文件（覆盖全局）
    if project_dir is not None:
        project_data = _load_json_file(Path(project_dir) / "config.json")
        if project_data:
            merged = _deep_merge(merged, project_data)

    # 第四层：命令行参数覆盖（最高优先级）
    if overrides:
        merged = _deep_merge(merged, overrides)

    # 第五层：环境变量注入 API Key（配置文件格式错误时 providers 可能不是 list）
    providers_raw_any = merged.get("llm_providers", [])
    providers_raw: list[dict[str, Any]] = (
        providers_raw_any if isinstance(providers_raw_any, list) else []
    )
    _inject_env_api_keys(providers_raw)

    # 解析为 AppConfig，解析失败回退到默认值并记录错误
    try:
        config = AppConfig.model_validate(merged)
    except Exception as e:
        logger.error("[配置] 配置解析失败，使用默认值: %s", e)
        config = AppConfig()

    # 如果没有任何 provider 配置，给出友好提示
    if not config.llm_providers:
        logger.warning("[配置] 未找到任何 LLM Provider 配置")
        logger.warning("[配置] 请在以下位置之一创建 config.json：")
        logger.warning("[配置]   1. %s", by19code_root / "config.json")
        logger.warning("[配置]   2. %s", global_dir / "config.json")
        if project_dir:
            logger.warning("[配置]   3. %s", project_dir / "config.json")
        logger.warning("[配置] 或参考 config.example.json 创建配置文件")

    # 对模型实例再次注入（providers 来自默认值时 providers_raw 为空）
    for provider in config.llm_providers:
        if not provider.api_key:
            env_key = f"BY19CODE_{provider.name.upper()}_API_KEY"
            env_val = os.environ.get(env_key, "").strip()
            if env_val:
                provider.api_key = env_val

    return config


def save_config(config: AppConfig, path: Path) -> None:
    """
    将 AppConfig 序列化为 JSON 并写入指定路径（UTF-8 编码，LF 换行）。
    父目录不存在时自动创建。

    参数
    ----
    config : 要保存的配置对象。
    path   : 目标文件路径（pathlib.Path）。

    异常
    ----
    OSError : 目录创建或文件写入失败时抛出。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = config.model_dump()
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("[配置] 已保存: %s", path)
    except OSError as e:
        logger.error("[配置] 保存失败 %s: %s", path, e)
        raise
