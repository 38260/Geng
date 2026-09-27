"""赶梗判断：状态只能落在三个枚举上，且必须由算法决定。"""

from __future__ import annotations

from app.analytics.catch_up import STATUSES, decide
from app.analytics.lifecycle import LifecycleInput


def run(*, stage, heat, growth, peak_heat, activity=60, view_7d=800_000, active_days_7=7,
        stale_days=0, creator_growth=0.4):
    inp = LifecycleInput(
        heat=heat, growth=growth, activity=activity, view_7d=view_7d,
        peak_heat=peak_heat, stale_days=stale_days, active_days_7=active_days_7,
    )
    return decide(inp, stage=stage, heat=heat, growth=growth,
                  peak_gap=inp.peak_gap, creator_growth=creator_growth)


def test_status_is_always_one_of_three_enums():
    cases = [
        dict(stage="explosive", heat=94.0, growth=1.6, peak_heat=95.0),
        dict(stage="rising", heat=70.0, growth=0.9, peak_heat=71.0),
        dict(stage="plateau", heat=45.0, growth=0.0, peak_heat=47.0),
        dict(stage="receding", heat=30.0, growth=-0.3, peak_heat=60.0),
        dict(stage="obsolete", heat=3.0, growth=None, peak_heat=40.0, stale_days=21,
             activity=0, view_7d=0, active_days_7=0),
        dict(stage="sprouting", heat=38.0, growth=1.0, peak_heat=38.0, activity=6,
             view_7d=40_000),
    ]
    for case in cases:
        result = run(**case)
        assert result.status in STATUSES
        assert result.label and result.emoji and result.reason
        assert 0.0 <= result.confidence <= 1.0


def test_obsolete_is_too_late():
    result = run(stage="obsolete", heat=3.0, growth=None, peak_heat=40.0,
                 stale_days=21, activity=0, view_7d=0, active_days_7=0)
    assert result.status == "too_late"
    assert result.confidence < 0.5  # 没数据的梗，判断置信度必须低


def test_receding_from_peak_is_too_late():
    result = run(stage="receding", heat=32.0, growth=-0.33, peak_heat=60.0)
    assert result.status == "too_late"


def test_still_spreading_is_can_catch():
    result = run(stage="rising", heat=74.0, growth=0.93, peak_heat=75.0)
    assert result.status == "can_catch"
    assert "来得及" in result.reason


def test_at_peak_but_decelerating_is_caution():
    result = run(stage="explosive", heat=96.0, growth=1.4, peak_heat=112.0)
    assert result.status == "caution"


def test_reason_never_pretends_to_predict_the_future():
    """文档 §十九：不得出现"未来 7 天/一定会爆/预计增长"这类预测。"""
    banned = ["未来", "预测", "预计", "一定会", "明天", "下周", "AI认为", "大模型"]
    for case in [
        dict(stage="explosive", heat=94.0, growth=1.6, peak_heat=95.0),
        dict(stage="rising", heat=70.0, growth=0.9, peak_heat=71.0),
        dict(stage="plateau", heat=45.0, growth=0.0, peak_heat=47.0),
        dict(stage="receding", heat=30.0, growth=-0.3, peak_heat=60.0),
    ]:
        reason = run(**case).reason
        for word in banned:
            assert word not in reason, f"{reason} 含有不该出现的 {word}"


def test_to_dict_shape_matches_spec():
    result = run(stage="rising", heat=74.0, growth=0.93, peak_heat=75.0)
    payload = result.to_dict()
    assert set(payload) == {"status", "label", "emoji", "reason", "confidence"}
    assert payload["status"] == "can_catch"
    assert payload["label"] == "还来得及"
