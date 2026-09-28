"""生命周期必须由"时间序列 + 算法"决定。

最强的验证方式：让演示数据按某个原型生成曲线，再要求算法把它认出来。
"""

from __future__ import annotations

import pytest

from app.analytics import Series, build_input, classify, compute_hotness, nickname
from app.analytics.hotness import rolling_hotness
from app.config import LIFECYCLE_STAGES
from app.mock.curves import build_daily_points, stats_from_points

ARCHETYPES = ["sprouting", "rising", "explosive", "plateau", "receding", "obsolete"]

# 每个原型配一个与其量级相符的 scale：萌芽期本来就应该是小量级，
# 用爆款量级去测"萌芽"是没有意义的（那会被正确判成上升期）。
SCALE_BY_ARCHETYPE = {
    "sprouting": 12_000,
    "rising": 90_000,
    "explosive": 260_000,
    "plateau": 40_000,
    "receding": 18_000,
    "obsolete": 3_600,
}


def analyse(archetype: str, *, scale: float | None = None):
    scale = scale or SCALE_BY_ARCHETYPE[archetype]
    points = build_daily_points(archetype=archetype, scale=scale, seed=42, days=30)
    stats = stats_from_points(1, points)
    series = Series.from_stats(1, stats, window_days=30)
    daily = rolling_hotness(series)
    current = compute_hotness(series)
    inp = build_input(series, heat=current.score, growth=current.metrics.get("growth"),
                      daily_hotness=[value for _, value in daily])
    return current, inp, classify(inp)


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_algorithm_recovers_declared_archetype(archetype):
    _, _, result = analyse(archetype)
    assert result.stage == archetype, (
        f"{archetype} 被判成了 {result.stage}（依据：{result.reasons}）"
    )


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_every_stage_returns_label_emoji_and_indicators(archetype):
    _, _, result = analyse(archetype)
    assert result.stage in LIFECYCLE_STAGES
    assert result.label and result.emoji
    assert result.reasons
    assert "peak_gap" in result.indicators and "declining_days" in result.indicators


def test_obsolete_when_no_content_for_two_weeks():
    from app.analytics.lifecycle import LifecycleInput

    # observed_days_7=7：这七天每天都真去看过了，确实一条新内容都没有。
    # 要是没观测（接口给空壳），下面该判的是「数据不足」而不是「过气」。
    inp = LifecycleInput(heat=6.0, growth=0.0, activity=0, view_7d=0,
                         peak_heat=40.0, stale_days=21, active_days_7=0, observed_days_7=7)
    assert classify(inp).stage == "obsolete"


def test_plateau_is_not_called_receding_by_small_wobble():
    """平稳期末尾的正常抖动不应该被判成退潮（曾经真实发生过的误判）。"""
    from app.analytics.lifecycle import LifecycleInput

    inp = LifecycleInput(heat=44.0, growth=-0.05, activity=21, view_7d=300_000,
                         peak_heat=47.0, stale_days=0, active_days_7=7, observed_days_7=7,
                         declining_days=2)
    assert classify(inp).stage == "plateau"


def test_explosive_needs_both_height_and_steep_growth():
    from app.analytics.lifecycle import LifecycleInput

    steep_and_high = LifecycleInput(heat=92.0, growth=1.6, activity=180, view_7d=5_000_000,
                                    peak_heat=93.0, stale_days=0, active_days_7=7,
                                    observed_days_7=7)
    fast_but_small = LifecycleInput(heat=40.0, growth=1.6, activity=180, view_7d=5_000_000,
                                    peak_heat=41.0, stale_days=0, active_days_7=7,
                                    observed_days_7=7)
    assert classify(steep_and_high).stage == "explosive"
    assert classify(fast_but_small).stage == "rising"


def test_sparse_observation_refuses_a_trend_verdict():
    """「琵琶曲」那种序列：7 天里只观测到 2 天，其余是接口空壳。

    这时 activity/view_7d 都是被洞压低过的数，判退潮、判过气都等于把抖动
    当成结论。宁可不给结论。
    """
    from app.analytics.lifecycle import LifecycleInput
    from app.analytics.catch_up import INSUFFICIENT, decide
    from app.config import LIFECYCLE_THRESHOLDS

    holey = LifecycleInput(heat=49.5, growth=-0.62, activity=26, view_7d=6_315_597,
                           peak_heat=80.1, stale_days=0, active_days_7=2, observed_days_7=2)
    result = classify(holey)
    assert result.stage == "insufficient"
    assert LIFECYCLE_THRESHOLDS.min_observed_days > holey.observed_days_7
    assert "观测" in result.reasons[0]
    # 同一个梗即使热度分数照旧，趋势结论也必须被闸门挡住
    verdict = decide(holey, stage=result.stage, heat=holey.heat, growth=holey.growth,
                     peak_gap=holey.peak_gap)
    assert verdict.status == INSUFFICIENT and verdict.confidence == 0.0


def test_full_observation_still_gets_a_real_verdict():
    """补够观测天数，同样的数字就该正常给结论——闸门不能变成万能挡箭牌。"""
    from app.analytics.lifecycle import LifecycleInput

    inp = LifecycleInput(heat=49.5, growth=-0.62, activity=26, view_7d=6_315_597,
                         peak_heat=80.1, stale_days=0, active_days_7=6, observed_days_7=7)
    assert classify(inp).stage == "receding"


def test_nickname_uses_playful_wording_for_fast_risers():
    assert nickname("explosive", 1.6) == "正在爆"
    assert nickname("rising", 0.9) == "快起飞"
    assert nickname("rising", 0.2) == "上升期"
    assert nickname("obsolete") == "考古区"
    assert nickname("unknown-stage") == "unknown-stage"
