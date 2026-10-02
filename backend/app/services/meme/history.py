"""梗史馆：近 N 天内入池的梗，逐日热度 + 历史周期画像。

产品原有两条读侧口径回答的都是「今天玩什么」：

* 热榜（``scope=board``）——过气不进、近 7 天头部播放不够不进；
* 梗库（``scope=all``）——过了发现层准入的全量。

两者都把「一个梗怎么走到今天」折叠成了一个当前态（热度 + 阶段），看不到过程。
这一层补的是复盘：把最近 N 天（默认 90，与认证窗口同宽）内**有真实解说证据**
的梗捞出来，逐个还原它在观测窗口里的逐日热度与阶段轨迹，并给出周期画像
（峰值日 / 距峰天数 / 半衰期 / 周期类型）。

三条边界，与项目其它口径保持一致：

1. **入池口径直接复用** :func:`app.services.meme.query.fresh_cert_ids`，不另起一套：
   认证窗口内（默认 90 天）有 ``data_source='bilibili'`` 且带 ``published_at``
   的真实证据，才算"这三个月里的梗"。
2. **周期全部由逐日序列算出来**，LLM 不参与；逐日阶段复用
   :mod:`app.analytics.lifecycle` 的同一套阈值，不新造判定逻辑。
3. **观测洞不当零活动**：``observed=False`` 的日子不进任何趋势判断，只用来标覆盖度；
   近 7 天真正观测不足 ``min_observed_days`` 时，那一天的阶段直接记 ``insufficient``。

已知限制（页面必须如实标出来，不能靠"看起来完整"糊过去）：库里逐日序列目前只有
一个月的长度（2026-08-28 起、约 34 天）。**入池日早于序列起点**的梗，其周期左端被截断，
所以每条都带 ``obs_from`` 与 ``truncated`` 两个字段供界面说明。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean, median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.hotness import compute_hotness
from app.analytics.lifecycle import build_input, classify
from app.analytics.series import DayPoint, Series
from app.config import LIFECYCLE_EMOJI, LIFECYCLE_LABELS, get_logger, settings
from app.models import (
    HotnessSnapshot,
    LifecycleSnapshot,
    Meme,
    MemeCertification,
    MemeDailyStats,
)

from .certification import cert_label, certified_by, settings_cert_window_days
from .query import covers_by_meme, fresh_cert_ids, thumbnail_for

log = get_logger(__name__)

# 历史窗口默认与认证窗口同宽：问的是"这三个月里被介绍过的梗"
HISTORY_DAYS = 90

# 周期类型：只用逐日序列就能判，四个都带明确的判定条件（见 _classify_cycle）
CYCLE_LABELS = {
    "no_data": "数据不足",
    "rising": "仍在爬升",
    "pulse": "脉冲型",
    "long_tail": "长尾型",
}
CYCLE_EMOJI = {
    "no_data": "⏳",
    "rising": "📈",
    "pulse": "⚡",
    "long_tail": "🌊",
}
CYCLE_HINTS = {
    "no_data": "观测窗里一天都没真的看到内容，不给周期结论",
    "rising": "峰值落在观测窗末端（最近 3 天内），当前仍贴着峰值",
    "pulse": "见峰后 5 天内热度腰斩——起得快、落得也快",
    "long_tail": "见峰后 5 天仍未腰斩，热度在长尾上拖着",
}
# 峰值算"在窗口末端"的容差（天）：3 天内见峰且仍在 85% 峰位 = 还在爬
RISING_TAIL_DAYS = 3
RISING_KEEP_RATIO = 0.85
# 半衰期短于这个天数算"脉冲型"
PULSE_HALF_LIFE_DAYS = 5

SORTS = {"recent", "peak", "hotness", "off_peak", "name"}
SORT_LABELS = {
    "recent": "最近入池",
    "peak": "峰值热度",
    "hotness": "当前热度",
    "off_peak": "距峰最远",
    "name": "名称",
}


@dataclass(frozen=True)
class CycleDay:
    """观测窗里的一天（缺失日补 0 且 observed=False）。"""

    day: date
    hotness: float
    view: int
    video_count: int
    discussion: int
    observed: bool


# --------------------------------------------------------------------------- #
# 序列重建
# --------------------------------------------------------------------------- #
def _build_series(
    rows: list[MemeDailyStats], window_days: int | None
) -> tuple[list[CycleDay], list[DayPoint]]:
    """把稀疏的日行补成连续序列。

    与 :meth:`Series.from_stats` 同规则（缺失日补 0、``observed=False``），
    区别是这里额外保留**当日热度**——周期画像要用它，而 ``DayPoint`` 里没有这个字段。

    ``window_days`` 留空（None / 0）= **用满库里有多少逐日序列就画多长**。
    复盘本来就该尽量看全过程，砍到 7/30 天是首页那套"看当下"的口径。
    """
    if not rows:
        return [], []
    by_day = {row.stat_date: row for row in rows}
    end = max(by_day)
    start = min(by_day)
    if window_days:
        start = max(end - timedelta(days=window_days - 1), start)

    days: list[CycleDay] = []
    points: list[DayPoint] = []
    cursor = start
    while cursor <= end:
        row = by_day.get(cursor)
        # 库里没有这一行 = 这天没被观测；有行但 observed=False = 观测了但接口给了空壳。
        # 两者都不是"当天没内容"，任何趋势结论都不许拿它们当零活动。
        observed = bool(row is not None and row.observed is not False)
        days.append(
            CycleDay(
                day=cursor,
                hotness=float(row.hotness or 0.0) if row else 0.0,
                view=int(row.view or 0) if row else 0,
                video_count=int(row.video_count or 0) if row else 0,
                discussion=int(row.discussion) if row else 0,
                observed=observed,
            )
        )
        points.append(
            DayPoint(
                day=cursor,
                video_count=days[-1].video_count,
                creator_count=int(row.creator_count or 0) if row else 0,
                view=days[-1].view,
                like=int(row.like or 0) if row else 0,
                coin=int(row.coin or 0) if row else 0,
                favorite=int(row.favorite or 0) if row else 0,
                reply=int(row.reply or 0) if row else 0,
                danmaku=int(row.danmaku or 0) if row else 0,
                observed=observed,
            )
        )
        cursor += timedelta(days=1)
    return days, points


def stage_path_for_rows(
    rows: list[MemeDailyStats], *, window_days: int | None = None
) -> dict[date, str]:
    """按管线口径复算逐日阶段，返回 ``{日期: 阶段}``。

    详情页的热度柱要用它给每根柱子上色，梗史馆的轨迹也用它——**必须是同一份实现**，
    否则同一只梗在两个页面里的颜色会对不上。
    注意：调用方要给**尽量长的历史**（详见 `_stage_path` 的说明），只给 7 天会让
    复算出来的阶段与右上角徽章打架。
    """
    days, points = _build_series(rows, window_days)
    if not days:
        return {}
    stages = _stage_path(days, points, window=settings.analysis_window_days)
    return {day.day: stage for day, stage in zip(days, stages)}


def _stage_path(days: list[CycleDay], points: list[DayPoint], *, window: int) -> list[str]:
    """逐日阶段：把当前态的一个阶段，还原成一条阶段轨迹。

    判定协议**刻意与管线保持一致**，否则同一行里"当前阶段"与最后一格的颜色会打架：
    每一天都在"截至那天的最近 ``window`` 天"上跑同一套阈值（``window`` 取
    ``ANALYSIS_WINDOW_DAYS``，也就是管线重算快照时用的那个窗口），
    热度用 ``compute_hotness``（滚动 7 天），增长用它的复合增长率，
    峰值参考同一窗口内的逐日热度。

    这样最后一天算出来的阶段与 ``lifecycle_snapshots`` 里的当前阶段是同一次判定，
    页面不需要解释"为什么右上角写上升、最后一格是黄的"。
    """
    hotness = [day.hotness for day in days]
    out: list[str] = []
    for index in range(len(days)):
        start = max(0, index - window + 1)
        prefix = Series(meme_id=0, points=points[start : index + 1])
        current = compute_hotness(prefix)
        result = classify(
            build_input(
                prefix,
                heat=current.score,
                growth=current.metrics.get("growth"),
                daily_hotness=hotness[start : index + 1],
            )
        )
        out.append(result.stage)
    return out


# --------------------------------------------------------------------------- #
# 周期画像
# --------------------------------------------------------------------------- #
def _empty_cycle(days: list[CycleDay]) -> dict[str, Any]:
    return {
        "cycle": "no_data",
        "cycle_label": CYCLE_LABELS["no_data"],
        "cycle_emoji": CYCLE_EMOJI["no_data"],
        "cycle_hint": CYCLE_HINTS["no_data"],
        "obs_from": days[0].day.isoformat() if days else None,
        "obs_to": days[-1].day.isoformat() if days else None,
        "window_days": len(days),
        "observed_days": 0,
        "coverage": 0.0,
        "active_days": 0,
        "peak_date": None,
        "peak_hotness": 0.0,
        "current_hotness": round(days[-1].hotness, 1) if days else 0.0,
        "off_peak": 0.0,
        "days_since_peak": None,
        "half_life_days": None,
        "rise_days": None,
        "window_view": 0,
        "window_discussion": 0,
    }


def _classify_cycle(
    *, total: int, peak_index: int, current_ratio: float, half_life: int | None
) -> str:
    """周期类型。规则短、可复述，尽量不制造需要解释的黑箱。"""
    if peak_index >= total - RISING_TAIL_DAYS and current_ratio >= RISING_KEEP_RATIO:
        return "rising"
    if half_life is not None and half_life <= PULSE_HALF_LIFE_DAYS:
        return "pulse"
    return "long_tail"


def _cycle(days: list[CycleDay]) -> dict[str, Any]:
    """一个梗的周期画像（全部来自逐日序列，观测洞一律不参与）。"""
    if not days:
        return _empty_cycle(days)
    seen = [day for day in days if day.observed]
    if not seen:
        return _empty_cycle(days)

    total = len(days)
    peak = max(seen, key=lambda day: day.hotness)
    if peak.hotness <= 0:
        return _empty_cycle(days)
    peak_index = days.index(peak)
    current = days[-1]
    current_ratio = current.hotness / peak.hotness if peak.hotness > 0 else 0.0

    # 半衰期：从峰值日起，热度首次跌到峰位一半用了几天。
    # 一直没跌到 = None，含义是"仍在高位"，不是"没有数据"——界面要分开说。
    half_life: int | None = None
    for index in range(peak_index + 1, total):
        if days[index].observed and days[index].hotness <= peak.hotness * 0.5:
            half_life = (days[index].day - peak.day).days
            break

    # 爬升天数：从"第一次真的看到内容"到峰值日。
    first_active = next(
        (index for index, day in enumerate(days) if day.video_count > 0 or day.view > 0), None
    )
    rise_days = peak_index - first_active if first_active is not None and peak_index >= first_active else None

    cycle = _classify_cycle(
        total=total, peak_index=peak_index, current_ratio=current_ratio, half_life=half_life
    )
    observed_days = len(seen)
    return {
        "cycle": cycle,
        "cycle_label": CYCLE_LABELS[cycle],
        "cycle_emoji": CYCLE_EMOJI[cycle],
        "cycle_hint": CYCLE_HINTS[cycle],
        "obs_from": days[0].day.isoformat(),
        "obs_to": days[-1].day.isoformat(),
        "window_days": total,
        "observed_days": observed_days,
        "coverage": round(observed_days / total, 3),
        "active_days": sum(1 for day in days if day.video_count > 0 or day.view > 0),
        "peak_date": peak.day.isoformat(),
        "peak_hotness": round(peak.hotness, 1),
        "current_hotness": round(current.hotness, 1),
        # 离开峰值的比例：0 = 正在峰上，0.4 = 只剩六成
        "off_peak": round(max(0.0, 1.0 - current_ratio), 3),
        "days_since_peak": (days[-1].day - peak.day).days,
        "half_life_days": half_life,
        "rise_days": rise_days,
        "window_view": sum(day.view for day in days if day.observed),
        "window_discussion": sum(day.discussion for day in days if day.observed),
    }


def _spark(days: list[CycleDay], stages: list[str]) -> list[dict[str, Any]]:
    """逐日轨迹：界面拿它画「热度条 + 阶段着色」，一格一天。"""
    return [
        {
            "date": day.day.isoformat(),
            "hotness": round(day.hotness, 1),
            "stage": stage,
            # false = 这天接口给了空壳：画空档，不能画成"热度 0"
            "observed": day.observed,
        }
        for day, stage in zip(days, stages)
    ]


# --------------------------------------------------------------------------- #
# 组装
# --------------------------------------------------------------------------- #
def _evidence_rows(session: Session, meme_ids: list[int], floor: datetime) -> dict[int, list[MemeCertification]]:
    """窗口内的真实解说证据，按 meme 分组（梗百科在前，与展示顺序一致）。"""
    if not meme_ids:
        return {}
    rows = session.scalars(
        select(MemeCertification)
        .where(
            MemeCertification.meme_id.in_(meme_ids),
            MemeCertification.data_source == "bilibili",
            MemeCertification.published_at >= floor,
        )
        .order_by(MemeCertification.role)
    )
    out: dict[int, list[MemeCertification]] = {}
    for row in rows:
        out.setdefault(row.meme_id, []).append(row)
    return out


def _evidences(rows: list[MemeCertification]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        item = row.to_dict()
        out.append(
            {
                "role": row.role,
                "up_name": row.up_name,
                "bvid": row.bvid,
                "video_title": row.video_title,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "linkable": bool(item.get("linkable")),
                "video_url": item.get("video_url") or "",
            }
        )
    return out


def _entry(
    meme: Meme,
    hotness: HotnessSnapshot | None,
    lifecycle: LifecycleSnapshot | None,
    rows: list[MemeDailyStats],
    certs: list[MemeCertification],
    *,
    window_days: int | None,
    cover: str,
) -> dict[str, Any]:
    days, points = _build_series(rows, window_days)
    stages = (
        _stage_path(days, points, window=settings.analysis_window_days) if days else []
    )
    cycle = _cycle(days)
    evidences = _evidences(certs)
    admitted = min(
        (row.published_at for row in certs if row.published_at), default=None
    )
    obs_from = days[0].day if days else None
    # 入池日早于观测窗起点 = 起步那段我们没看到。必须标出来，
    # 否则读者会以为"这个梗的爬升只花了 0 天"。
    truncated = bool(admitted and obs_from and admitted.date() < obs_from)

    return {
        "id": meme.id,
        "name": meme.name,
        "slug": meme.slug,
        "thumbnail": thumbnail_for(meme, cover),
        "stage": lifecycle.stage if lifecycle else "insufficient",
        "stage_label": lifecycle.stage_label if lifecycle else LIFECYCLE_LABELS["insufficient"],
        "emoji": lifecycle.emoji if lifecycle else LIFECYCLE_EMOJI["insufficient"],
        "catch_label": lifecycle.catch_label if lifecycle else "",
        "hotness": round(hotness.score, 1) if hotness else None,
        "cert_label": cert_label(meme),
        "certified_by": certified_by(meme),
        "double_certified": bool(meme.certified),
        "verification_state": meme.verification_state or "unverified",
        "admitted_at": admitted.isoformat() if admitted else None,
        "evidences": evidences,
        "truncated": truncated,
        "has_metrics": hotness is not None and lifecycle is not None,
        **cycle,
        "spark": _spark(days, stages),
    }


def _summary(
    items: list[dict[str, Any]], *, pool: int, days: int, window_days: int | None
) -> dict[str, Any]:
    cycles = [item["cycle"] for item in items]
    by_cycle = [
        {
            "key": key,
            "label": CYCLE_LABELS[key],
            "emoji": CYCLE_EMOJI[key],
            "hint": CYCLE_HINTS[key],
            "count": cycles.count(key),
        }
        for key in ("rising", "pulse", "long_tail", "no_data")
    ]
    off_peaks = [item["days_since_peak"] for item in items if item["days_since_peak"] is not None]
    rises = [item["rise_days"] for item in items if item["rise_days"] is not None]
    half_lives = [item["half_life_days"] for item in items if item["half_life_days"] is not None]
    obs_from = min((item["obs_from"] for item in items if item["obs_from"]), default=None)
    obs_to = max((item["obs_to"] for item in items if item["obs_to"]), default=None)
    truncated = sum(1 for item in items if item["truncated"])
    peaks = [item for item in items if item["peak_hotness"] > 0]
    leader = max(peaks, key=lambda item: item["peak_hotness"], default=None)
    # 观测窗长度按**实际画出来的格子数**报，而不是把请求参数原样回吐：
    # 库里序列比请求窗口短时（现在就是这样），报参数会让页面把 30 天写成 90 天。
    span = max((len(item["spark"]) for item in items), default=0)

    return {
        "pool": pool,
        "returned": len(items),
        "days": days,
        "window_days": span,
        "window_days_requested": window_days or 0,
        "obs_from": obs_from,
        "obs_to": obs_to,
        "truncated_count": truncated,
        "with_series": sum(1 for item in items if item["observed_days"] > 0),
        "no_metrics": sum(1 for item in items if not item["has_metrics"]),
        "by_cycle": by_cycle,
        "by_stage": _stage_counts(items),
        "median_days_since_peak": round(median(off_peaks), 1) if off_peaks else None,
        "avg_days_since_peak": round(mean(off_peaks), 1) if off_peaks else None,
        "avg_rise_days": round(mean(rises), 1) if rises else None,
        "avg_half_life_days": round(mean(half_lives), 1) if half_lives else None,
        "peak_leader": (
            {
                "id": leader["id"],
                "name": leader["name"],
                "peak_hotness": leader["peak_hotness"],
                "peak_date": leader["peak_date"],
            }
            if leader
            else None
        ),
    }


def _stage_counts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = ["explosive", "rising", "plateau", "receding", "sprouting", "obsolete", "insufficient"]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["stage"]] = counts.get(item["stage"], 0) + 1
    return [
        {
            "key": key,
            "label": LIFECYCLE_LABELS[key],
            "emoji": LIFECYCLE_EMOJI[key],
            "count": counts.get(key, 0),
        }
        for key in order
        if counts.get(key)
    ]


def _sort_items(items: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> Any:
        if sort == "recent":
            return item["admitted_at"] or ""
        if sort == "peak":
            return item["peak_hotness"]
        if sort == "hotness":
            return item["hotness"] if item["hotness"] is not None else -1
        if sort == "off_peak":
            return item["days_since_peak"] if item["days_since_peak"] is not None else -1
        return item["name"]

    reverse = sort != "name"
    return sorted(items, key=key, reverse=reverse)


def history_payload(
    session: Session,
    *,
    days: int | None = None,
    window_days: int | None = None,
    cycle: str = "",
    stage: str = "",
    cert: str = "",
    sort: str = "recent",
) -> dict[str, Any]:
    """组装梗史馆的完整返回。

    ``days`` 是**入池窗口**（哪些梗算"这三个月里的"），``window_days`` 是
    **观测窗口**（逐日序列取多少天）。两个窗口刻意分开：前者决定收录谁，
    后者决定看多长的轨迹，混在一起会导致"改一个参数看不出是哪儿变了"。
    """
    days = days or HISTORY_DAYS
    floors = datetime.now() - timedelta(days=days)
    pool_ids = sorted(fresh_cert_ids(session, days=days))
    pool_total = len(pool_ids)
    if not pool_ids:
        return _empty_payload(days=days, window_days=window_days, sort=sort)

    memes = {meme.id: meme for meme in session.scalars(select(Meme).where(Meme.id.in_(pool_ids)))}
    hotness = {
        row.meme_id: row
        for row in session.scalars(select(HotnessSnapshot).where(HotnessSnapshot.meme_id.in_(pool_ids)))
    }
    lifecycle = {
        row.meme_id: row
        for row in session.scalars(
            select(LifecycleSnapshot).where(LifecycleSnapshot.meme_id.in_(pool_ids))
        )
    }
    stats: dict[int, list[MemeDailyStats]] = {}
    for row in session.scalars(
        select(MemeDailyStats)
        .where(MemeDailyStats.meme_id.in_(pool_ids))
        .order_by(MemeDailyStats.meme_id, MemeDailyStats.stat_date)
    ):
        stats.setdefault(row.meme_id, []).append(row)
    certs = _evidence_rows(session, pool_ids, floors)
    covers = covers_by_meme(session)

    items = [
        _entry(
            memes[meme_id],
            hotness.get(meme_id),
            lifecycle.get(meme_id),
            stats.get(meme_id, []),
            certs.get(meme_id, []),
            window_days=window_days,
            cover=covers.get(meme_id, ""),
        )
        for meme_id in pool_ids
        if meme_id in memes
    ]

    # 筛选在服务端做，且**计数基于同一个集合**——否则筛选行写着 12、点进去 7 条，
    # 用户只会觉得数据不可信（这条教训在列表接口那边也踩过）。
    if cycle:
        items = [item for item in items if item["cycle"] == cycle]
    if stage:
        items = [item for item in items if item["stage"] == stage]
    if cert == "double":
        items = [item for item in items if item["double_certified"]]
    elif cert == "single":
        items = [item for item in items if not item["double_certified"]]

    items = _sort_items(items, sort)
    summary = _summary(items, pool=pool_total, days=days, window_days=window_days)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "days": days,
        # 顶层这个数报**实际画出来的天数**：库里序列只有一个月时，
        # 原样回吐请求参数会把"34 天"说成"90 天"。
        "window_days": summary["window_days"],
        "window_days_requested": window_days or 0,
        "sort": sort,
        "sort_label": SORT_LABELS.get(sort, ""),
        "filter": {"cycle": cycle, "stage": stage, "cert": cert},
        "summary": summary,
        "items": items,
        "rule": (
            f"入池看最近 {days} 天：任一梗解释 UP 主（梗百科 / 梗指南）在这段时间里"
            "有真实投稿证据（带 BV 号与发布时间）就算「这三个月里的梗」，"
            "两位都做过标双 UP 认证。周期只用逐日序列算，"
            "逐日阶段复用同一套阈值；接口返回的每一天都带 observed 标记，"
            "接口给空壳的日子不参与任何趋势判断。"
            f"（当前认证窗口 {settings_cert_window_days()} 天）"
        ),
    }


def _empty_payload(*, days: int, window_days: int | None, sort: str) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "days": days,
        "window_days": 0,
        "window_days_requested": window_days or 0,
        "sort": sort,
        "sort_label": SORT_LABELS.get(sort, ""),
        "filter": {"cycle": "", "stage": "", "cert": ""},
        "summary": _summary([], pool=0, days=days, window_days=window_days),
        "items": [],
        "rule": f"最近 {days} 天里没有任何一位 UP 主的真实解说证据，梗史馆为空。",
    }
