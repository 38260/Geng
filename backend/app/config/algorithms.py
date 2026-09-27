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
    """Weights of the five sub-scores that build the 赶梗潮 heat index."""

    view: float = 0.28          # 播放表现
    interaction: float = 0.24   # 互动表现（评论/弹幕/点赞/投币/收藏）
    content: float = 0.18       # 内容规模（相关视频数）
    creator: float = 0.15       # 参与 UP 主数量
    growth: float = 0.15        # 近期增长速度


HOTNESS_WEIGHTS = HotnessWeights()

# Sub-scores are log-scaled against these reference values so that a single
# viral mega-video cannot dominate the ranking, and so that the index stays
# comparable across memes of very different sizes.
HOTNESS_REFERENCE = {
    "view": 2_000_000,        # 7 天播放量参考上限
    "interaction": 150_000,   # 7 天互动总量参考上限
    "content": 600,           # 7 天相关视频数参考上限
    "creator": 250,           # 7 天参与 UP 主参考上限
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
    """Rules are evaluated top-down; the first match wins.

    ``growth``   : heat growth of the last 7 days vs. the previous 7 days
    ``level``    : current heat index (0-100)
    ``peak_gap`` : how far today's heat sits below the 30-day peak
    ``activity`` : relevant videos published in the last 7 days
    """

    obsolete_max_activity: int = 2
    obsolete_max_heat: float = 18.0
    obsolete_stale_days: int = 14

    sprouting_max_activity: int = 6
    sprouting_max_heat: float = 25.0

    explosive_min_heat: float = 70.0
    explosive_min_growth: float = 0.45
    explosive_near_peak_gap: float = 0.12

    rising_min_growth: float = 0.15
    rising_min_heat: float = 30.0

    receding_max_growth: float = -0.12
    receding_from_peak_gap: float = 0.20

    plateau_band: float = 0.12  # |growth| below this is "flat"


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

