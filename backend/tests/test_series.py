"""时间序列与窗口聚合。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.analytics import DayPoint, Series, growth_rate, safe_growth


def series_from_views(views: list[int], *, end: date | None = None) -> Series:
    end = end or date(2026, 9, 27)
    points = []
    for index, view in enumerate(views):
        points.append(
            DayPoint(
                day=end - timedelta(days=len(views) - 1 - index),
                video_count=max(1, int(view / 20_000)) if view else 0,
                creator_count=max(1, int(view / 30_000)) if view else 0,
                view=view,
                like=int(view * 0.06),
                coin=int(view * 0.02),
                favorite=int(view * 0.03),
                reply=int(view * 0.012),
                danmaku=int(view * 0.035),
            )
        )
    return Series(meme_id=1, points=points)


def test_tail_and_window_offsets():
    series = series_from_views(list(range(1, 31)))
    assert [p.view for p in series.tail(7)] == [24, 25, 26, 27, 28, 29, 30]
    assert [p.view for p in series.tail(7, offset=7)] == [17, 18, 19, 20, 21, 22, 23]


def test_aggregate_sums_and_active_days():
    series = series_from_views([0, 0, 1000, 2000])
    agg = series.aggregate(4)
    assert agg.view == 3000
    assert agg.active_days == 2
    assert agg.discussion == int(1000 * 0.047) + int(2000 * 0.047)


def test_growth_rate_division_by_zero_is_none_not_infinity():
    assert growth_rate(100, 0) is None
    assert growth_rate(0, 0) is None
    assert growth_rate(150, 100) == pytest.approx(0.5)
    assert growth_rate(50, 100) == pytest.approx(-0.5)


def test_safe_growth_treats_new_entry_as_high_growth():
    assert safe_growth(100, 0) == pytest.approx(1.0)
    assert safe_growth(0, 0) == 0.0


def test_from_stats_fills_missing_days_with_zero():
    from app.models import MemeDailyStats

    end = date(2026, 9, 27)
    stats = [
        MemeDailyStats(meme_id=1, stat_date=end, view=500, video_count=1, creator_count=1),
        MemeDailyStats(meme_id=1, stat_date=end - timedelta(days=3), view=300, video_count=1, creator_count=1),
    ]
    series = Series.from_stats(1, stats, window_days=7)
    assert len(series) == 4
    assert [p.view for p in series.points] == [300, 0, 0, 500]


def test_empty_series_is_safe():
    series = Series(meme_id=1, points=[])
    assert series.aggregate(7).is_empty
    assert series.tail(7) == []
    assert series.end_day is None
