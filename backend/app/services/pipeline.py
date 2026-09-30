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
    MemeCertification,
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


def _quality(row: MemeDailyStats) -> tuple[int, int, int]:
    """同一天两次采集谁更好：**先看到没看到**，再看头部样本条数，最后看合计播放量。

    第一位是后加的：B 站搜索抖动会让一次采集把有内容的日子返回成空壳，
    如果只比 video_count，空壳 (0,0) 和"当天真的没人做"的 (0,0) 一样好，
    于是新采的一次空返回就能把上次真正观测到的那天覆盖掉。
    """
    return (
        1 if getattr(row, "observed", True) else 0,
        int(row.video_count or 0),
        int(row.view or 0),
    )


def split_daily_stats(
    session: Session, meme: Meme, incoming: list[MemeDailyStats], source: str
) -> tuple[list[MemeDailyStats], int]:
    """已经过完的那一天，只保留"更好的一次观测"，另一些日子用新采的。

    B 站对同一个词、同一天两次返回的头部 20 条差别可以很大（接口抖动 / 风控降级），
    而那天到底有哪些头部视频是既定事实。相加会把同一批视频算两遍，
    直接替换又会让"琵琶曲 44.2 分 → 0 分"这种纯抖动看起来像热度崩了。
    所以按天取更好的一次：样本更多的那天沿用旧数据，其余日子照常更新。
    """
    previous = {
        row.stat_date: row
        for row in session.scalars(
            select(MemeDailyStats).where(
                MemeDailyStats.meme_id == meme.id, MemeDailyStats.data_source == source
            )
        )
    }
    kept: list[MemeDailyStats] = []
    reuse = 0
    for row in incoming:
        old = previous.get(row.stat_date)
        if old is not None and _quality(old) > _quality(row):
            reuse += 1
            continue          # 旧的那次样本更多，这一天的行不动
        kept.append(row)
    return kept, reuse


def purge_previous_series(session: Session, meme: Meme, source: str, overwrite_days: set) -> None:
    """只删本次真正要覆盖的那几天；其他数据源的行一律清掉（演示数据不进真实序列）。

    原来这里是"删掉 keep_days 之外的所有行"，等于把没被重采的历史一起删——
    跑一次 ``--days 1`` 就会把 30 天序列砍成 1 天，滚动窗口外的历史也永远留不下。
    增量日更必须先修这条：只动本次覆盖到的日期。
    """
    session.query(MemeDailyStats).filter(
        MemeDailyStats.meme_id == meme.id, MemeDailyStats.data_source != source
    ).delete(synchronize_session=False)
    if overwrite_days:
        session.query(MemeDailyStats).filter(
            MemeDailyStats.meme_id == meme.id,
            MemeDailyStats.data_source == source,
            MemeDailyStats.stat_date.in_(overwrite_days),
        ).delete(synchronize_session=False)
    session.query(Video).filter(
        Video.meme_id == meme.id, Video.data_source != source
    ).delete(synchronize_session=False)
    session.flush()


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
        # 没有时间序列就没有算分的依据：把旧快照一起撤掉。
        # 否则这个梗会带着上一版的分数继续留在榜单上，等于用已经不存在的数据说话。
        removed = _drop_snapshots(session, meme.id)
        log.info(
            "梗「%s」暂无时间序列数据，%s",
            meme.name, "已撤下旧的热度/生命周期快照" if removed else "跳过",
        )
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


def _drop_snapshots(session, meme_id: int) -> int:
    """撤下某个梗的热度与生命周期快照，返回删除行数。"""
    from app.models import LifecycleSnapshot

    # 不关会话同步：后面还会 session.get 这两张表，留着脏对象会"删不掉"
    removed = session.query(HotnessSnapshot).filter(HotnessSnapshot.meme_id == meme_id).delete()
    removed += session.query(LifecycleSnapshot).filter(LifecycleSnapshot.meme_id == meme_id).delete()
    return removed


def _delete_other_source(session, model, meme_id: int, source: str) -> int:
    """删掉这个梗身上不属于当前数据源的旧行，返回删除行数。"""
    rows = session.query(model).filter(model.meme_id == meme_id, model.data_source != source)
    count = rows.count()
    rows.delete(synchronize_session=False)
    return count


def _count_rows(
    session, model, meme_id: int, *, video_count_min: int | None = None, within: set | None = None
) -> int:
    """数行数。``within`` 给定时只数这批日期——增量日更之后库里会留着长历史，
    拿全表行数和"本次窗口内的行数"比会把正常累积说成"变薄了"。"""
    query = session.query(model).filter(model.meme_id == meme_id)
    if video_count_min is not None:
        query = query.filter(model.video_count >= video_count_min)
    if within is not None:
        query = query.filter(model.stat_date.in_(within))
    return query.count()


