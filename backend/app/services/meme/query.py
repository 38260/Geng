"""梗查询服务：把库里预计算好的指标组装成前端要的形状。

首页要求"打开快"，所以这里只读快照表，不现算热度；
AI 文案单独走 :mod:`app.services.llm.service`，失败只影响它自己那一段。
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
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

DEFAULT_THUMBNAIL = {"emoji": "🎬", "color": "#FFE9E4", "image": ""}


def _clean(value: Any) -> Any:
    """把 NaN/Inf 变成 None，前端就不会渲染出 NaN。"""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _clean_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: _clean(value) for key, value in payload.items()}


def _https(url: str) -> str:
    """B站返回的是协议相对地址（//i0.hdslb.com/...），浏览器 img src 需要补上协议。"""
    url = (url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    return url if url.startswith("http") else ""


def covers_by_meme(session: Session) -> dict[int, str]:
    """梗的代表封面 = 该梗播放量最高的那条真实视频的 B站封面。

    一次查询拿全表再分组，避免列表页 N+1；演示数据没有真实封面，
    拿不到就退回"主题色 + 表情"贴纸，绝不编造图片地址。
    """
    rows = session.execute(
        select(Video.meme_id, Video.cover, Video.view).order_by(Video.view.desc())
    )
    out: dict[int, str] = {}
    for meme_id, cover, _view in rows:
        link = _https(cover)
        if link and meme_id not in out:
            out[meme_id] = link
    return out


def cover_for_meme(session: Session, meme_id: int) -> str:
    link = covers_by_meme(session).get(meme_id, "")
    return link


def manual_cover_for(meme: Meme) -> str:
    """人工维护的封面地址（站内素材保留相对路径，站外统一补 https）。

    注意顺序：`//host/x.jpg` 是协议相对外链，不是站内路径。
    """
    raw = (meme.cover_url or "").strip()
    if not raw or raw.startswith("//") or raw.startswith("http"):
        return _https(raw)
    return raw if raw.startswith("/") else ""


def thumbnail_for(meme: Meme, real_cover: str = "") -> dict[str, Any]:
    """封面优先级：人工维护 > B站真实封面 > 演示素材图 > 主题色 + 表情贴纸。

    真实采集的梗必须用真实视频封面，不能拿设计稿里的素材图冒充抓取结果；
    只有演示数据才允许用那批素材图。人工挑的封面带 manual 标记，
    免得看的人以为它是某条真实视频的封面。
    """
    spec = spec_for(meme.name)
    emoji = spec.emoji if spec else DEFAULT_THUMBNAIL["emoji"]
    color = spec.color if spec else DEFAULT_THUMBNAIL["color"]
    manual = manual_cover_for(meme)
    demo_image = getattr(spec, "image", "") if spec else ""
    is_real = (meme.data_source or "mock") == "bilibili"
    image = manual or real_cover or ("" if is_real else demo_image)
    return {"emoji": emoji, "color": color, "image": image, "manual": bool(manual)}


def _growth_percent(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value) * 100, 1)


def _pair(value: Any, growth: Any) -> dict[str, Any]:
    return {"value": int(value or 0), "growth": _growth_percent(growth)}


def effective_source(sources: list[str]) -> tuple[str, bool]:
    """站点级数据源标签由库里真实存在的数据决定，而不是由配置决定。

    配置写的是 bilibili、但库里还是演示数据（例如刚建库还没采集）时，
    绝不能对外显示"B站真实数据"。混合情况一律按"含演示数据"标注。
    """
    present = {item or "mock" for item in sources}
    if not present:
        return settings.data_source, settings.data_source == "mock"
    if present == {"bilibili"}:
        return "bilibili", False
    if present == {"mock"}:
        return "mock", True
    return "mixed", True


