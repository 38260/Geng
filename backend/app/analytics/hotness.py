"""梗热度指数（0-100）。

不使用 B 站官方指数，也不直接用播放量/点赞量排序，而是五个子分数加权：

    Hotness = w1*ViewScore + w2*InteractionScore + w3*ContentScore
            + w4*CreatorScore + w5*GrowthScore

要点：
* 绝对量用 **对数区间归一化**（floor→ceiling），避免一条爆款视频吃掉整个榜；
* 增长分量只看「最近 7 天 vs 前 7 天」，所以历史累计 1 亿播放的老梗不会霸榜；
* 样本量不足（近 7 天相关视频太少）时整体打折，而不是给一个虚高的分数；
* 所有权重与参考值来自 :mod:`app.config.algorithms`。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.config import (
    GROWTH_SCORE_FULL,
    GROWTH_SCORE_ZERO,
    HOTNESS_REFERENCE,
    HOTNESS_WEIGHTS,
    LOW_SAMPLE_DAMPING,
    MIN_SAMPLE_VIDEOS,
)

from .series import Series, growth_rate, safe_growth

PRIMARY_WINDOW = 7
COMPARE_WINDOW = 7


@dataclass
class HotnessResult:
    score: float
    components: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    window_days: int = PRIMARY_WINDOW


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    if value != value:  # NaN
        return low
    return max(low, min(high, value))


def log_score(value: float, metric: str) -> float:
    """把绝对量映射到 0-100（对数区间归一化）。"""
    floor, ceiling = HOTNESS_REFERENCE[metric]
    if value <= 0:
        return 0.0
    if ceiling <= floor:
        return 100.0 if value >= ceiling else 0.0
    if value <= floor:
        return _clamp(100.0 * value / floor * 0.05, 0.0, 5.0)
    ratio = (math.log(value) - math.log(floor)) / (math.log(ceiling) - math.log(floor))
    return _clamp(ratio * 100.0)


def growth_score(rate: float | None) -> float:
    """增长率映射到 0-100：-30% → 0 分，+120% → 100 分。"""
    if rate is None:
        return 50.0  # 无基数（新出现的梗）不惩罚也不奖励，交给活跃度分量判断
    scaled = (rate - GROWTH_SCORE_ZERO) / (GROWTH_SCORE_FULL - GROWTH_SCORE_ZERO)
    return _clamp(scaled * 100.0)


def blended_growth(current_view: float, prev_view: float,
                   current_discussion: float, prev_discussion: float,
                   current_videos: float, prev_videos: float,
                   current_creators: float, prev_creators: float) -> float:
    """综合增长率：播放 0.35 / 讨论 0.35 / 视频数 0.2 / UP 主数 0.1。"""
    parts = (
        (0.35, current_view, prev_view),
        (0.35, current_discussion, prev_discussion),
        (0.20, current_videos, prev_videos),
        (0.10, current_creators, prev_creators),
    )
    return sum(weight * safe_growth(cur, prev) for weight, cur, prev in parts)


def compute_hotness(series: Series, *, end_index: int | None = None) -> HotnessResult:
    """计算截至 ``end_index``（默认最后一天）的滚动 7 天热度。"""
    if not series or len(series) == 0:
        return HotnessResult(score=0.0, components={}, metrics={"reason": "no_data"})

    points = series.points if end_index is None else series.points[: end_index + 1]
    if not points:
        return HotnessResult(score=0.0, components={}, metrics={"reason": "no_data"})

    sub = Series(meme_id=series.meme_id, points=points)
    cur = sub.aggregate(PRIMARY_WINDOW)
    prev = sub.aggregate(COMPARE_WINDOW, offset=PRIMARY_WINDOW)

    growth = blended_growth(
        cur.view, prev.view,
        cur.discussion, prev.discussion,
        cur.video_count, prev.video_count,
        cur.creator_count, prev.creator_count,
    )

    components = {
        "view": log_score(cur.view, "view"),
        "interaction": log_score(cur.interaction, "interaction"),
        "content": log_score(cur.video_count, "content"),
        "creator": log_score(cur.creator_count, "creator"),
        "growth": growth_score(growth),
    }

    # 两个窗口都没有像样的样本时，增长率纯属噪声（考古区冒出 1 条视频
    # 不该被算成"+100% 增长"），此时增长分记 0 而不是外推。
    low_sample = (
        cur.video_count < MIN_SAMPLE_VIDEOS
        and prev.video_count < MIN_SAMPLE_VIDEOS
    )
    if low_sample:
        components["growth"] = 0.0

    weights = {
        "view": HOTNESS_WEIGHTS.view,
        "interaction": HOTNESS_WEIGHTS.interaction,
        "content": HOTNESS_WEIGHTS.content,
        "creator": HOTNESS_WEIGHTS.creator,
        "growth": HOTNESS_WEIGHTS.growth,
    }
    raw = sum(components[key] * weights[key] for key in components)

    damped = raw
    sample_note = None
    if cur.video_count < MIN_SAMPLE_VIDEOS:
        damped = raw * LOW_SAMPLE_DAMPING
        sample_note = f"近{PRIMARY_WINDOW}天相关视频仅 {cur.video_count} 条，热度已按低样本折减"

    metrics = {
        "window_days": PRIMARY_WINDOW,
        "raw_score": round(raw, 2),
        "view": cur.view,
        "interaction": cur.interaction,
        "video_count": cur.video_count,
        "creator_count": cur.creator_count,
        "discussion": cur.discussion,
        "reply": cur.reply,
        "danmaku": cur.danmaku,
        "prev_view": prev.view,
        "prev_discussion": prev.discussion,
        "prev_video_count": prev.video_count,
        "prev_creator_count": prev.creator_count,
        "growth": growth,
        "view_growth": growth_rate(cur.view, prev.view),
        "discussion_growth": growth_rate(cur.discussion, prev.discussion),
        "video_growth": growth_rate(cur.video_count, prev.video_count),
        "creator_growth": growth_rate(cur.creator_count, prev.creator_count),
        "reply_growth": growth_rate(cur.reply, prev.reply),
        "danmaku_growth": growth_rate(cur.danmaku, prev.danmaku),
    }
    if low_sample:
        # 样本太小时不把"+100%"这种外推结果当成真实增长
        metrics["growth"] = None
        metrics["growth_note"] = "近两周样本过小，增长率不计入热度"
    if sample_note:
        metrics["sample_note"] = sample_note

    return HotnessResult(
        score=round(_clamp(damped), 1),
        components={k: round(v, 1) for k, v in components.items()},
        metrics=metrics,
    )


def rolling_hotness(series: Series) -> list[tuple[date, float]]:
    """逐日滚动热度，用于详情页趋势图。"""
    out: list[tuple[date, float]] = []
    for index, point in enumerate(series.points):
        result = compute_hotness(series, end_index=index)
        out.append((point.day, result.score))
    return out
