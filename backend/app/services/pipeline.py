"""指标计算管线：时间序列 → 热度 → 生命周期 → 赶梗判断 → 落库。

对应文档的数据处理架构：

    Data Collector → Cleaner → Meme Matcher → 双UP认证 → Time Series Aggregator
    → Hotness Calculator → Lifecycle Analyzer → (LLM) → API

LLM 不在这条链路上，它只在读接口里被单独调用，且失败不影响这里产出的任何字段。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import (
    MemeTerms,
    Series,
    build_input,
    classify,
    compute_hotness,
    decide,
    match_videos,
    rolling_hotness,
)
from app.config import get_logger, settings
from app.models import (
    HotnessSnapshot,
    LifecycleSnapshot,
    Meme,
    MemeDailyStats,
    MemeStatus,
    SessionLocal,
    Video,
)
from app.services.meme.certification import require_certified

log = get_logger(__name__)


@dataclass
class MemeMetrics:
    hotness: Any
    lifecycle: Any
    catch_up: Any
    series: Series
    data_version: str


def compute_data_version(end_day: str, heat: float, metrics: dict[str, Any]) -> str:
    """数据版本：底层数据明显变化时才让 AI 缓存失效。"""
    payload = "|".join(
        str(item)
        for item in (
            end_day,
            round(heat, 1),
            metrics.get("video_count"),
            metrics.get("view"),
            metrics.get("discussion"),
            metrics.get("creator_count"),
        )
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def filter_meme_videos(session: Session, meme: Meme) -> tuple[list[Video], list[Video]]:
    """对已入库视频重跑相关性过滤（清洗 + 匹配 + 去重）。"""
    videos = list(
        session.scalars(
            select(Video).where(Video.meme_id == meme.id).order_by(Video.publish_time.desc())
        )
    )
    seen: set[str] = set()
    unique: list[Video] = []
    for video in videos:
        if video.bvid in seen:
            continue
        seen.add(video.bvid)
        unique.append(video)
    return match_videos(MemeTerms.from_meme(meme), unique)


def recompute_meme(session: Session, meme: Meme, *, window_days: int | None = None) -> MemeMetrics | None:
    """重算单个梗。未通过双 UP 认证的梗直接拒绝（认证闸门）。"""
    try:
        require_certified(meme)
    except RuntimeError as exc:
        log.warning("拒绝计算未认证梗：%s", exc)
        meme.status = MemeStatus.CANDIDATE
        return None

    window = window_days or settings.analysis_window_days
    stats = list(
        session.scalars(
            select(MemeDailyStats)
            .where(MemeDailyStats.meme_id == meme.id)
            .order_by(MemeDailyStats.stat_date)
        )
    )
    if not stats:
        log.info("梗「%s」暂无时间序列数据，跳过", meme.name)
        return None

    series = Series.from_stats(meme.id, stats, window_days=window)
    daily = rolling_hotness(series)
    by_day = dict(daily)
    for row in stats:
        row.hotness = by_day.get(row.stat_date, row.hotness)

    current = compute_hotness(series)
    daily_values = [value for _, value in daily]
    inp = build_input(
        series,
        heat=current.score,
        growth=current.metrics.get("growth"),
        daily_hotness=daily_values,
    )
    lifecycle = classify(inp)
    peak_gap = inp.peak_gap
    catch_up = decide(
        inp,
        stage=lifecycle.stage,
        heat=current.score,
        growth=current.metrics.get("growth"),
        peak_gap=peak_gap,
        creator_growth=current.metrics.get("creator_growth"),
    )

    end_day = series.end_day.isoformat() if series.end_day else ""
    data_version = compute_data_version(end_day, current.score, current.metrics)

    hotness_row = session.get(HotnessSnapshot, meme.id)
    if hotness_row is None:
        hotness_row = HotnessSnapshot(meme_id=meme.id)
        session.add(hotness_row)
    hotness_row.score = current.score
    hotness_row.window_days = current.window_days
    hotness_row.components = current.components
    hotness_row.metrics = current.metrics
    hotness_row.computed_at = datetime.now()
    hotness_row.data_version = data_version

    lifecycle_row = session.get(LifecycleSnapshot, meme.id)
    if lifecycle_row is None:
        lifecycle_row = LifecycleSnapshot(meme_id=meme.id)
        session.add(lifecycle_row)
    lifecycle_row.stage = lifecycle.stage
    lifecycle_row.stage_label = lifecycle.label
    lifecycle_row.emoji = lifecycle.emoji
    lifecycle_row.indicators = lifecycle.indicators
    lifecycle_row.reasons = lifecycle.reasons
    lifecycle_row.catch_status = catch_up.status
    lifecycle_row.catch_label = catch_up.label
    lifecycle_row.catch_reason = catch_up.reason
    lifecycle_row.catch_confidence = catch_up.confidence
    lifecycle_row.computed_at = datetime.now()
    lifecycle_row.data_version = data_version

    meme.data_version = data_version
    meme.data_updated_at = datetime.now()

    log.info(
        "梗「%s」热度 %.1f / %s / %s（数据版本 %s）",
        meme.name, current.score, lifecycle.label, catch_up.label, data_version[:8],
    )
    return MemeMetrics(
        hotness=current, lifecycle=lifecycle, catch_up=catch_up, series=series, data_version=data_version
    )


def recompute_all(*, window_days: int | None = None, commit: bool = True) -> dict[str, int]:
    """重算全部已认证梗（首页要快，所以热度/生命周期全部预计算好）。"""
    session = SessionLocal()
    result = {"computed": 0, "skipped": 0, "total": 0}
    try:
        memes = list(session.scalars(select(Meme).order_by(Meme.id)))
        result["total"] = len(memes)
        for meme in memes:
            metrics = recompute_meme(session, meme, window_days=window_days)
            if metrics is None:
                result["skipped"] += 1
            else:
                result["computed"] += 1
        if commit:
            session.commit()
    finally:
        session.close()
    return result
