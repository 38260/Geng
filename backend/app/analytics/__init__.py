"""分析算法层：相关性过滤 → 聚合 → 热度指数 → 生命周期 → 赶梗判断。

这一层是纯函数 + 数据结构，不碰数据库、不碰 HTTP，方便单测。
"""

from .aggregation import aggregate_videos, series_from_stats
from .catch_up import STATUSES, CatchUpResult, decide
from .hotness import HotnessResult, compute_hotness, growth_score, log_score, rolling_hotness
from .lifecycle import LifecycleInput, LifecycleResult, build_input, classify, nickname
from .relevance import MemeTerms, RelevanceResult, match_videos, score_text
from .series import DayPoint, Series, WindowAgg, growth_rate, safe_growth

__all__ = [
    "DayPoint",
    "Series",
    "WindowAgg",
    "growth_rate",
    "safe_growth",
    "MemeTerms",
    "RelevanceResult",
    "score_text",
    "match_videos",
    "aggregate_videos",
    "series_from_stats",
    "HotnessResult",
    "compute_hotness",
    "rolling_hotness",
    "log_score",
    "growth_score",
    "LifecycleInput",
    "LifecycleResult",
    "build_input",
    "classify",
    "nickname",
    "CatchUpResult",
    "decide",
    "STATUSES",
]
