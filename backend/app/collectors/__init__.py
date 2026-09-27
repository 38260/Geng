"""采集器工厂：`DATA_SOURCE=mock|bilibili` 决定用哪一个。"""

from __future__ import annotations

from app.config import settings

from .base import CollectedBundle, Collector
from .bilibili_collector import BilibiliCollector
from .mock_collector import MockCollector


def make_collector(source: str | None = None) -> Collector:
    chosen = (source or settings.data_source or "mock").lower()
    if chosen == "bilibili":
        return BilibiliCollector()
    return MockCollector()


__all__ = ["CollectedBundle", "Collector", "MockCollector", "BilibiliCollector", "make_collector"]
