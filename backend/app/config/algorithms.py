"""Central place for every analytics threshold.

The product spec is explicit: heat index and lifecycle must be produced by our
own algorithm, and the thresholds must not be scattered across the code base
(let alone the frontend). Change numbers here, nowhere else.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Relevance filtering
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RelevanceWeights:
    title: float = 0.6
    description: float = 0.2
    keyword: float = 0.2


RELEVANCE_WEIGHTS = RelevanceWeights()
RELEVANCE_THRESHOLD = 0.5


# --------------------------------------------------------------------------- #
# Hotness index (0 - 100)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class HotnessWeights:
    """热度指数五个子分数的权重（合计 1.0）。

    增长权重给到 0.25 是刻意的：产品要回答的是"最近是不是正在变热"，
    一个历史累计 1 亿播放、但近 7 天没人做的梗不应该排在前面。
    """

    view: float = 0.25          # 播放表现
    interaction: float = 0.20   # 互动表现（评论/弹幕/点赞/投币/收藏）
    content: float = 0.16       # 内容规模（相关视频数）
    creator: float = 0.14       # 参与 UP 主数量
    growth: float = 0.25        # 近期增长速度


HOTNESS_WEIGHTS = HotnessWeights()

# 子分数采用「对数区间归一化」：(floor, ceiling) 分别是 7 天窗口内的起步量与封顶量。
# 绝对量再大也不会让一个梗吃掉整个榜，绝对量极小的梗也不会因为噪声上榜。
HOTNESS_REFERENCE = {
    "view": (3_000, 8_000_000),          # 7 天播放量
    "interaction": (300, 900_000),       # 7 天互动总量（赞+币+藏+评+弹）
    "content": (1, 900),                 # 7 天相关视频数
    "creator": (1, 500),                 # 7 天参与 UP 主（日累计）
}

# Growth sub-score maps a 7d-vs-prev-7d growth rate onto 0..100.
GROWTH_SCORE_ZERO = -0.30   # -30% growth  -> 0
GROWTH_SCORE_FULL = 1.20    # +120% growth -> 100

# A meme with fewer than this many relevant videos inside the window is treated
# as "not enough data" and its heat index is damped instead of shown as noise.
MIN_SAMPLE_VIDEOS = 3
LOW_SAMPLE_DAMPING = 0.6


# --------------------------------------------------------------------------- #
# Lifecycle classification
# --------------------------------------------------------------------------- #
LIFECYCLE_STAGES = [
    "sprouting",   # 🌱 萌芽期
    "rising",      # 📈 上升期
    "explosive",   # 🔥 爆发期
    "plateau",     # 🌊 平稳期
    "receding",    # 📉 退潮期
    "obsolete",    # 🪦 过气
]

LIFECYCLE_LABELS = {
    "sprouting": "萌芽期",
    "rising": "上升期",
    "explosive": "爆发期",
    "plateau": "平稳期",
    "receding": "退潮期",
    "obsolete": "过气",
}

LIFECYCLE_EMOJI = {
    "sprouting": "🌱",
    "rising": "📈",
    "explosive": "🔥",
    "plateau": "🌊",
    "receding": "📉",
    "obsolete": "🪦",
}


@dataclass(frozen=True)
class LifecycleThresholds:
    """规则自上而下匹配，第一条命中即判定。

    ``heat``         : 当前热度指数（0-100）
    ``growth``       : 最近 7 天 vs 前 7 天的综合增长率
    ``peak_gap``     : 距 30 天内热度峰值的回落幅度（0 = 正在峰值上）
    ``activity``     : 最近 7 天新增相关视频数
    ``view_7d``      : 最近 7 天播放量
    ``stale_days``   : 距今多少天没有新内容
    """

    # 🪦 过气：长期没有新内容，或量级与热度同时塌到地板
    obsolete_stale_days: int = 14
    obsolete_max_activity: int = 2
    obsolete_max_heat: float = 18.0

    # 🌱 萌芽：有动静但绝对量还很小（热度会因为高增长率被抬高，所以看量级）
    sprouting_max_activity: int = 10
    sprouting_max_view_7d: int = 80_000
    sprouting_max_heat: float = 45.0

    # 🔥 爆发：短时间陡增且已经冲到高位、正贴着峰值
    #   增长门槛刻意高于普通上升期（+130%），否则涨得快的上升期会被误判成爆发
    explosive_min_heat: float = 70.0
    explosive_min_growth: float = 1.30
    explosive_max_peak_gap: float = 0.15

    # 📈 上升：稳定增长，量级已经起来
    rising_min_growth: float = 0.15
    rising_min_heat: float = 30.0

    # 📉 退潮：增速转负，或已明显离开峰值且连续下滑
    receding_max_growth: float = -0.12
    receding_min_peak_gap: float = 0.20
    # 只有"连续若干天热度在掉"才算退潮，避免平稳期的正常抖动被误判
    receding_min_declining_days: int = 3

    # 🌊 平稳：以上都不命中（|增长| 很小）
    plateau_band: float = 0.12


LIFECYCLE_THRESHOLDS = LifecycleThresholds()


# --------------------------------------------------------------------------- #
# Catch-up judgement ("现在赶还来得及吗")
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CatchUpThresholds:
    """Algorithm-owned status. The LLM only words it, never decides it."""

    too_late_max_growth: float = -0.10
    too_late_min_peak_gap: float = 0.25
    too_late_stages: tuple[str, ...] = ("receding", "obsolete")

    can_catch_min_growth: float = 0.10
    can_catch_max_peak_gap: float = 0.15
    can_catch_stages: tuple[str, ...] = ("sprouting", "rising", "explosive")

    # Heat already very high + close to peak => the window is shrinking.
    caution_min_heat: float = 85.0


CATCHUP_THRESHOLDS = CatchUpThresholds()

CATCHUP_LABELS = {
    "can_catch": "还来得及",
    "caution": "慎赶",
    "too_late": "你来晚了",
}

CATCHUP_EMOJI = {"can_catch": "🟢", "caution": "🟡", "too_late": "🔴"}

# Homepage filter chips -> the lifecycle/heat set they select.
HOME_FILTERS = {
    "all": None,
    "hot": ("explosive",),                       # 正在爆
    "taking_off": ("sprouting", "rising"),       # 快起飞
    "receding": ("receding", "obsolete"),        # 退潮中
    "plateau": ("plateau",),
}

HOME_FILTER_LABELS = {
    "all": "全部",
    "hot": "正在爆",
    "taking_off": "快起飞",
    "receding": "退潮中",
}


@dataclass(frozen=True)
class AnalyticsConfig:
    relevance: RelevanceWeights = RELEVANCE_WEIGHTS
    hotness: HotnessWeights = HOTNESS_WEIGHTS
    lifecycle: LifecycleThresholds = LIFECYCLE_THRESHOLDS
    catch_up: CatchUpThresholds = CATCHUP_THRESHOLDS
    extras: dict = field(default_factory=dict)


ANALYTICS_CONFIG = AnalyticsConfig()

# Time windows the product can report on. ``primary`` feeds the heat index,
# ``compare`` is the baseline the growth rate is measured against.
ANALYSIS_DEFAULTS = {
    "windows_days": [1, 3, 7, 30],
    "primary_window": 7,
    "compare_window": 7,
    "default_trend_window": 7,
    "trend_windows": [7, 30],
    "detail_window": 30,
}

