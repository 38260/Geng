"""采集器公共契约。

无论数据来自演示生成器还是 B 站真实接口，都返回同一个 :class:`CollectedBundle`，
下游的清洗 / 匹配 / 聚合 / 热度计算完全不需要知道数据从哪来。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.models import Meme, MemeDailyStats, Video


@dataclass
class CertificationEvidence:
    """某个梗解释 UP 主「介绍过这个梗」的证据，交给认证服务落库。"""

    role: str
    bvid: str = ""
    video_title: str = ""
    published_at: datetime | None = None
    confirmed: bool = True
    data_source: str = "mock"


@dataclass
class CollectedBundle:
    daily_stats: list[MemeDailyStats] = field(default_factory=list)
    videos: list[Video] = field(default_factory=list)
    certifications: list[CertificationEvidence] = field(default_factory=list)


class Collector(Protocol):
    """梗库驱动 + B 站定向搜索 + 每日聚合。"""

    source: str

    def collect(self, meme: Meme, *, window_days: int) -> CollectedBundle:
        ...

    def is_available(self) -> tuple[bool, str]:
        """返回 (是否可用, 原因)。不可用时上层必须回退到演示数据。"""
        ...
