"""热度指数：0-100、只看近期、不被历史累计绑架。"""

from __future__ import annotations

import math

import pytest

from app.analytics import Series, compute_hotness, growth_score, log_score
from app.analytics.hotness import rolling_hotness

from .test_series import series_from_views


def test_empty_series_scores_zero():
    result = compute_hotness(Series(meme_id=1, points=[]))
    assert result.score == 0.0
    assert result.metrics.get("reason") == "no_data"


def test_score_always_inside_zero_to_hundred():
    for views in ([0] * 30, [10] * 30, [10**9] * 30, [50_000 * i for i in range(30)]):
        result = compute_hotness(series_from_views(views))
        assert 0.0 <= result.score <= 100.0


def test_more_views_means_more_heat_at_equal_growth():
    small = compute_hotness(series_from_views([20_000] * 30)).score
    big = compute_hotness(series_from_views([2_000_000] * 30)).score
    assert big > small


def test_growth_outranks_stale_cumulative_volume():
    """文档 §十四：去年 1 亿播放不代表现在还火。"""
    once_huge_then_dead = series_from_views([80_000_000] * 10 + [0] * 20)
    steadily_rising = series_from_views([20_000 * i for i in range(1, 31)])

    assert compute_hotness(once_huge_then_dead).score < compute_hotness(steadily_rising).score


def test_log_score_boundaries_and_nan():
    floor, ceiling = 3_000, 8_000_000
    assert log_score(0, "view") == 0.0
    assert log_score(ceiling, "view") == pytest.approx(100.0)
    assert log_score(ceiling * 100, "view") == 100.0        # 封顶，不被单条爆款拉爆
    assert log_score(float("nan"), "view") == 0.0           # NaN 不外泄
    assert log_score(floor / 100, "view") < 5.0


def test_growth_score_clipping():
    assert growth_score(-1.0) == 0.0
    assert growth_score(5.0) == 100.0
    assert growth_score(None) == 50.0                        # 无基数不奖不罚


def test_low_sample_damping_and_growth_suppression():
    """考古区冒出 1 条视频，不应该被算成 +100% 增长。"""
    trickle = series_from_views([0] * 28 + [15_000, 20_000])
    result = compute_hotness(trickle)
    assert result.components["growth"] == 0.0
    assert result.metrics.get("growth") is None
    assert result.metrics.get("sample_note")
    assert result.score < 15.0
    assert result.score < result.metrics["raw_score"]  # 确实被折减过


def test_rolling_hotness_covers_every_day():
    series = series_from_views([10_000 * i for i in range(1, 31)])
    daily = rolling_hotness(series)
    assert len(daily) == len(series)
    assert all(0.0 <= value <= 100.0 for _, value in daily)
    assert not any(math.isnan(value) for _, value in daily)
    # 持续上涨的梗，末期热度应高于初期
    assert daily[-1][1] > daily[3][1]