def _demo_only_ids(session: Session) -> set[int]:
    """纯演示梗：``data_source=mock``、状态不是 candidate、且在 B 站没有任何真实证据/视频。

    这类梗去搜 B 站只会拿到一堆无关结果（相关性筛全砍掉），白白吃几百个请求；
    真实模式下刷新应该跳过它们。两个例外：只要有一条真实证据就不算演示数据；
    手动投稿进来的 candidate 也不算——那是有人明确要求"去量它"，闸门不该管。
    """
    evidence = {
        row[0]
        for row in session.execute(
            select(MemeCertification.meme_id).where(MemeCertification.data_source == "bilibili")
        )
    }
    videos = {
        row[0]
        for row in session.execute(
            select(Video.meme_id).where(Video.data_source == "bilibili")
        )
    }
    return {
        meme.id
        for meme in session.scalars(
            select(Meme).where(Meme.data_source == "mock", Meme.status != MemeStatus.CANDIDATE)
        )
        if meme.id not in evidence and meme.id not in videos
    }


def collect_all(
    source: str | None = None,
    *,
    meme_ids: list[int] | None = None,
    limit: int | None = None,
    window_days: int | None = None,
    commit: bool = True,
    purge_when_empty: bool = False,
    include_candidates: bool = True,
    scope: str = "real",
) -> dict[str, object]:
    """跑一遍采集 → 清洗 → 匹配 → 聚合 → 指标计算。

    一个梗只保留一份数据来源：采集某个梗时会先清掉它原来的行，
    避免演示数据和真实数据混在同一个时间序列里被重复计数。

    采集范围默认含候选梗：闸门管的是"能不能上榜单"，不该管"能不能被度量"——
    否则手动加进来的真热梗连数据都拿不到。指标计算那一步仍然逐条过闸门。

    ``scope``：``real``（默认，真实模式下跳过纯演示梗）| ``all`` | ``library``
    （已有指标快照的）| ``board``（还在热榜上的，最省请求）。
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
        "kept_snapshots": 0,   # 本次空窗、沿用上次真实快照的梗数
        "thinned": 0,          # 本次采到但比上次薄的梗数
        "kept_better_days": 0,  # 沿用"更好的一次观测"的天数（同日不相加）
    }
    if not available:
        log.warning("数据源 %s 不可用：%s", collector.source, reason)
        return summary

    session = SessionLocal()
    try:
        # 覆盖"库里所有可分析的梗"，而不只是在线核验通过的——
        # 未核验的会带着 verification_state 如实出现在结果里
        stmt = select(Meme)
        if not include_candidates:
            stmt = stmt.where(Meme.status == MemeStatus.CERTIFIED)
        if meme_ids:
            stmt = stmt.where(Meme.id.in_(meme_ids))
        memes = list(session.scalars(stmt.order_by(Meme.id)))
        summary["scope"] = scope
        # 显式点名了梗就别再套 scope：调用方已经选好了目标，
        # 比如"只刷新这一个梗"，不该被"它是演示梗"挡掉。
        if meme_ids:
            summary["scope_note"] = f"按 ids 指定 {len(meme_ids)} 个梗，不套 scope"
        elif scope == "real" and collector.source == "bilibili":
            demo = _demo_only_ids(session)
            picked = [meme for meme in memes if meme.id in demo]
            memes = [meme for meme in memes if meme.id not in demo]
            summary["skipped_demo"] = len(picked)
            summary["scope_note"] = (
                f"跳过 {len(picked)} 个纯演示梗（B 站上不存在，搜了也只会拿到无关结果）"
                if picked else "库里没有纯演示梗需要跳过"
            )
        elif scope == "real":
            summary["scope_note"] = "演示数据源不区分真实/演示，scope=real 等同 all"
        elif scope in {"library", "board"}:
            from app.services.meme.query import on_board

            rows = list(session.execute(
                select(HotnessSnapshot, LifecycleSnapshot).join(
                    Meme, Meme.id == HotnessSnapshot.meme_id
                )
            ))
            have = {hot.meme_id for hot, _ in rows}
            if scope == "board":
                have &= {hot.meme_id for hot, life in rows if on_board(hot, life)}
            before = len(memes)
            memes = [meme for meme in memes if meme.id in have]
            summary["scope_note"] = f"{scope} 口径：{before} 个候选里留下 {len(memes)} 个"
        if limit:
            memes = memes[:limit]
        summary["targets"] = len(memes)

        # 硬风控连锁计数器：连续多少个梗撞上 BilibiliBlocked（412 / -352 / 需要 Cookie）。
        # 软限流（v_voucher）只是把结果吞掉，硬风控是风控升级的信号——
        # 这时继续跑既拿不到数据，又在给风控喂料，所以整批停下来更安全。
        block_streak = 0
        abort_after = int(getattr(settings, "collect_block_abort_after", 3) or 0)

        for meme in memes:
            try:
                bundle = collector.collect(meme, window_days=window)
            except BilibiliBlocked as exc:
                summary["failed"] = int(summary["failed"]) + 1
                block_streak += 1
                log.warning("梗「%s」采集中断：%s（连续第 %d 个）",
                            meme.name, exc, block_streak)
                if abort_after and block_streak >= abort_after:
                    summary["aborted"] = True
                    summary["abort_reason"] = (
                        f"连续 {block_streak} 个梗被 B 站硬风控拦下"
                        f"（最后一次：{exc}），已中止本次采集。"
                        f"继续跑只会加深风控；建议改用小号 Cookie 或降低频率后重试。"
                    )
                    log.error(summary["abort_reason"])
                    break
                continue
            block_streak = 0

            # 清洗 → 梗匹配：搜索结果里混着无关内容，先按相关性打分过滤，
            # 再用剩下的视频做每日聚合，否则统计会被无关样本灌水。
            terms = MemeTerms.from_meme(meme)
            kept, dropped = match_videos(terms, bundle.videos)
            dropped = dropped + [None] * int(getattr(bundle, "dropped_irrelevant", 0) or 0)
            if dropped:
                bundle.videos = kept
                summary["dropped"] = int(summary["dropped"]) + len(dropped)
                log.info("梗「%s」相关性过滤：保留 %s 条，剔除 %s 条", meme.name, len(kept), len(dropped))

            # 注意：不重算日统计。两个采集器都自己产出按日的统计
            # （演示器给完整曲线，B站器逐日区间查询），
            # 用"过滤后的视频列表"反推会把序列压断。

            if not bundle.videos:
                summary["empty"] = int(summary["empty"]) + 1
                if purge_when_empty:
                    # 只清掉"不是这个数据源"的旧行（演示数据不能混进真实数据），
                    # 同源的上一份真实快照必须留着：B站搜索对同一个词两次返回
                    # 结果差别很大，一次空窗就把上次采到的删掉等于越跑越薄。
                    stale_stats = _delete_other_source(session, MemeDailyStats, meme.id, collector.source)
                    stale_videos = _delete_other_source(session, Video, meme.id, collector.source)
                    kept_days = _count_rows(session, MemeDailyStats, meme.id)
                    summary["kept_snapshots"] = int(summary["kept_snapshots"]) + (1 if kept_days else 0)
                    meme.data_updated_at = datetime.now()
                    log.info(
                        "梗「%s」本次窗口内无相关视频：%s",
                        meme.name,
                        f"清掉 {stale_stats + stale_videos} 行演示数据"
                        if kept_days == 0
                        else f"保留上次真实快照（{kept_days} 行）",
                    )
                else:
                    log.info("梗「%s」窗口内没有可用视频，保留原数据", meme.name)
                continue

            covered = {row.stat_date for row in bundle.daily_stats}
            had_days = _count_rows(session, MemeDailyStats, meme.id, video_count_min=1, within=covered)
            new_days = sum(1 for stat in bundle.daily_stats if stat.video_count)
            # 已经过完的那一天只保留更好的一次观测：搜索抖动不该让一个梗从 44 分掉到 0 分
            incoming, reuse = split_daily_stats(session, meme, bundle.daily_stats, collector.source)
            overwrite = {row.stat_date for row in incoming}
            if had_days and new_days < had_days:
                summary["thinned"] = int(summary["thinned"]) + 1
                log.warning(
                    "梗「%s」本次只采到 %s 天内容（上次 %s 天），%s",
                    meme.name, new_days, had_days,
                    f"其中 {reuse} 天沿用更好的一次观测" if reuse else "本次更薄且无同日旧数据可留",
                )
            if reuse:
                summary["kept_better_days"] = int(summary["kept_better_days"]) + reuse
                log.info(
                    "梗「%s」有 %s 天沿用更好的一次观测（同日多次采集取头部样本更多的那次，不相加）",
                    meme.name, reuse,
                )

            purge_previous_series(session, meme, collector.source, overwrite)

            for stat in incoming:
                stat.meme_id = meme.id
                session.add(stat)
            # 沿用旧观测的那些天、以及本次窗口之外的历史，样本都已经在库里：
            # 按 bvid 去重，别把同一条视频存两遍
            stored = {
                row.bvid: row
                for row in session.scalars(
                    select(Video).where(
                        Video.meme_id == meme.id, Video.data_source == collector.source
                    )
                )
            }
            for video in bundle.videos:
                existing = stored.get(video.bvid)
                if existing is None:
                    video.meme_id = meme.id
                    session.add(video)
                    continue
                # 库里已有这条：只把新抓到的"B 站综合排序名次"补上。
                # 逐日头部样本采到的视频本来就没有名次，不补的话默认排序永远是空的。
                if video.search_rank and not existing.search_rank:
                    existing.search_rank = video.search_rank

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
