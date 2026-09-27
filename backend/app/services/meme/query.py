"""梗查询服务：把库里预计算好的指标组装成前端要的形状。

首页要求"打开快"，所以这里只读快照表，不现算热度；
AI 文案单独走 :mod:`app.services.llm.service`，失败只影响它自己那一段。
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import MemeTerms, match_videos, nickname
from app.config import (
    CATCHUP_LABELS,
    HOME_FILTERS,
    HOME_FILTER_LABELS,
    LIFECYCLE_EMOJI,
    LIFECYCLE_LABELS,
    LIFECYCLE_STAGES,
    HOTNESS_WEIGHTS,
    get_logger,
    settings,
)
from app.models import (
    HotnessSnapshot,
    LifecycleSnapshot,
    Meme,
    MemeDailyStats,
    MemeStatus,
    Video,
)
from app.mock.catalogue import spec_for

from ..llm.service import generate_catch_up_advice, generate_trend_explanation
from .certification import certification_progress

log = get_logger(__name__)

DEFAULT_THUMBNAIL = {"emoji": "🎬", "color": "#FFE9E4"}


def _clean(value: Any) -> Any:
    """把 NaN/Inf 变成 None，前端就不会渲染出 NaN。"""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _clean_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: _clean(value) for key, value in payload.items()}


def thumbnail_for(meme: Meme) -> dict[str, str]:
    spec = spec_for(meme.name)
    if spec is None:
        return dict(DEFAULT_THUMBNAIL)
    return {"emoji": spec.emoji, "color": spec.color}


def _growth_percent(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value) * 100, 1)


def _pair(value: Any, growth: Any) -> dict[str, Any]:
    return {"value": int(value or 0), "growth": _growth_percent(growth)}


def _load_rows(session: Session) -> list[tuple[Meme, HotnessSnapshot, LifecycleSnapshot]]:
    """正式梗库 = 双 UP 认证通过 且 已有指标快照。"""
    stmt = (
        select(Meme, HotnessSnapshot, LifecycleSnapshot)
        .join(HotnessSnapshot, HotnessSnapshot.meme_id == Meme.id)
        .join(LifecycleSnapshot, LifecycleSnapshot.meme_id == Meme.id)
        .where(Meme.certified.is_(True), Meme.status == MemeStatus.CERTIFIED)
    )
    return list(session.execute(stmt))


def card_payload(meme: Meme, hotness: HotnessSnapshot, lifecycle: LifecycleSnapshot) -> dict[str, Any]:
    metrics = hotness.metrics or {}
    growth = metrics.get("growth")
    return _clean_dict({
        "id": meme.id,
        "name": meme.name,
        "slug": meme.slug,
        "description": meme.description,
        "aliases": meme.aliases or [],
        "keywords": meme.keywords or [],
        "data_source": settings.data_source,
        "hotness": round(hotness.score, 1),
        "stage": lifecycle.stage,
        "stage_label": lifecycle.stage_label,
        "nickname": nickname(lifecycle.stage, growth),
        "emoji": lifecycle.emoji,
        "discussion_growth": _growth_percent(metrics.get("discussion_growth")),
        "video_growth": _growth_percent(metrics.get("video_growth")),
        "creator_growth": _growth_percent(metrics.get("creator_growth")),
        "catch_status": lifecycle.catch_status,
        "catch_label": lifecycle.catch_label or CATCHUP_LABELS.get(lifecycle.catch_status, ""),
        "catch_reason": lifecycle.catch_reason,
        "catch_confidence": round(lifecycle.catch_confidence, 2),
        "thumbnail": thumbnail_for(meme),
        "meme_data_source": meme.data_source or settings.data_source,
        "certified_at": meme.certified_at.isoformat() if meme.certified_at else None,
        "data_updated_at": meme.data_updated_at.isoformat() if meme.data_updated_at else None,
    })


def list_memes(
    session: Session,
    *,
    filter_key: str = "all",
    search: str = "",
    sort: str = "hotness",
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    rows = _load_rows(session)

    stages = HOME_FILTERS.get(filter_key)
    if stages:
        rows = [row for row in rows if row[2].stage in stages]

    if search:
        needle = search.strip().lower()
        rows = [
            row for row in rows
            if needle in row[0].name.lower()
            or any(needle in alias.lower() for alias in (row[0].aliases or []))
            or any(needle in keyword.lower() for keyword in (row[0].keywords or []))
        ]

    reverse = sort in {"hotness", "growth", "discussion"}
    keyfunc = {
        "hotness": lambda row: row[1].score,
        "growth": lambda row: (row[1].metrics or {}).get("growth") or -999,
        "discussion": lambda row: (row[1].metrics or {}).get("discussion") or 0,
        "name": lambda row: row[0].name,
    }.get(sort, lambda row: row[1].score)
    rows.sort(key=keyfunc, reverse=reverse)

    total = len(rows)
    page = rows[offset:] if limit is None else rows[offset : offset + limit]
    return {
        "filter": filter_key,
        "filter_label": HOME_FILTER_LABELS.get(filter_key, "全部"),
        "total": total,
        "items": [card_payload(meme, hotness, lifecycle) for meme, hotness, lifecycle in page],
    }


def _daily_rows(session: Session, meme_id: int, window_days: int) -> list[MemeDailyStats]:
    return list(
        session.scalars(
            select(MemeDailyStats)
            .where(MemeDailyStats.meme_id == meme_id)
            .order_by(MemeDailyStats.stat_date.desc())
            .limit(window_days)
        )
    )[::-1]


def _metric_block(session: Session, meme: Meme, hotness: HotnessSnapshot) -> dict[str, Any]:
    """详情页四项核心指标：30 天累计量 + 最近 7 天 vs 前 7 天增幅。"""
    rows = _daily_rows(session, meme.id, settings.analysis_window_days)
    metrics = hotness.metrics or {}

    def total(field: str) -> int:
        return sum(getattr(row, field) for row in rows)

    return {
        "videos": _pair(total("video_count"), metrics.get("video_growth")),
        "creators": _pair(total("creator_count"), metrics.get("creator_growth")),
        "comments": _pair(total("reply"), metrics.get("reply_growth")),
        "danmaku": _pair(total("danmaku"), metrics.get("danmaku_growth")),
        "views": _pair(total("view"), metrics.get("view_growth")),
        "interactions": _pair(total("like") + total("coin") + total("favorite"), None),
        "window_days": settings.analysis_window_days,
        "note": "增幅口径为最近 7 天相对前 7 天；参与 UP 主按日累计统计",
    }


def trend_payload(session: Session, meme_id: int, window: int) -> dict[str, Any]:
    rows = _daily_rows(session, meme_id, window)
    return {
        "window": window,
        "points": [
            {
                "date": row.stat_date.isoformat(),
                "hotness": round(row.hotness, 1),
                "view": row.view,
                "discussion": row.discussion,
                "video_count": row.video_count,
                "creator_count": row.creator_count,
            }
            for row in rows
        ],
    }


def video_payloads(session: Session, meme: Meme, limit: int | None = 4) -> list[dict[str, Any]]:
    videos = list(
        session.scalars(
            select(Video).where(Video.meme_id == meme.id).order_by(Video.view.desc())
        )
    )
    kept, _ = match_videos(MemeTerms.from_meme(meme), videos)
    kept.sort(key=lambda video: video.view, reverse=True)
    selected = kept[:limit] if limit else kept
    return [
        {
            **video.to_dict(include_meme=False),
            "duration_text": _duration_text(video.duration_seconds),
            "view_text": _compact(video.view),
            "danmaku_text": _compact(video.danmaku),
        }
        for video in selected
    ]


def _duration_text(seconds: int) -> str:
    seconds = int(seconds or 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _compact(value: int) -> str:
    value = int(value or 0)
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿"
    if value >= 10_000:
        return f"{value / 10_000:.1f}万"
    if value >= 1_000:
        return f"{value / 1000:.1f}K"
    return str(value)


def _insight_data(meme: Meme, hotness: HotnessSnapshot, lifecycle: LifecycleSnapshot) -> dict[str, Any]:
    metrics = hotness.metrics or {}
    return _clean_dict({
        "meme": meme.name,
        "hotness": round(hotness.score, 1),
        "growth": metrics.get("growth"),
        "video_growth": metrics.get("video_growth"),
        "discussion_growth": metrics.get("discussion_growth"),
        "danmaku_growth": metrics.get("danmaku_growth"),
        "creator_growth": metrics.get("creator_growth"),
        "lifecycle": lifecycle.stage,
        "lifecycle_label": lifecycle.stage_label,
        "peak_gap": (lifecycle.indicators or {}).get("peak_gap"),
        "stability": (lifecycle.indicators or {}).get("active_days_7"),
        "status": lifecycle.catch_status,
        "confidence": round(lifecycle.catch_confidence, 2),
        "algorithm_reason": lifecycle.catch_reason,
    })


def cached_insights(
    session: Session, meme_id: int, data_version: str
) -> dict[str, Any]:
    """只读缓存，不打 LLM。

    详情页要"打开就快"，所以 AI 文案不在这里生成：
    命中缓存就直接给，没命中就返回 null，由前端单独调用
    ``POST /api/memes/{id}/insight`` 去生成（带 loading 与重试按钮）。
    """
    from app.models import AIInsight, InsightKind

    out: dict[str, Any] = {}
    for kind, key in (
        (InsightKind.TREND_EXPLANATION, "trend_explanation"),
        (InsightKind.CATCH_UP_ADVICE, "catch_up_advice"),
    ):
        row = session.scalar(
            select(AIInsight).where(
                AIInsight.meme_id == meme_id,
                AIInsight.kind == kind,
                AIInsight.data_version == data_version,
                AIInsight.status == "ok",
            )
        )
        out[key] = row.to_dict() if row else None
    return out


def insights_payload(
    session: Session,
    meme: Meme,
    hotness: HotnessSnapshot,
    lifecycle: LifecycleSnapshot,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    data = _insight_data(meme, hotness, lifecycle)
    version = meme.data_version or hotness.data_version

    trend = generate_trend_explanation(
        session, meme_id=meme.id, data=data, data_version=version, force_refresh=refresh
    )
    advice = generate_catch_up_advice(
        session, meme_id=meme.id, data=data, data_version=version, force_refresh=refresh
    )
    session.commit()
    return {
        "trend_explanation": trend.to_dict(),
        "catch_up_advice": advice.to_dict(),
    }


def get_meme_or_none(session: Session, meme_id: int) -> Meme | None:
    return session.get(Meme, meme_id)


def detail_payload(session: Session, meme: Meme) -> dict[str, Any] | None:
    hotness = session.get(HotnessSnapshot, meme.id)
    lifecycle = session.get(LifecycleSnapshot, meme.id)
    if hotness is None or lifecycle is None:
        return None

    payload = {
        "meme": card_payload(meme, hotness, lifecycle),
        "hotness": {
            "score": round(hotness.score, 1),
            "window_days": hotness.window_days,
            "components": _clean_dict(hotness.components or {}),
            "weights": {
                "view": HOTNESS_WEIGHTS.view,
                "interaction": HOTNESS_WEIGHTS.interaction,
                "content": HOTNESS_WEIGHTS.content,
                "creator": HOTNESS_WEIGHTS.creator,
                "growth": HOTNESS_WEIGHTS.growth,
            },
        },
        "lifecycle": {
            **lifecycle.to_dict(),
            "stages": [
                {
                    "key": stage,
                    "label": LIFECYCLE_LABELS[stage],
                    "emoji": LIFECYCLE_EMOJI[stage],
                    "active": stage == lifecycle.stage,
                }
                for stage in LIFECYCLE_STAGES
            ],
        },
        "metrics": _metric_block(session, meme, hotness),
        "certification": certification_progress(meme),
        "videos": video_payloads(session, meme, limit=4),
        "trend": trend_payload(session, meme.id, settings.analysis_window_days),
    }
    version = meme.data_version or hotness.data_version
    insight = cached_insights(session, meme.id, version)
    # 算法自己的判断永远在，AI 只是锦上添花
    insight["algorithm_reason"] = lifecycle.catch_reason
    insight["catch_up"] = {
        "status": lifecycle.catch_status,
        "label": lifecycle.catch_label,
        "confidence": round(lifecycle.catch_confidence, 2),
        "decided_by": "algorithm",
    }
    payload["insight"] = insight
    return payload


def meta_payload(session: Session) -> dict[str, Any]:
    latest = session.scalar(select(Meme.data_updated_at).order_by(Meme.data_updated_at.desc()))
    total_certified = len(_load_rows(session))
    sources = [meme.data_source or settings.data_source for meme, _, _ in _load_rows(session)]
    source_breakdown = {key: sources.count(key) for key in sorted(set(sources))}
    candidate_count = len(
        list(session.scalars(select(Meme.id).where(Meme.certified.is_(False))))
    )
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "data_source": settings.data_source,
        "is_demo": settings.data_source == "mock",
        "data_updated_at": latest.isoformat() if isinstance(latest, datetime) else latest,
        "certified_count": total_certified,
        "candidate_count": candidate_count,
        "window_days": settings.analysis_window_days,
        "source_breakdown": source_breakdown,
        "filters": [
            {"key": key, "label": HOME_FILTER_LABELS[key]}
            for key in ("all", "hot", "taking_off", "receding")
        ],
        "lifecycle_stages": [
            {"key": stage, "label": LIFECYCLE_LABELS[stage], "emoji": LIFECYCLE_EMOJI[stage]}
            for stage in LIFECYCLE_STAGES
        ],
        "transparency": {
            "data_platform": "Bilibili",
            "certification": ["梗百科", "梗指南"],
            "hotness_algorithm": "赶梗潮自定义热度指数（0-100，五因子加权）",
            "lifecycle_algorithm": "时间序列 + 阈值规则，不由 LLM 决定",
            "llm_role": "仅负责趋势解释与赶梗建议的文案，不参与计算",
        },
    }