def _load_rows(session: Session) -> list[tuple[Meme, HotnessSnapshot, LifecycleSnapshot]]:
    """正式梗库 = 双 UP 认证通过 且 已有指标快照。

    真实模式下再加一道：数据必须真是 B 站采来的、认证必须真在线核验过（verified_both）。
    手写演示梗的 certified 是自记自认的，跟琵琶曲、老叟戏顽童这种真梗同榜，
    就是拿假数字压真热度。
    """
    stmt = (
        select(Meme, HotnessSnapshot, LifecycleSnapshot)
        .join(HotnessSnapshot, HotnessSnapshot.meme_id == Meme.id)
        .join(LifecycleSnapshot, LifecycleSnapshot.meme_id == Meme.id)
        .where(Meme.certified.is_(True), Meme.status == MemeStatus.CERTIFIED)
    )
    if settings.data_source == "bilibili" and settings.leaderboard_require_verified:
        stmt = stmt.where(
            Meme.data_source == "bilibili",
            Meme.verification_state == "verified_both",
        )
    return list(session.execute(stmt))


def card_payload(
    meme: Meme,
    hotness: HotnessSnapshot,
    lifecycle: LifecycleSnapshot,
    *,
    real_cover: str = "",
) -> dict[str, Any]:
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
        "thumbnail": thumbnail_for(meme, real_cover),
        "meme_data_source": meme.data_source or settings.data_source,
        "verification_state": meme.verification_state or "unverified",
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
    covers = covers_by_meme(session)
    return {
        "filter": filter_key,
        "filter_label": HOME_FILTER_LABELS.get(filter_key, "全部"),
        "total": total,
        "items": [
            card_payload(meme, hotness, lifecycle, real_cover=covers.get(meme.id, ""))
            for meme, hotness, lifecycle in page
        ],
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
            "cover": _https(video.cover),
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
        "meme": card_payload(
            meme, hotness, lifecycle, real_cover=cover_for_meme(session, meme.id)
        ),
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
    rows = _load_rows(session)
    # 统计截至日：只看"榜单里这些梗"的序列最后一天。采集窗口刻意不含今天
    # （今天没过完，头部样本会偏低、增幅会假跌），所以这里必须把"截至哪天"讲明白，
    # 否则用户看到的就是"数据是过去的"。取可见梗而不是全库，免得被演示数据顶高。
    visible_ids = [meme.id for meme, _, _ in rows]
    data_through = session.scalar(
        select(func.max(MemeDailyStats.stat_date)).where(MemeDailyStats.meme_id.in_(visible_ids or [-1]))
    )
    lag_days = (date.today() - data_through).days if data_through else None
    total_certified = len(rows)
    sources = [meme.data_source or settings.data_source for meme, _, _ in rows]
    source_breakdown = {key: sources.count(key) for key in sorted(set(sources))}
    site_source, site_is_demo = effective_source(sources)
    candidate_count = len(
        list(session.scalars(select(Meme.id).where(Meme.certified.is_(False))))
    )
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "data_source": site_source,
        "is_demo": site_is_demo,
        "configured_source": settings.data_source,
        "data_updated_at": latest.isoformat() if isinstance(latest, datetime) else latest,
        "data_through": data_through.isoformat() if data_through else None,
        "data_lag_days": lag_days,
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
            "sampling": (
                "真实采集口径：每日取 B 站该关键词下播放量最高的前 20 条相关视频作为样本，"
                "所以「当日播放量」是该日头部内容的合计，不是全站绝对量；"
                "跨日与跨梗比较用同一把尺子。"
                "统计窗口不含今天——今天还没过完，头部样本会偏低、增幅会假跌。"
                if site_source == "bilibili"
                else (
                    "混合状态：配置的数据源是 " + settings.data_source +
                    "，但库里仍有演示数据，请先跑 python -m app.scripts.rebuild_from_bilibili。"
                    if site_source == "mixed"
                    else "演示数据：数值由生命周期原型生成，不是真实抓取结果。"
                )
            ),
        },
    }
