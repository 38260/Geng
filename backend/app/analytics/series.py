"""时间序列与窗口聚合。

产品关注的不是"历史上有多少播放量"，而是"最近是不是正在变热"，
因此所有指标都在 1/3/7/30 天窗口上计算，并额外计算
「最近 7 天 vs 前 7 天」的增长率。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.models import MemeDailyStats


@dataclass(frozen=True)
class DayPoint:
    day: date
    video_count: int = 0
    creator_count: int = 0
    view: int = 0
    like: int = 0
    coin: int = 0
    favorite: int = 0
    reply: int = 0
    danmaku: int = 0
    # False = 这一天接口没返回（B站搜索抖动），不代表当天真的没内容。
    # 任何"趋势/阶段"结论都不许拿它当零活动用。
    observed: bool = True

    @property
    def interaction(self) -> int:
        return self.like + self.coin + self.favorite + self.reply + self.danmaku

    @property
    def discussion(self) -> int:
        """讨论量 = 评论 + 弹幕（首页卡片口径）。"""
        return self.reply + self.danmaku


@dataclass(frozen=True)
class WindowAgg:
    days: int
    start: date
    end: date
    video_count: int = 0
    creator_count: int = 0        # 各日累加（跨日可能重复），口径为"参与UP主(日累计)"
    creator_peak: int = 0         # 单日峰值，作为去重后的下界
    view: int = 0
    interaction: int = 0
    reply: int = 0
    danmaku: int = 0
    discussion: int = 0
    active_days: int = 0
    observed_days: int = 0          # 真正观测到的天数（不含接口空返回的洞）

    @property
    def is_empty(self) -> bool:
        return self.video_count == 0 and self.view == 0

    @property
    def coverage(self) -> float:
        """窗口覆盖度：观测到的天数 / 窗口天数。"""
        return round(self.observed_days / self.days, 3) if self.days else 0.0


@dataclass
class Series:
    """某个梗的完整日粒度时间序列（按日期升序、无缺口）。"""

    meme_id: int
    points: list[DayPoint] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    @classmethod
    def from_stats(cls, meme_id: int, stats: list[MemeDailyStats], *, window_days: int = 30) -> "Series":
        """把稀疏的每日统计补齐成连续日期序列（缺失日补 0）。"""
        if not stats:
            return cls(meme_id=meme_id, points=[])
        by_day = {s.stat_date: s for s in stats}
        end = max(by_day)
        start = max(end - timedelta(days=window_days - 1), min(by_day))
        points: list[DayPoint] = []
        cursor = start
        while cursor <= end:
            row = by_day.get(cursor)
            points.append(
                DayPoint(
                    day=cursor,
                    video_count=row.video_count if row else 0,
                    creator_count=row.creator_count if row else 0,
                    view=row.view if row else 0,
                    like=row.like if row else 0,
                    coin=row.coin if row else 0,
                    favorite=row.favorite if row else 0,
                    reply=row.reply if row else 0,
                    danmaku=row.danmaku if row else 0,
                    # 库里没有这一行 = 这一天没被观测过；有行但 observed=False
                    # = 观测了但接口给了空壳。两者都不能当"当天没内容"用。
                    # （未 flush 的行 observed 还是 None，按默认值 True 处理。）
                    observed=(row.observed is not False) if row else False,
                )
            )
            cursor += timedelta(days=1)
        return cls(meme_id=meme_id, points=points)

    def __len__(self) -> int:
        return len(self.points)

    @property
    def end_day(self) -> date | None:
        return self.points[-1].day if self.points else None

    # ------------------------------------------------------------------ #
    def tail(self, days: int, offset: int = 0) -> list[DayPoint]:
        """取最近 ``days`` 天；``offset`` 往前再挪 ``offset`` 天（用于"前 7 天"）。"""
        if not self.points or days <= 0:
            return []
        end = len(self.points) - offset
        start = max(0, end - days)
        return self.points[start:end] if end > start else []

    def aggregate(self, days: int, offset: int = 0) -> WindowAgg:
        chunk = self.tail(days, offset)
        if not chunk:
            anchor = self.end_day or date.today()
            start = anchor - timedelta(days=days - 1)
            return WindowAgg(days=days, start=start, end=anchor)
        return WindowAgg(
            days=days,
            start=chunk[0].day,
            end=chunk[-1].day,
            video_count=sum(p.video_count for p in chunk),
            creator_count=sum(p.creator_count for p in chunk),
            creator_peak=max((p.creator_count for p in chunk), default=0),
            view=sum(p.view for p in chunk),
            interaction=sum(p.interaction for p in chunk),
            reply=sum(p.reply for p in chunk),
            danmaku=sum(p.danmaku for p in chunk),
            discussion=sum(p.discussion for p in chunk),
            active_days=sum(1 for p in chunk if p.video_count > 0 or p.view > 0),
            observed_days=sum(1 for p in chunk if p.observed),
        )


def growth_rate(current: float, previous: float) -> float | None:
    """增长率；分母为 0 时返回 None（表示"无法比较"，而不是 +∞ 或 0）。"""
    if previous <= 0:
        return None
    return (current - previous) / previous


def safe_growth(current: float, previous: float, *, new_entry_value: float = 1.0) -> float:
    """用于打分的增长率：从 0 涨起来视为"新出现"，给一个固定的高增长值。"""
    rate = growth_rate(current, previous)
    if rate is None:
        return new_entry_value if current > 0 else 0.0
    return rate
