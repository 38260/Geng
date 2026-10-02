"""梗查询服务：把库里预计算好的指标组装成前端要的形状。

首页要求"打开快"，所以这里只读快照表，不现算热度；
AI 文案单独走 :mod:`app.services.llm.service`，失败只影响它自己那一段。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.analytics import MemeTerms, match_videos, nickname
from app.config import (
    BOARD_HIDE_OBSOLETE,
    BOARD_MIN_RECENT_VIEW,
    CATCHUP_LABELS,
    HOME_FILTERS,
    HOME_FILTER_LABELS,
    LIFECYCLE_EMOJI,
    LIFECYCLE_LABELS,
    LIFECYCLE_STAGES,
    LIFECYCLE_THRESHOLDS,
    HOTNESS_WEIGHTS,
    get_logger,
    settings,
)
from app.models import (
    HotnessSnapshot,
    LifecycleSnapshot,
    Meme,
    MemeCertification,
    MemeDailyStats,
    MemeStatus,
    Video,
    VideoTranscript,
)
from app.mock.catalogue import spec_for

from ..llm.service import generate_catch_up_advice, generate_trend_explanation
from .collections import collection_member_ids, collection_summary, tag_summary
from .ai_intro import (
    build_material,
    generate_meme_intro,
    material_digest,
    read_cached_ai_intro,
)
from .intro import compose_intro, transcript_block
from .summary import read_cached_summary
from .certification import (
    ENCYCLOPEDIA,
    GUIDE,
    cert_label,
    certified_by,
    certification_progress,
    settings_cert_window_days,
)

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
    """榜单 = 通过发现层准入（任一 UP 主介绍过）且已有指标快照的梗。

    真实模式下再加一道：数据必须真是 B 站采来的、认证证据必须真在 UP 主投稿里
    抓到过（verified_both 或 partially_verified）。手写演示梗的 certified 是自记自认的，
    跟琵琶曲、老叟戏顽童这种真梗同榜，就是拿假数字压真热度。
    单 UP 的梗在这里不被排除，只有标签会写明它是"梗百科认证"还是"双 UP 认证"。
    """
    stmt = (
        select(Meme, HotnessSnapshot, LifecycleSnapshot)
        .join(HotnessSnapshot, HotnessSnapshot.meme_id == Meme.id)
        .join(LifecycleSnapshot, LifecycleSnapshot.meme_id == Meme.id)
        .where(
            or_(Meme.encyclopedia_confirmed.is_(True), Meme.guide_confirmed.is_(True)),
            Meme.status == MemeStatus.CERTIFIED,
        )
    )
    if settings.data_source == "bilibili" and settings.leaderboard_require_verified:
        stmt = stmt.where(
            Meme.data_source == "bilibili",
            Meme.verification_state.in_(("verified_both", "partially_verified")),
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
        # 主题标签（key 数组）。空数组 = 还没打标，与「标成其他」不是一回事，
        # 所以界面要能区分：空就什么都不显示，不要硬塞一个「其他」。
        "tags": meme.tags or [],
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
        # 覆盖度自解释：卡片上那几个百分比是"几天观测出来的"必须能查到，
        # 否则用户没法分辨"-62%"是真跌还是接口给了几个空壳。
        "observed_days": metrics.get("observed_days"),
        "observed_window_days": metrics.get("window_days"),
        "coverage": metrics.get("coverage"),
        "prev_observed_days": metrics.get("prev_observed_days"),
        "thumbnail": thumbnail_for(meme, real_cover),
        "meme_data_source": meme.data_source or settings.data_source,
        "verification_state": meme.verification_state or "unverified",
        # 认证强度标签如实说明证据来自哪一位 UP：榜单不再要求"两位都做过"，
        # 但用户必须能看出这条是双 UP 还是单 UP。
        "cert_label": cert_label(meme),
        "certified_by": certified_by(meme),
        "double_certified": bool(meme.certified),
        "certified_at": meme.certified_at.isoformat() if meme.certified_at else None,
        "data_updated_at": meme.data_updated_at.isoformat() if meme.data_updated_at else None,
    })


def board_gate_reason(hotness: HotnessSnapshot, lifecycle: LifecycleSnapshot) -> str:
    """为什么这个梗没进热榜。返回空串表示通过门槛。

    准入（并集）只解决"这是不是个真梗"；热榜还要回答"今天玩什么"，
    所以过气的、以及 30 天里几乎没内容的都要挡在外面——但脉冲型梗例外：
    天数少不代表不火，近 7 天头部播放够大就照样上榜。

    注意 ``insufficient``（数据不足）这个状态**不参与门槛**：门槛看的是存量水平
    （近 7 天头部播放），跨梗用的是同一把尺子，偏差共通；被观测洞影响的是
    "涨还是退"这类趋势结论，那个由生命周期闸门去管。
    """
    if not settings.leaderboard_gate:
        return ""
    if BOARD_HIDE_OBSOLETE and lifecycle.stage == "obsolete":
        return "过气（已归入考古区）"
    recent_view = int((hotness.metrics or {}).get("view") or 0)
    if recent_view >= BOARD_MIN_RECENT_VIEW:
        return ""
    active_days = int((hotness.metrics or {}).get("active_days") or 0)
    return (f"近 7 天头部播放 {recent_view:,}，低于上榜下限 {BOARD_MIN_RECENT_VIEW:,}"
            f"（30 天内 {active_days} 天有内容）")


def on_board(hotness: HotnessSnapshot, lifecycle: LifecycleSnapshot) -> bool:
    return not board_gate_reason(hotness, lifecycle)


def fresh_cert_ids(session: Session, *, days: int | None = None) -> set[int]:
    """认证窗口内还有**真实解说证据**的梗 id —— 就是发现层定义的那个"最新池"。

    热榜回答的是"今天玩什么"，所以资格不认 `Meme.encyclopedia_confirmed` 这种
    一次性布尔标记：它一旦为真就永远为真，解说视频却是会过期的。
    只认带 `published_at` 的真实证据行（`data_source='bilibili'`）。
    """
    floor = datetime.now() - timedelta(days=days or settings.cert_window_days)
    return {
        row[0]
        for row in session.execute(
            select(MemeCertification.meme_id).where(
                MemeCertification.data_source == "bilibili",
                MemeCertification.published_at >= floor,
            )
        )
    }


def _board_rows(
    session: Session,
    rows: list[tuple[Meme, HotnessSnapshot, LifecycleSnapshot]],
) -> list[tuple[Meme, HotnessSnapshot, LifecycleSnapshot]]:
    """热榜口径：先过"活着"门槛，再限定在最新准入池内。

    两处（列表与 meta 计数）共用这一个函数，免得页面显示 20 个、
    头部却报 26 个——数字对不上时用户只会觉得数据不可信。
    """
    kept = [row for row in rows if on_board(row[1], row[2])]
    if settings.data_source == "bilibili" and settings.leaderboard_require_fresh_cert:
        # 解说证据出窗的梗不算"今天能赶的梗"，哪怕存量热度还很高；
        # 完整梗库（scope=all）仍然查得到它。
        fresh = fresh_cert_ids(session)
        kept = [row for row in kept if row[0].id in fresh]
    return kept


def parse_ids(raw: str, *, cap: int = 100) -> list[int]:
    """把 "1,2, 3" 解析成 [1,2,3]；非数字丢掉，超出上限截断。

    小程序的收藏只存在本机，要拿实时数据只能把 id 传回来查，
    所以列表接口得支持按 id 取——不能为了一个本地功能去存梗的副本，
    那样收藏页会显示过期热度。
    """
    out: list[int] = []
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk.isdigit():
            continue
        value = int(chunk)
        if value > 0 and value not in out:
            out.append(value)
    return out[:cap]


def list_memes(
    session: Session,
    *,
    filter_key: str = "all",
    search: str = "",
    sort: str = "hotness",
    limit: int | None = None,
    offset: int = 0,
    scope: str = "board",
    ids: list[int] | None = None,
    tag: str = "",
    collection: str = "",
) -> dict[str, Any]:
    """scope=board 是热榜口径（还要过"活着"门槛）；scope=all 是完整梗库。"""
    rows = _load_rows(session)
    library_total = len(rows)
    gated = 0
    if scope != "all":
        kept = _board_rows(session, rows)
        gated = library_total - len(kept)
        rows = kept

    if ids:
        wanted = set(ids)
        rows = [row for row in rows if row[0].id in wanted]

    stages = HOME_FILTERS.get(filter_key)
    if stages:
        rows = [row for row in rows if row[2].stage in stages]

    # 主题标签：直接看梗身上标的 key（LLM 打标，见 services/meme/tagging.py）
    if tag:
        rows = [row for row in rows if tag in (row[0].tags or [])]

    # 算法专题：成员由规则现算（本月新梗 / 年度爆款），见 services/meme/collections.py。
    # 传当前可选集合，让专题规则与列表口径取交集——两套口径不交集的话，
    # 会出现「筛选行写着 74、点进去只有 46」这种对不上的数。
    if collection:
        eligible = {row[0].id for row in rows}
        members = set(collection_member_ids(session, collection, eligible_ids=eligible))
        rows = [row for row in rows if row[0].id in members]

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
        "scope": "all" if scope == "all" else "board",
        # 门槛挡掉了多少、库里总共有多少，接口要如实说，否则用户以为梗库就这么点
        "library_total": library_total,
        "gated_out": gated,
        "items": [
            card_payload(meme, hotness, lifecycle, real_cover=covers.get(meme.id, ""))
            for meme, hotness, lifecycle in page
        ],
    }


# 复算逐日阶段时的取行上限：要"尽可能长的历史"，但要有个明确的数
_ALL_DAYS = 400


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
    # 逐日阶段要在**更长**的历史上复算才能与管线判定一致（管线用的是 30 天窗口），
    # 只拿 7/30 天去算会让柱子颜色和右上角徽章打架——梗史馆踩过这个坑。
    # 这里另外取全量日行只为复算，展示的仍然是 window 天那一段。
    #
    # 延迟导入：`history` 那边要用本模块的 fresh_cert_ids / thumbnail_for，
    # 顶层互相 import 会成环；本文件已经 import 了它的一半，所以只能在这里引。
    from .history import stage_path_for_rows

    stage_by_day = stage_path_for_rows(_daily_rows(session, meme_id, _ALL_DAYS))
    points = [
        {
            "date": row.stat_date.isoformat(),
            "hotness": round(row.hotness, 1),
            "view": row.view,
            "discussion": row.discussion,
            "video_count": row.video_count,
            "creator_count": row.creator_count,
            # false = 这天接口给了个空壳，画图上必须跟"真的是 0"分开画
            "observed": row.observed is not False,
            # 这天处于哪个阶段：热度柱按它上色，与梗史馆同一份复算结果
            "stage": stage_by_day.get(row.stat_date, ""),
        }
        for row in rows
    ]
    observed_days = sum(1 for point in points if point["observed"])
    return {
        "window": window,
        "observed_days": observed_days,
        "coverage": round(observed_days / len(points), 2) if points else 0.0,
        "points": points,
    }


def kept_videos(
    session: Session, meme: Meme, limit: int | None = None, *, sort: str = "rank"
) -> list[Video]:
    """按播放量取"确实还在讲这个梗"的视频（过相关性筛，不拿错片简介拼介绍）。

    ``sort``：``rank`` = B 站搜这个词的默认（综合）排序名次，``view`` = 播放量。
    库里一条名次都没有时（演示梗、或还没抓过综合排序）如实退回播放量，
    不返回一个看起来排过、其实按创建顺序摆着的列表。
    """
    videos = list(
        session.scalars(
            select(Video).where(Video.meme_id == meme.id).order_by(Video.view.desc())
        )
    )
    kept, _ = match_videos(MemeTerms.from_meme(meme), videos)
    if sort == "view" or not any(video.search_rank for video in kept):
        kept.sort(key=lambda video: video.view, reverse=True)
    else:
        # 有名次的在前；同一名次（不该出现）或没名次的按播放量兜底
        kept.sort(key=lambda video: (
            video.search_rank is None, int(video.search_rank or 0), -int(video.view or 0)
        ))
    return kept[:limit] if limit else kept


def video_sort_state(kept: list[Video], requested: str) -> tuple[str, str]:
    """请求的排序能不能真做到：返回 (实际生效的排序, 说明)。"""
    if requested != "rank":
        return "view", "按播放量从高到低。"
    if not any(video.search_rank for video in kept):
        return "view", "这条梗还没抓到 B 站综合排序的名次，先按播放量排。"
    return "rank", "按你在 B 站搜这个词看到的默认（综合）顺序排，名次取自过滤前的原始位置。"


def video_items(videos: list[Video]) -> list[dict[str, Any]]:
    return [
        {
            **video.to_dict(include_meme=False),
            "cover": _https(video.cover),
            "duration_text": _duration_text(video.duration_seconds),
            "view_text": _compact(video.view),
            "danmaku_text": _compact(video.danmaku),
        }
        for video in videos
    ]


def video_page(
    session: Session, meme: Meme, *, limit: int = 20, offset: int = 0, sort: str = "rank"
) -> dict[str, Any]:
    """相关视频分页。

    ``total`` 必须是"过完相关性筛之后还剩多少条"，不是本次请求的条数：
    前端拿它决定"还有没有下一页"，之前把 limit 当 total 返回，
    125 条的梗会被显示成 3 条，用户根本翻不到后面的内容。
    """
    kept = kept_videos(session, meme, sort=sort)
    applied, sort_note = video_sort_state(kept, sort)
    return {
        "items": video_items(kept[offset : offset + limit]),
        "total": len(kept),
        "offset": offset,
        "sort": sort,
        "sort_applied": applied,
        "sort_label": "B站默认排序" if applied == "rank" else "播放量",
        # 两段都是完整子句，用分号接——拼成"再这条梗还没抓到…"这种病句没法看
        "note": "已按相关性过滤（标题/简介/标签命中梗名或别名才算）；" + sort_note,
    }


def video_payloads(
    session: Session, meme: Meme, limit: int | None = 4, *, sort: str = "rank"
) -> list[dict[str, Any]]:
    return video_items(kept_videos(session, meme, limit, sort=sort))


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


def meme_transcripts(session: Session, meme: Meme) -> list[VideoTranscript]:
    """这个梗能用到的字幕：本梗名下的 + 双 UP 认证视频名下的。

    一条解说视频可能被两个梗共用（字幕按 bvid 存，归属第一个抓到它的梗），
    只查 meme_id 会让第二个梗看不见已经抓好的原文。
    """
    bvids = [cert.bvid for cert in meme.certifications if cert.bvid]
    conditions = [VideoTranscript.meme_id == meme.id]
    if bvids:
        conditions.append(VideoTranscript.bvid.in_(bvids))
    return list(
        session.scalars(
            select(VideoTranscript)
            .where(or_(*conditions))
            .order_by(VideoTranscript.chars.desc())
        )
    )


# 介绍这块最多摊开多少相关视频：喂给 AI 的材料要够宽，展示的摘录只要够用
MATERIAL_VIDEO_LIMIT = 12


@dataclass(frozen=True)
class IntroContext:
    """介绍这一块的全部输入：字幕、摘录、相关视频、AI 材料。

    「读缓存」与「生成」必须用**完全一样**的输入：材料指纹是 AI 摘要的缓存键，
    两边各建一次材料就会因为细节不同而算出不同的指纹，页面将永远查不到刚生成的那条。
    所以只在这里建一次，两边共用。
    """

    transcripts: list[VideoTranscript]
    block: dict[str, Any] | None
    videos: list[Video]
    material: str

    @property
    def material_version(self) -> str:
        return material_digest(self.material)

    @property
    def transcript_excerpt(self) -> str:
        return self.block["excerpt"] if self.block else ""


def intro_context(session: Session, meme: Meme) -> IntroContext:
    rows = meme_transcripts(session, meme)
    block = transcript_block(meme, meme.certifications, rows)
    videos = kept_videos(session, meme, MATERIAL_VIDEO_LIMIT)
    material = build_material(
        meme,
        meme.certifications,
        videos,
        transcript_excerpt=block["excerpt"] if block else "",
    )
    return IntroContext(transcripts=rows, block=block, videos=videos, material=material)


def intro_payload(session: Session, meme: Meme) -> dict[str, Any]:
    """详情页的「这个梗是什么」：人工介绍 > AI 摘要 > 字幕原文 > 真实证据原文 > 显式空态。

    AI 那两档都**只读缓存**，不在详情请求里现调模型——那会让页面为一段文案等几十秒。
    """
    ctx = intro_context(session, meme)
    summary = (
        read_cached_summary(session, meme_id=meme.id, version=ctx.block["version"])
        if ctx.block
        else None
    )
    ai_intro = read_cached_ai_intro(session, meme_id=meme.id, version=ctx.material_version)
    return compose_intro(
        meme,
        meme.certifications,
        ctx.videos,
        ctx.transcripts,
        summary,
        ai_intro=ai_intro,
    )


def generate_intro(
    session: Session, meme: Meme, *, refresh: bool = False
) -> dict[str, Any] | None:
    """生成/刷新 AI 摘要（**会打模型**，一次调用几十秒）。

    只有前端那个「重新生成」按钮和 ``app.scripts.generate_intros`` 走这里；
    详情接口永远不调它。
    """
    ctx = intro_context(session, meme)
    return generate_meme_intro(
        session,
        meme,
        certifications=meme.certifications,
        videos=ctx.videos,
        transcript_excerpt=ctx.transcript_excerpt,
        force_refresh=refresh,
    )


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
        "intro": intro_payload(session, meme),
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
    library_rows = _load_rows(session)
    # 分类清单的计数只数「梗库里的梗」，与列表接口取同一个集合——
    # 否则筛选行上的数字与点进去的条数会对不上。
    library_ids = {meme.id for meme, _, _ in library_rows}
    # 热榜口径 = 梗库再过滤一道"活着"门槛，并且只看最新准入池（解说证据在认证窗口内）。
    # 两个数都要给出去：只报热榜数会让人以为梗库就这么点。
    rows = _board_rows(session, library_rows)
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
    # 候选 = 两位 UP 主都没介绍过（发现层并集之外），只能靠人工投稿进库。
    # 只介绍过一位的梗已经算入池，不能跟"没人做过"的混成一类。
    candidate_count = len(
        list(
            session.scalars(
                select(Meme.id).where(
                    Meme.encyclopedia_confirmed.is_(False),
                    Meme.guide_confirmed.is_(False),
                )
            )
        )
    )
    # 上次刷新的摘要：界面要能说"这套数是几点、由谁、怎么刷出来的"。
    # 只读一个 json 文件，不碰 B 站；没自动刷过时给 null 而不是假装刚刷过。
    from app.services.refresh import last_report, schedule_info

    report = last_report()
    refresh_summary = None
    if report:
        refresh_summary = {
            "at": report.get("finished_at"),
            "trigger": report.get("trigger"),
            "mode": report.get("mode"),
            "exit_code": report.get("exit_code"),
            "collected": (report.get("collect") or {}).get("collected"),
            "targets": (report.get("collect") or {}).get("targets"),
            "failed": (report.get("collect") or {}).get("failed"),
            "skipped_demo": (report.get("collect") or {}).get("skipped_demo"),
            "data_through": report.get("data_through"),
        }

    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "refresh": {"last": refresh_summary, "schedule": schedule_info()},
        "environment": settings.environment,
        "data_source": site_source,
        "is_demo": site_is_demo,
        "configured_source": settings.data_source,
        "data_updated_at": latest.isoformat() if isinstance(latest, datetime) else latest,
        "data_through": data_through.isoformat() if data_through else None,
        "data_lag_days": lag_days,
        "certified_count": total_certified,
        "library_count": len(library_rows),
        "gated_out": len(library_rows) - total_certified,
        "candidate_count": candidate_count,
        "window_days": settings.analysis_window_days,
        "source_breakdown": source_breakdown,
        "filters": [
            {"key": key, "label": HOME_FILTER_LABELS[key]}
            for key in ("all", "hot", "taking_off", "receding")
        ],
        # 分类：主题标签（LLM 打标）与算法专题（规则现算）。
        # 计数与列表都基于 library_ids，保证「筛选行上的数字」与「点进去看到的条数」一致——
        # 一个来自缓存一个现算的话，点进去对不上就会显得数据不可信。
        "tags": tag_summary(session, eligible_ids=library_ids),
        "collections": collection_summary(session, eligible_ids=library_ids),
        "lifecycle_stages": [
            {"key": stage, "label": LIFECYCLE_LABELS[stage], "emoji": LIFECYCLE_EMOJI[stage]}
            for stage in LIFECYCLE_STAGES
        ],
        "transparency": {
            "data_platform": "Bilibili",
            "certification": ["梗百科", "梗指南"],
            "certification_rule": (
                f"发现层并集准入：{ENCYCLOPEDIA.name}为主、{GUIDE.name}补，"
                f"任一 UP 主在最近 {settings_cert_window_days()} 天内真实介绍过即入池；"
                "两位都介绍过标记为「双 UP 认证」，只有一位则标明是哪一位"
            ),
            "cert_window_days": settings_cert_window_days(),
            "board_gate": (
                (
                    f"热榜只收「活着」且「在最新池里」的梗：最近 {settings_cert_window_days()} 天内"
                    f"有真实解说证据（发现层并集的证据行）才算池内；过气（考古区）不上榜，"
                    f"且近 7 天头部播放须 ≥{BOARD_MIN_RECENT_VIEW:,}"
                    "（不用有内容天数卡，避免误杀琵琶曲这种脉冲型梗）"
                    + (
                        "" if settings.leaderboard_require_fresh_cert
                        else "；注意最新池闸门已被关掉（LEADERBOARD_REQUIRE_FRESH_CERT=false），"
                             "此时解说证据出窗的老梗也会回到榜上"
                    )
                )
                if settings.leaderboard_gate else "上榜门槛已关闭（LEADERBOARD_GATE=false）"
            ),
            "board_gate_on": bool(settings.leaderboard_gate),
            "hotness_algorithm": "赶梗潮自定义热度指数（0-100，五因子加权）",
            "lifecycle_algorithm": "时间序列 + 阈值规则，不由 LLM 决定",
            # 观测闸门也要界面自解释：用户看得见"什么时候我们拒绝给结论"
            "coverage_rule": (
                "B 站的「没结果」要分开看：返回体只有 v_voucher 的是**被限流吞掉**，"
                "我们没看清；连续几次都空的日子也只敢记成「未观测」——那可能是 B 站没给，"
                "不等于当天没人做这个梗。只有「接口给了行、但都跟这个梗无关」才算"
                "**观测到当天零活动**。未观测的日子不计入零活动，也不参与趋势；"
                f"近 7 天真正观测到不足 {LIFECYCLE_THRESHOLDS.min_observed_days} 天时，"
                "算法拒绝给生命周期与赶梗结论，只报「数据不足」。热度分数照给——"
                "那是存量水平，跨梗同一把尺子；被洞影响的是「在涨还是在退」这种时间轴比较。"
                "（限流是会话级累积状态、处罚窗口数小时级；实测配了 BILI_COOKIE 之后"
                "30 天窗口能观测到 29~30 天，匿名则几百次请求就进处罚。）"
            ) if site_source == "bilibili" else "演示数据不涉及接口抖动，无观测闸门。",
            # 介绍这一段的来源也要能被用户查到底：四档优先级 + 谁改写的，界面自解释
            "intro_rule": (
                "梗介绍的优先级：人工撰写 > 解说视频字幕原文 > 解说视频标题与简介原文 > 显式「暂无介绍」。"
                "后三档都不由系统写句子：字幕选段只按「出自/来历/这个梗」这类说法把原句挑出来拼接，"
                "一个字都不改写；字幕要 BILI_COOKIE 才抓得到（实测匿名请求只返回空字幕轨）。"
                "AI 只做缩短，且摘要里的数字与专名必须能在字幕原文里逐字找到，否则退回原文。"
            ),
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
