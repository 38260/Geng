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
    aggregate_videos,
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


def collect_all(
    source: str | None = None,
    *,
    meme_ids: list[int] | None = None,
    limit: int | None = None,
    window_days: int | None = None,
    commit: bool = True,
) -> dict[str, object]:
    """跑一遍采集 → 清洗 → 匹配 → 聚合 → 指标计算。

    一个梗只保留一份数据来源：采集某个梗时会先清掉它原来的行，
    避免演示数据和真实数据混在同一个时间序列里被重复计数。
    """
    from app.collectors import make_collector
    from app.collectors.bilibili import BilibiliBlocked

    collector = make_collector(source)
    window = window_days or settings.analysis_window_days
    available, reason = collector.is_available()
    summary: dict[str, object] = {
        "ok": bool(available),
        "source": collector.source,
        "reason": reason,
        "collected": 0,
        "empty": 0,
        "failed": 0,
        "videos": 0,
        "skipped": 0,
        "dropped": 0,
    }
    if not available:
        log.warning("数据源 %s 不可用：%s", collector.source, reason)
        return summary

    session = SessionLocal()
    try:
        stmt = select(Meme).where(Meme.certified.is_(True))
        if meme_ids:
            stmt = stmt.where(Meme.id.in_(meme_ids))
        memes = list(session.scalars(stmt.order_by(Meme.id)))
        if limit:
            memes = memes[:limit]

        for meme in memes:
            try:
                bundle = collector.collect(meme, window_days=window)
            except BilibiliBlocked as exc:
                summary["failed"] = int(summary["failed"]) + 1
                log.warning("梗「%s」采集中断：%s", meme.name, exc)
                continue

            # 清洗 → 梗匹配：搜索结果里混着无关内容，先按相关性打分过滤，
            # 再用剩下的视频做每日聚合，否则统计会被无关样本灌水。
            terms = MemeTerms.from_meme(meme)
            kept, dropped = match_videos(terms, bundle.videos)
            if dropped:
                bundle.videos = kept
                summary["dropped"] = int(summary["dropped"]) + len(dropped)
                log.info("梗「%s」相关性过滤：保留 %s 条，剔除 %s 条", meme.name, len(kept), len(dropped))

            # 只有"统计本来就是从视频聚合出来的"采集器才需要重算，
            # 否则演示数据会被 12 条视频样本压成一条断掉的曲线。
            if getattr(collector, "aggregates_from_videos", True):
                bundle.daily_stats = aggregate_videos(meme.id, kept, data_source=collector.source)

            if not bundle.videos:
                summary["empty"] = int(summary["empty"]) + 1
                log.info("梗「%s」窗口内没有可用视频，保留原数据", meme.name)
                continue

            session.query(MemeDailyStats).filter(MemeDailyStats.meme_id == meme.id).delete()
            session.query(Video).filter(Video.meme_id == meme.id).delete()
            session.flush()

            for stat in bundle.daily_stats:
                stat.meme_id = meme.id
                session.add(stat)
            for video in bundle.videos:
                video.meme_id = meme.id
                session.add(video)

            # autoflush=False：不 flush 的话下面 recompute 读不到刚插入的行
            session.flush()

            meme.data_source = collector.source
            summary["collected"] = int(summary["collected"]) + 1
            summary["videos"] = int(summary["videos"]) + len(bundle.videos)

            if recompute_meme(session, meme) is None:
                summary["skipped"] = int(summary["skipped"]) + 1
            session.commit()

        session.commit()
    finally:
        session.close()
    return summary


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
