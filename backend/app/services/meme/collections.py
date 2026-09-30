"""算法专题：规则写死、每次现算，零人工维护。

与主题标签的分工很清楚：标签回答「这梗讲什么」，是语义判断，要模型；
专题回答「这批梗凭什么聚在一起」，规则完全客观（时间、热度），所以**不需要模型**——
算得出来的东西不该让模型去猜，猜了反而没法复现。

两个专题：

* **{月}新梗速递**——本月内通过双 UP 认证的梗，刚冒头的那批。
* **{年}年度现象级爆梗**——本年度内热度峰值最高的前 N 个。

「峰值」取的是逐日滚动热度（``meme_daily_stats.hotness``）在**本年度内**的最大值，
不是当前快照分数：年度爆款看的是它最高冲到过哪，而不是今天还剩多少。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import COLLECTIONS, MEME_TAGS, YEARLY_TOP_N
from app.models import HotnessSnapshot, Meme, MemeDailyStats, MemeStatus


def _anchor_day(meme: Meme) -> date | None:
    """这个梗「进入梗库」的那一天：优先认证时间，回退入库时间。"""
    for value in (meme.certified_at, meme.created_at):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
    return None


def month_label(today: date) -> str:
    return f"{today.year}年{today.month}月"


def year_label(today: date) -> str:
    return f"{today.year}"


def collection_labels(today: date | None = None) -> dict[str, str]:
    """专题展示名。含当前月份/年份，所以每次现算而不是存下来。"""
    today = today or date.today()
    mapping = {"month": month_label(today), "year": year_label(today)}
    return {spec.key: spec.label.format(**mapping) for spec in COLLECTIONS}


def _certified_ids(session: Session) -> list[int]:
    return [
        meme.id
        for meme in session.scalars(select(Meme).where(Meme.status == MemeStatus.CERTIFIED))
    ]


def _monthly_ids(session: Session, today: date) -> list[int]:
    """本月内进入梗库的梗。"""
    out: list[int] = []
    for meme in session.scalars(select(Meme).where(Meme.status == MemeStatus.CERTIFIED)):
        anchor = _anchor_day(meme)
        if anchor and anchor.year == today.year and anchor.month == today.month:
            out.append(meme.id)
    return out


def _yearly_ids(session: Session, today: date, *, limit: int = YEARLY_TOP_N) -> list[int]:
    """本年度内峰值热度最高的前 N 个（按峰值降序）。"""
    year_start = date(today.year, 1, 1)
    peak_rows = session.execute(
        select(MemeDailyStats.meme_id, func.max(MemeDailyStats.hotness))
        .where(MemeDailyStats.stat_date >= year_start)
        .group_by(MemeDailyStats.meme_id)
    ).all()
    peaks = {int(meme_id): float(value or 0.0) for meme_id, value in peak_rows}

    # 逐日热度还没算过的梗（刚入库、没跑过重算）退回当前快照分数：
    # 否则它连参与排名的机会都没有，而这不是"它不火"，是"我们还没算"。
    snapshot = {
        int(meme_id): float(score or 0.0)
        for meme_id, score in session.execute(
            select(HotnessSnapshot.meme_id, HotnessSnapshot.score)
        )
    }

    candidates = [
        (meme_id, peaks.get(meme_id, snapshot.get(meme_id, 0.0)))
        for meme_id in _certified_ids(session)
    ]
    ranked = sorted(candidates, key=lambda item: (-item[1], item[0]))
    # 0 分的不要：一个数据都没采到的梗进「年度爆款」是荒谬的
    return [meme_id for meme_id, score in ranked[:limit] if score > 0]


def collection_member_ids(
    session: Session,
    key: str,
    *,
    today: date | None = None,
    eligible_ids: set[int] | None = None,
) -> list[int]:
    """某个专题下的梗 id（有序：月度按入库顺序，年度按峰值降序）。

    ``eligible_ids`` 给定时只保留其中的梗，**列表接口必须传**：
    专题规则只认 ``status=certified``，而列表接口还要求有指标快照，
    两套口径不交集的话，计数就会与「点进去看到的条数」对不上——
    筛选行写着 74、点进去只有 46，用户只会觉得数据不可信。
    """
    today = today or date.today()
    if key == "monthly":
        ids = _monthly_ids(session, today)
    elif key == "yearly":
        ids = _yearly_ids(session, today)
    else:
        return []
    if eligible_ids is not None:
        ids = [meme_id for meme_id in ids if meme_id in eligible_ids]
    return ids


def collection_summary(
    session: Session,
    *,
    today: date | None = None,
    eligible_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    """专题清单（含实时计数），给 meta 接口用。

    计数与列表走同一个 ``eligible_ids``，保证页面上的数字与点进去的条数一致。
    """
    today = today or date.today()
    labels = collection_labels(today)
    out: list[dict[str, Any]] = []
    for spec in COLLECTIONS:
        members = collection_member_ids(
            session, spec.key, today=today, eligible_ids=eligible_ids
        )
        out.append(
            {
                "key": spec.key,
                "label": labels[spec.key],
                "emoji": spec.emoji,
                "description": spec.description,
                "count": len(members),
            }
        )
    return out


def tag_summary(
    session: Session, *, eligible_ids: set[int] | None = None
) -> list[dict[str, Any]]:
    """主题标签清单（含实时计数）。顺序按 taxonomy 里的定义，不按计数排——
    顺序老是变的话，用户会找不到自己上次点的那个。"""
    counts: dict[str, int] = {}
    for meme in session.scalars(select(Meme)):
        if eligible_ids is not None and meme.id not in eligible_ids:
            continue
        for tag in meme.tags or []:
            counts[tag] = counts.get(tag, 0) + 1

    # 一个梗都还没标过 → 返回空清单。页面据此显示「还没打标」的提示，
    # 而不是挂一排点进去没结果的死标签。
    if not counts:
        return []

    out: list[dict[str, Any]] = []
    for spec in MEME_TAGS:
        count = counts.get(spec.key, 0)
        # 「其他」永远显示（它是兜底类）；其余标签一个梗都没有就不展示，
        # 免得筛选行上挂着一排点了没结果的死标签。
        if spec.key != "other" and count == 0:
            continue
        out.append(
            {
                "key": spec.key,
                "label": spec.label,
                "emoji": spec.emoji,
                "count": count,
            }
        )
    return out
