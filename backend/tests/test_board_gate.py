"""上榜门槛（第③层）：准入只证明"这是个真梗"，热榜还要证明"它今天还活着"。

重点测两类误伤：
* 过气梗占位——判成 obsolete 的不能再挤在"今天玩什么"里；
* 脉冲型梗——「琵琶曲」30 天只有 4 天有内容但那几天播了 3,976 万，
  只看天数会把它误杀，所以门槛是"天数 或 近 7 天头部播放"二选一。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.analytics import Series
from app.analytics.hotness import compute_hotness
from app.config import BOARD_MIN_RECENT_VIEW, settings
from app.models import HotnessSnapshot, LifecycleSnapshot, MemeDailyStats, MemeStatus
from app.services.meme.query import board_gate_reason, list_memes, meta_payload, on_board

from .conftest import make_stats


def _snap(session, meme, *, score=30.0, stage="plateau", active_days=20,
          recent_view=2_000_000):
    session.add(HotnessSnapshot(
        meme_id=meme.id, score=score, window_days=7,
        components={}, metrics={"active_days": active_days, "view": recent_view},
    ))
    session.add(LifecycleSnapshot(
        meme_id=meme.id, stage=stage, stage_label=stage, catch_status="can_catch",
        catch_label="还来得及", catch_confidence=0.6, reasons=[], indicators={},
    ))
    session.flush()


@pytest.fixture()
def live_meme(meme_factory):
    def _make(name):
        return meme_factory(name, encyclopedia_confirmed=True, guide_confirmed=True,
                            certified=True, status=MemeStatus.CERTIFIED,
                            data_source="bilibili", verification_state="verified_both")
    return _make


def _names(session, scope, **kwargs):
    return {item["name"] for item in list_memes(session, scope=scope, **kwargs)["items"]}


def test_obsolete_meme_is_off_the_board_but_still_in_library(session, live_meme):
    meme = live_meme("门槛过气梗")
    _snap(session, meme, stage="obsolete")

    assert on_board(session.get(HotnessSnapshot, meme.id),
                    session.get(LifecycleSnapshot, meme.id)) is False
    board = list_memes(session, scope="board")
    library = list_memes(session, scope="all")
    assert meme.name not in {i["name"] for i in board["items"]}
    assert meme.name in {i["name"] for i in library["items"]}
    assert board["gated_out"] >= 1 and board["library_total"] == library["total"]


def test_pulse_meme_with_few_days_but_big_views_stays(session, live_meme):
    meme = live_meme("门槛脉冲梗")
    _snap(session, meme, active_days=4, recent_view=BOARD_MIN_RECENT_VIEW + 1)
    # 天数只有 4 天（低于旧的 5 天口径），但近 7 天播放够大——脉冲型梗不能被天数误杀

    assert meme.name in _names(session, "board")


def test_thin_meme_is_gated_with_an_explainable_reason(session, live_meme):
    meme = live_meme("门槛空壳梗")
    _snap(session, meme, active_days=2, recent_view=1000)

    reason = board_gate_reason(session.get(HotnessSnapshot, meme.id),
                               session.get(LifecycleSnapshot, meme.id))
    assert "2 天有内容" in reason and "低于上榜下限" in reason
    assert meme.name not in _names(session, "board")
    assert meme.name in _names(session, "all")


def test_gate_can_be_switched_off(session, live_meme, monkeypatch):
    meme = live_meme("门槛关闭梗")
    _snap(session, meme, stage="obsolete")
    assert meme.name not in _names(session, "board")

    monkeypatch.setattr(settings, "leaderboard_gate", False)
    assert meme.name in _names(session, "board")


def test_meta_reports_both_counts(session, live_meme):
    _snap(session, live_meme("门槛活梗"))
    _snap(session, live_meme("门槛死梗"), stage="obsolete")

    meta = meta_payload(session)
    assert meta["library_count"] >= 2
    assert meta["certified_count"] == meta["library_count"] - meta["gated_out"]
    assert meta["gated_out"] >= 1
    assert "活着" in meta["transparency"]["board_gate"]


def test_active_days_is_measured_from_the_series_not_hardcoded():
    """active_days 数的是「有内容的天」：由序列实算，不是数播放非零的天数。"""
    values = [50_000, 40_000, 30_000, 20_000, 10_000, 0, 0, 0, 0, 0]
    stats = make_stats(1, values, end=date.today())
    series = Series.from_stats(1, stats, window_days=30)

    result = compute_hotness(series)

    assert result.metrics["active_days"] == sum(1 for p in series.points if p.video_count > 0)
    assert result.metrics["active_days"] == 4, "1 万播放那天没有样本，不能算有内容"
    assert result.metrics["series_days"] == len(values)
    assert result.metrics["view"] > 0


def test_meme_daily_stats_rows_are_untouched_by_the_gate(session, live_meme):
    """门槛只影响"上不上榜"，不许动底层数据：过气梗的序列还得能查。"""
    meme = live_meme("门槛保数据梗")
    for row in make_stats(meme.id, [10_000] * 6, end=date.today()):
        session.add(row)
    session.flush()
    _snap(session, meme, stage="obsolete")

    assert session.query(MemeDailyStats).filter_by(meme_id=meme.id).count() == 6
