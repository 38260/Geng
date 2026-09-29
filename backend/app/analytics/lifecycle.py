"""生命周期判定。

文档要求：生命周期必须由「时间序列 + 算法」决定，而不是由 LLM 决定。
本模块只做一件事——把已经算好的指标喂进一组阈值规则，输出六个阶段之一。
阈值全部在 :mod:`app.config.algorithms` 里。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.config import LIFECYCLE_EMOJI, LIFECYCLE_LABELS, LIFECYCLE_STAGES, LIFECYCLE_THRESHOLDS

from .series import Series


@dataclass
class LifecycleInput:
    heat: float = 0.0
    growth: float | None = None
    activity: int = 0            # 近 7 天新增相关视频数
    view_7d: int = 0
    peak_heat: float = 0.0       # 30 天内滚动热度峰值
    stale_days: int = 0          # 距今多少天没有新内容（只数真正观测到的日子）
    active_days_7: int = 0
    observed_days_7: int = 0     # 近 7 天里真正观测到几天，其余是接口的洞
    declining_days: int = 0      # 热度连续下滑的天数（末尾连续）
    window_days: int = 30

    @property
    def peak_gap(self) -> float:
        if self.peak_heat <= 0:
            return 0.0
        return max(0.0, (self.peak_heat - self.heat) / self.peak_heat)

    @property
    def growth_or_zero(self) -> float:
        return 0.0 if self.growth is None else self.growth


@dataclass
class LifecycleResult:
    stage: str
    label: str
    emoji: str
    reasons: list[str] = field(default_factory=list)
    indicators: dict[str, Any] = field(default_factory=dict)

    @property
    def stage_index(self) -> int:
        return LIFECYCLE_STAGES.index(self.stage)


def build_input(
    series: Series,
    *,
    heat: float,
    growth: float | None,
    daily_hotness: list[float],
) -> LifecycleInput:
    """从时间序列里取出规则需要的指标。"""
    last7 = series.tail(7)
    activity = sum(p.video_count for p in last7)
    view_7d = sum(p.view for p in last7)

    stale_days = 0
    for point in reversed(series.points):
        if point.video_count > 0:
            break
        # 接口没返回的日子不算"没有新内容"，只算"不知道"——不能拿洞去判过气
        if point.observed:
            stale_days += 1

    peak = max(daily_hotness) if daily_hotness else heat
    declining = 0
    for index in range(len(daily_hotness) - 1, 0, -1):
        if daily_hotness[index] < daily_hotness[index - 1]:
            declining += 1
        else:
            break
    return LifecycleInput(
        heat=heat,
        growth=growth,
        activity=activity,
        view_7d=view_7d,
        peak_heat=peak,
        stale_days=stale_days,
        active_days_7=sum(1 for p in last7 if p.video_count > 0),
        observed_days_7=sum(1 for p in last7 if p.observed),
        declining_days=declining,
        window_days=len(series.points),
    )


def classify(inp: LifecycleInput) -> LifecycleResult:
    t = LIFECYCLE_THRESHOLDS
    growth = inp.growth_or_zero
    peak_gap = inp.peak_gap
    reasons: list[str] = []

    def _make(stage: str, *why: str) -> LifecycleResult:
        reasons.extend(why)
        return LifecycleResult(
            stage=stage,
            label=LIFECYCLE_LABELS[stage],
            emoji=LIFECYCLE_EMOJI[stage],
            reasons=reasons,
            indicators={**asdict(inp), "peak_gap": round(peak_gap, 3)},
        )

    # 数据不足：窗口里洞太多，后面每一条规则拿到的 activity/view_7d/stale_days
    # 都是被空洞压低过的数，判出来的"退潮/过气"其实是接口抖动（「琵琶曲」-62% 就是这么来的）。
    # 宁可不给结论，也不给一个建在空洞上的结论。
    if inp.observed_days_7 < t.min_observed_days:
        return _make(
            "insufficient",
            f"最近 7 天只观测到 {inp.observed_days_7} 天数据，趋势说不准（B站搜索接口对同一天"
            f"会随机返回空结果，观测不够时不给阶段结论）",
        )

    # 🪦 过气
    if inp.stale_days >= t.obsolete_stale_days:
        return _make("obsolete", f"已经 {inp.stale_days} 天没有新增相关内容")
    if inp.activity <= t.obsolete_max_activity and inp.heat <= t.obsolete_max_heat:
        return _make(
            "obsolete",
            f"近 7 天仅 {inp.activity} 条相关内容，热度 {inp.heat:.0f} 已落到地板",
        )

    # 🌱 萌芽
    if (
        inp.activity <= t.sprouting_max_activity
        and inp.view_7d <= t.sprouting_max_view_7d
        and inp.heat <= t.sprouting_max_heat
    ):
        return _make(
            "sprouting",
            f"刚开始有 UP 主做，近 7 天 {inp.activity} 条内容、播放量 {inp.view_7d}，量级还很小",
        )

    # 🔥 爆发
    if (
        inp.heat >= t.explosive_min_heat
        and growth >= t.explosive_min_growth
        and peak_gap <= t.explosive_max_peak_gap
    ):
        return _make(
            "explosive",
            f"热度 {inp.heat:.0f} 且一周内增长 {growth * 100:.0f}%，正贴着近期峰值",
        )

    # 📈 上升
    if growth >= t.rising_min_growth and inp.heat >= t.rising_min_heat:
        return _make("rising", f"热度 {inp.heat:.0f}，最近一周增长 {growth * 100:.0f}%")

    # 📉 退潮
    if growth <= t.receding_max_growth:
        return _make("receding", f"最近一周增长 {growth * 100:.0f}%，新增内容开始减少")
    if (
        peak_gap >= t.receding_min_peak_gap
        and growth <= -0.05
        and inp.declining_days >= t.receding_min_declining_days
    ):
        return _make(
            "receding",
            f"已离开近期峰值 {peak_gap * 100:.0f}%，且热度连续 {inp.declining_days} 天往下走",
        )

    # 🌊 平稳：增长落在中立带里。
    # 这条规则以前是缺失的——`plateau` 只是函数末尾的兜底 else，
    # 于是 `plateau_band` 这个阈值配了却从来没人读，
    # 任何"没命中前面任何规则"的输入都会被打成平稳期，包括反常在涨的梗。
    # 现在它是显式规则：先判持平，判不到才落兜底。
    if abs(growth) <= t.plateau_band:
        return _make(
            "plateau",
            f"增长基本持平（{growth * 100:+.0f}%），热度稳定在 {inp.heat:.0f}",
        )

    # 兜底：没命中以上任何一条（例如在涨但还没到上升期的量级，
    # 或在跌但没跌到退潮的线）。归到平稳期并如实说明它是"没特征"。
    return _make(
        "plateau",
        f"没有明显方向（增长 {growth * 100:+.0f}%），热度 {inp.heat:.0f}，按平稳期处理",
    )


def stage_is_valid(stage: str) -> bool:
    return stage in LIFECYCLE_STAGES


# 首页卡片上的"潮称"：正式阶段名 + 一点梗文化说法（文档要求 80% 正常 / 20% 玩梗）
NICKNAMES = {
    "sprouting": "刚冒头",
    "rising": "上升期",
    "explosive": "正在爆",
    "plateau": "平稳期",
    "receding": "退潮中",
    "obsolete": "考古区",
    "insufficient": "数据不足",
}


def nickname(stage: str, growth: float | None = None) -> str:
    """给卡片用的短标签；上升期涨得特别快时叫「快起飞」。"""
    if stage == "rising" and growth is not None and growth >= 0.6:
        return "快起飞"
    return NICKNAMES.get(stage, LIFECYCLE_LABELS.get(stage, stage))
