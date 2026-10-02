"""梗史馆：近 N 天入池的梗 + 历史周期画像。

守两类事：

1. **入池口径**必须与读侧闸门一致（认证窗口内 + 真实 bilibili 证据），
   不能因为多了一个页面就放宽成"库里所有梗"；
2. **周期判定**要能被指纹到具体条件上——观测洞不许当零活动、
   半衰期算不出来要如实说"未腰斩"而不是"没数据"。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Meme, MemeDailyStats, MemeStatus, SessionLocal
from app.services.meme.certification import ENCYCLOPEDIA, GUIDE, record_certification
from app.services.meme.history import CYCLE_LABELS, _classify_cycle, history_payload

END = date(2026, 9, 30)


def _meme(session, name: str) -> Meme:
    meme = Meme(
        name=name,
        slug=f"history-{name}",
        aliases=[],
        keywords=[name],
        status=MemeStatus.CERTIFIED,
        certified=True,
        encyclopedia_confirmed=True,
        guide_confirmed=True,
        verification_state="verified_both",
        data_source="bilibili",
    )
    session.add(meme)
    session.flush()
    return meme


def _certify(session, meme: Meme, *, days_ago: int = 2, role: str = "encyclopedia", source: str = "bilibili"):
    author = ENCYCLOPEDIA if role == "encyclopedia" else GUIDE
    record_certification(
        session,
        meme,
        role,
        bvid=f"BV{meme.id:04d}{role[:3]}",
        video_title=f"{meme.name}是什么梗",
        published_at=datetime.now() - timedelta(days=days_ago),
        data_source=source,
    )


def _stats(
    session,
    meme: Meme,
    hotness: list[float],
    *,
    observed: list[bool] | None = None,
    end: date = END,
) -> None:
    total = len(hotness)
    for index, value in enumerate(hotness):
        session.add(
            MemeDailyStats(
                meme_id=meme.id,
                stat_date=end - timedelta(days=total - 1 - index),
                video_count=1 if value > 0 else 0,
                creator_count=1 if value > 0 else 0,
                view=int(value * 1000),
                reply=int(value * 10),
                danmaku=int(value * 20),
                hotness=value,
                observed=True if observed is None else observed[index],
                data_source="bilibili",
            )
        )
    session.flush()


def _by_name(payload: dict) -> dict[str, dict]:
    return {item["name"]: item for item in payload["items"]}


# --------------------------------------------------------------------------- #
# 入池口径
# --------------------------------------------------------------------------- #
def test_pool_only_takes_in_window_real_evidence(session):
    """窗口外的老梗、以及演示证据，都不算"这三个月里的梗"。"""
    inside = _meme(session, "窗口内梗")
    _certify(session, inside, days_ago=5)

    stale = _meme(session, "窗口外老梗")
    _certify(session, stale, days_ago=200)

    demo = _meme(session, "演示证据梗")
    _certify(session, demo, days_ago=5, source="mock")

    _stats(session, inside, [50.0, 60.0])
    _stats(session, stale, [90.0, 90.0])
    _stats(session, demo, [80.0, 80.0])

    names = [item["name"] for item in history_payload(session, days=90)["items"]]
    assert "窗口内梗" in names
    assert "窗口外老梗" not in names
    assert "演示证据梗" not in names


def test_window_days_controls_admission_not_observation(session):
    """``days`` 是入池窗口：调窄它会把老梗筛掉，而不是截断曲线。"""
    old = _meme(session, "两个月前入池梗")
    _certify(session, old, days_ago=60)
    _stats(session, old, [10.0, 40.0, 70.0, 40.0])

    wide = history_payload(session, days=90)
    assert old.id in {item["id"] for item in wide["items"]}
    narrow = history_payload(session, days=30)
    assert old.id not in {item["id"] for item in narrow["items"]}
    # 曲线本身没被 days 截断：窗口再窄，观测格数还是 4
    assert _by_name(wide)["两个月前入池梗"]["window_days"] == 4


# --------------------------------------------------------------------------- #
# 周期判定
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("total", "peak_index", "current_ratio", "half_life", "expected"),
    [
        (10, 9, 0.95, None, "rising"),        # 峰在末端且还贴着峰
        (10, 9, 0.40, 1, "pulse"),            # 末端见峰但已经掉下去了 → 按半衰期判
        (10, 2, 0.30, 3, "pulse"),            # 见峰后 3 天腰斩
        (10, 2, 0.80, 6, "long_tail"),        # 半衰期 6 天，超出脉冲阈值
        (10, 2, 0.80, None, "long_tail"),     # 压根没腰斩
    ],
)
def test_cycle_classification_is_pinned_to_conditions(
    total, peak_index, current_ratio, half_life, expected
):
    assert (
        _classify_cycle(
            total=total,
            peak_index=peak_index,
            current_ratio=current_ratio,
            half_life=half_life,
        )
        == expected
    )


def test_pulse_needs_a_real_half_life(session):
    """峰在第 4 天、两天内腰斩 → 脉冲型。"""
    meme = _meme(session, "脉冲梗")
    _certify(session, meme)
    _stats(session, meme, [10.0, 20.0, 45.0, 90.0, 40.0, 20.0, 10.0])

    item = _by_name(history_payload(session, days=90))["脉冲梗"]
    assert item["cycle"] == "pulse"
    assert item["half_life_days"] == 1
    assert item["peak_date"] == "2026-09-27"


def test_still_high_means_no_half_life_not_missing_data(session):
    """一直没跌到一半 → 半衰期是 None，意思是"未腰斩"，不是"算不出来"。"""
    meme = _meme(session, "长尾梗")
    _certify(session, meme)
    _stats(session, meme, [60.0, 90.0, 88.0, 85.0, 82.0, 80.0, 78.0])

    item = _by_name(history_payload(session, days=90))["长尾梗"]
    assert item["cycle"] == "long_tail"
    assert item["half_life_days"] is None
    assert item["days_since_peak"] == 5


def test_rising_needs_peak_at_the_tail(session):
    meme = _meme(session, "上升梗")
    _certify(session, meme)
    _stats(session, meme, [20.0, 35.0, 50.0, 65.0, 80.0, 88.0, 92.0])

    item = _by_name(history_payload(session, days=90))["上升梗"]
    assert item["cycle"] == "rising"
    assert item["off_peak"] == pytest.approx(0.0)


def test_no_observed_day_never_becomes_peak(session):
    """接口给空壳的那天不进峰值、也不进活跃天数——它只该降低覆盖度。"""
    meme = _meme(session, "有洞的梗")
    _certify(session, meme)
    _stats(
        session,
        meme,
        [30.0, 99.0, 40.0, 50.0, 60.0],
        observed=[True, False, True, True, True],
    )

    item = _by_name(history_payload(session, days=90))["有洞的梗"]
    assert item["peak_hotness"] == 60.0
    assert item["observed_days"] == 4
    assert item["window_days"] == 5
    assert item["coverage"] == pytest.approx(0.8)
    # 没观测到的那天在轨迹里必须带 observed=False，界面据此画空档
    assert [point["observed"] for point in item["spark"]] == [True, False, True, True, True]


def test_no_observed_data_gives_gate_state_not_a_cycle(session):
    meme = _meme(session, "全是洞的梗")
    _certify(session, meme)
    _stats(session, meme, [0.0, 0.0, 0.0], observed=[False, False, False])

    item = _by_name(history_payload(session, days=90))["全是洞的梗"]
    assert item["cycle"] == "no_data"
    assert item["cycle_label"] == CYCLE_LABELS["no_data"]
    assert item["observed_days"] == 0


def test_truncated_flag_says_the_cycle_start_was_not_observed(session):
    """入池早于观测窗起点，周期左端被截断——必须标出来，不能装作 climb 只花 0 天。"""
    early = _meme(session, "早入池梗")
    _certify(session, early, days_ago=60)
    _stats(session, early, [10.0, 40.0, 70.0, 40.0])

    late = _meme(session, "近入池梗")
    _certify(session, late, days_ago=2)
    _stats(session, late, [10.0, 40.0, 70.0, 40.0])

    items = _by_name(history_payload(session, days=90))
    assert items["早入池梗"]["truncated"] is True
    assert items["近入池梗"]["truncated"] is False


# --------------------------------------------------------------------------- #
# 筛选与接口
# --------------------------------------------------------------------------- #
def test_filters_and_counts_share_one_set(session):
    """筛选行上的数字必须等于点进去的条数。"""
    rising = _meme(session, "筛选上升梗")
    _certify(session, rising)                          # 梗百科
    _certify(session, rising, role="guide")            # 再加梗指南 → 双 UP
    _stats(session, rising, [20.0, 40.0, 60.0, 80.0, 90.0])

    pulse = _meme(session, "筛选脉冲梗")
    _certify(session, pulse, role="guide")
    _stats(session, pulse, [10.0, 20.0, 45.0, 90.0, 40.0, 18.0, 9.0])

    payload = history_payload(session, days=90, cycle="rising")
    assert [item["name"] for item in payload["items"]] == ["筛选上升梗"]
    assert payload["summary"]["returned"] == 1
    counts = {entry["key"]: entry["count"] for entry in payload["summary"]["by_cycle"]}
    # 计数与列表走的是同一个集合，所以两者必须一致
    assert counts["rising"] == payload["summary"]["returned"] == 1
    assert counts["pulse"] == 0

    double = history_payload(session, days=90, cert="double")
    assert [item["name"] for item in double["items"]] == ["筛选上升梗"]
    single = history_payload(session, days=90, cert="single")
    assert [item["name"] for item in single["items"]] == ["筛选脉冲梗"]


def test_sort_orders(session):
    low = _meme(session, "低峰梗")
    _certify(session, low)
    _stats(session, low, [30.0, 40.0, 50.0])

    high = _meme(session, "高峰梗")
    _certify(session, high, days_ago=1)
    _stats(session, high, [40.0, 60.0, 90.0])

    peak = [item["name"] for item in history_payload(session, days=90, sort="peak")["items"]]
    assert peak.index("高峰梗") < peak.index("低峰梗")

    recent = [item["name"] for item in history_payload(session, days=90, sort="recent")["items"]]
    assert recent.index("高峰梗") < recent.index("低峰梗")

    by_name = [item["name"] for item in history_payload(session, days=90, sort="name")["items"]]
    assert by_name.index("低峰梗") < by_name.index("高峰梗")


def test_last_trajectory_cell_matches_the_current_stage(session):
    """轨迹最后一格必须与「当前阶段」是同一次判定。

    两者用不同的数据源（前者逐日预算、后者读快照），一旦判定协议漂了，
    同一行里就会出现"右上角写上升期、最后一格是黄的"这种自相矛盾。
    这里用管线真算一遍快照来守这条不变量。
    """
    from app.models import LifecycleSnapshot
    from app.services.pipeline import recompute_meme

    meme = _meme(session, "口径一致梗")
    _certify(session, meme)
    _stats(session, meme, [12.0, 18.0, 26.0, 40.0, 55.0, 63.0, 70.0, 74.0, 71.0, 66.0])

    recompute_meme(session, meme)
    # 会话是 autoflush=False 的（生产里也是），查询前要显式 flush 才看得见新写的快照
    session.flush()
    snapshot = session.get(LifecycleSnapshot, meme.id)
    assert snapshot is not None

    item = _by_name(history_payload(session, days=90))["口径一致梗"]
    assert item["spark"][-1]["stage"] == snapshot.stage == item["stage"]


def test_trend_bars_carry_the_same_stage_as_the_badge(session):
    """详情页热度柱的颜色就是结论，必须与「当前阶段」徽章同一次判定。

    一旦判定协议漂了，同一屏里会同时出现"徽章写平稳期、最后一根柱子是蓝的"。
    与上面梗史馆那条不变量同源，共用 `stage_path_for_rows` 这一份复算实现。
    """
    from app.models import LifecycleSnapshot
    from app.services.meme.query import trend_payload
    from app.services.pipeline import recompute_meme

    meme = _meme(session, "柱子口径梗")
    _certify(session, meme)
    _stats(session, meme, [12.0, 18.0, 26.0, 40.0, 55.0, 63.0, 70.0, 74.0, 71.0, 66.0])

    recompute_meme(session, meme)
    session.flush()
    snapshot = session.get(LifecycleSnapshot, meme.id)
    assert snapshot is not None

    payload = trend_payload(session, meme.id, 30)
    assert payload["points"][-1]["stage"] == snapshot.stage
    # 每一天都要有阶段：缺一天就有一根柱子掉色，看起来像数据坏了
    assert all(point["stage"] for point in payload["points"])


def test_api_contract_and_validation(session):
    """参数写错一律 400（不静默返回空列表），正常请求给出完整形状。"""
    client = TestClient(app)
    ok = client.get("/api/history?days=90&sort=peak")
    assert ok.status_code == 200
    body = ok.json()
    for key in ("generated_at", "days", "window_days", "rule", "summary", "items"):
        assert key in body
    assert body["summary"]["window_days"] >= 0
    assert body["data_source"]

    assert client.get("/api/history?cycle=zzz").status_code == 400
    assert client.get("/api/history?stage=zzz").status_code == 400
    assert client.get("/api/history?cert=zzz").status_code == 400
    assert client.get("/api/history?sort=zzz").status_code == 400
    assert client.get("/api/history?days=3").status_code == 422


def test_empty_library_does_not_break_the_page(session):
    """不管库里有没有梗，返回结构都要齐——页面不该为 undefined 做防御。"""
    payload = history_payload(session, days=90)
    assert isinstance(payload["items"], list)
    assert payload["rule"]
    assert payload["summary"]["returned"] == len(payload["items"])
    assert {entry["key"] for entry in payload["summary"]["by_cycle"]} == set(CYCLE_LABELS)
