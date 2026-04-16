"""模型超时跟踪器

记录每个模型的超时次数，用于智能选择下一个模型。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class TimeoutTracker:
    """模型超时跟踪器

    职责
    ----
    - 记录每个模型的超时次数
    - 提供获取最少超时模型的方法
    - 持久化超时记录到文件
    """

    def __init__(self, storage_path: Path | None = None):
        """初始化超时跟踪器。

        参数
        ----
        storage_path : 存储文件路径（可选，默认为 ~/.by19code/timeout_log.json）
        """
        if storage_path is None:
            storage_path = Path.home() / ".by19code" / "timeout_log.json"

        self.storage_path = storage_path
        self.timeout_counts: Dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        """从文件加载超时记录。"""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self.timeout_counts = json.load(f)
                logger.debug("[超时跟踪] 已加载超时记录: %s", self.timeout_counts)
        except Exception as e:
            logger.warning("[超时跟踪] 加载超时记录失败: %s", e)
            self.timeout_counts = {}

    def _save(self) -> None:
        """保存超时记录到文件。"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.timeout_counts, f, ensure_ascii=False, indent=2)
            logger.debug("[超时跟踪] 已保存超时记录: %s", self.timeout_counts)
        except Exception as e:
            logger.error("[超时跟踪] 保存超时记录失败: %s", e)

    def record_timeout(self, model_name: str) -> None:
        """记录模型超时。

        参数
        ----
        model_name : 模型名称
        """
        if model_name not in self.timeout_counts:
            self.timeout_counts[model_name] = 0

        self.timeout_counts[model_name] += 1
        logger.info("[超时跟踪] 记录超时: %s (总计: %d 次)", model_name, self.timeout_counts[model_name])
        self._save()

    def get_least_timeout_model(self, available_models: list[str], exclude: str | None = None) -> str | None:
        """获取超时次数最少的模型。

        参数
        ----
        available_models : 可用模型列表
        exclude          : 要排除的模型（通常是当前模型）

        返回
        ----
        str | None : 超时次数最少的模型名称，如果没有可用模型返回 None
        """
        # 过滤掉要排除的模型
        candidates = [m for m in available_models if m != exclude]

        if not candidates:
            return None

        # 按超时次数排序（未记录的视为 0 次）
        candidates_sorted = sorted(candidates, key=lambda m: self.timeout_counts.get(m, 0))

        best_model = candidates_sorted[0]
        timeout_count = self.timeout_counts.get(best_model, 0)

        logger.info("[超时跟踪] 选择最少超时模型: %s (超时 %d 次)", best_model, timeout_count)
        return best_model

    def get_timeout_count(self, model_name: str) -> int:
        """获取指定模型的超时次数。

        参数
        ----
        model_name : 模型名称

        返回
        ----
        int : 超时次数
        """
        return self.timeout_counts.get(model_name, 0)

    def reset_counts(self) -> None:
        """重置所有超时计数。"""
        self.timeout_counts = {}
        self._save()
        logger.info("[超时跟踪] 已重置所有超时计数")
