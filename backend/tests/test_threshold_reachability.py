# -*- coding: utf-8 -*-
"""阈值可达性：配置里的每条阈值都必须"接了线"，且落在真实数据能到达的范围内。

来历：``CatchUpThresholds.caution_min_heat`` 曾经是 85.0，而全库最高热度只有 80.4、
``hotness_snapshots`` 里 ``score >= 85`` 的记录数为 0。那条规则连一次都没执行过，
所有「慎赶」都由文件末尾的兜底分支产出——兜底文案写的是「没有明显往上走的迹象」，
最后贴在 growth 高达 +82% 的上升期梗上，用户一眼就能看出自相矛盾。

既有的 ``test_catch_up.py`` 没发现，是因为它的用例把 heat 传成了 96.0：
一个现实中不可能出现的分数，恰好绕过了这个 bug。

**设计教训**：第一版这组测试用「扰动阈值 → 看输出是否改变」来判断可达性，
结果对兜底规则全部误报（把 receding_max_growth 抬高到 -0.2 之后，
``peak_gap + declining_days`` 那条规则接住了同一个输入，阶段没变）。
所以现在改成**直接用阈值的数值构造边界用例**：
阈值本身参与边界值的计算，输入不可能与阈值脱钩。
"""

from __future__ import annotations

import dataclasses

import pytest

from app.analytics import catch_up as catch_up_mod
from app.analytics.catch_up import STATUSES, decide
from app.analytics.hotness import compute_hotness
from app.analytics.lifecycle import LIFECYCLE_THRESHOLDS, LifecycleInput, classify
from app.analytics.series import DayPoint, Series, growth_rate
from app.config import CATCHUP_THRESHOLDS, HOTNESS_WEIGHTS

T = CATCHUP_THRESHOLDS
L = LIFECYCLE_THRESHOLDS


def _decide(*, stage, heat, growth, peak_heat, activity=60, view_7d=800_000,
            observed_days_7=7, active_days_7=7):
    inp = LifecycleInput(
        heat=heat, growth=growth, activity=activity, view_7d=view_7d,
        peak_heat=peak_heat, active_days_7=active_days_7,
        observed_days_7=observed_days_7,
    )
    return decide(inp, stage=stage, heat=heat, growth=growth,
                  peak_gap=inp.peak_gap, creator_growth=0.4)


def _classify(*, heat, growth, peak_heat, activity=60, view_7d=800_000,
              stale_days=0, declining_days=5, observed_days_7=7):
    return classify(LifecycleInput(
        heat=heat, growth=growth, activity=activity, view_7d=view_7d,
        peak_heat=peak_heat, stale_days=stale_days,
        declining_days=declining_days, observed_days_7=observed_days_7,
        active_days_7=7,
    ))


# --------------------------------------------------------------------------- #
# 1) 赶梗阈值：每个数值都要在边界两侧产生不同结论
# --------------------------------------------------------------------------- #
def test_too_late_max_growth_boundary():
    """正好跨过 too_late_max_growth，结论就该从"你来晚了"变成别的。"""
    below = _decide(stage="receding", heat=40.0, growth=T.too_late_max_growth - 0.02,
                    peak_heat=45.0)
    above = _decide(stage="receding", heat=40.0, growth=T.too_late_max_growth + 0.02,
                    peak_heat=45.0)
    assert below.status == "too_late"
    assert above.status != "too_late"
    assert {below.status, above.status} <= set(STATUSES) | {"insufficient"}


def test_too_late_min_peak_gap_boundary():
    """peak_gap 跨过阈值，退潮期就该从"慎赶"变成"你来晚了"。"""
    # peak_heat 反推：peak_gap = (peak-heat)/peak
    def heat_for(gap):
        return 40.0

    def peak_for(gap):
        return 40.0 / (1 - gap) if gap < 1 else 40.0

    below = _decide(stage="receding", heat=40.0, growth=-0.01,
                    peak_heat=peak_for(T.too_late_min_peak_gap - 0.03))
    above = _decide(stage="receding", heat=40.0, growth=-0.01,
                    peak_heat=peak_for(T.too_late_min_peak_gap + 0.03))
    assert below.status == "caution"
    assert above.status == "too_late"


def test_can_catch_min_growth_boundary():
    """正好跨过 can_catch_min_growth：刚够格 vs 不够格。"""
    peak = 61.0
    at = _decide(stage="rising", heat=60.0, growth=T.can_catch_min_growth + 0.005,
                 peak_heat=peak)
    under = _decide(stage="rising", heat=60.0, growth=T.can_catch_min_growth - 0.005,
                    peak_heat=peak)
    assert at.status == "can_catch"
    assert under.status != "can_catch"


def test_can_catch_max_peak_gap_boundary():
    """peak_gap 超过 can_catch_max_peak_gap 就不能再说"来得及"。"""
    heat = 60.0

    def peak_for(gap):
        return heat / (1 - gap)

    inside = _decide(stage="rising", heat=heat, growth=0.60,
                     peak_heat=peak_for(T.can_catch_max_peak_gap - 0.02))
    outside = _decide(stage="rising", heat=heat, growth=0.60,
                      peak_heat=peak_for(T.can_catch_max_peak_gap + 0.02))
    assert inside.status == "can_catch"
    assert outside.status != "can_catch"


def test_caution_min_peak_gap_boundary():
    """窗口收窄的判据是 peak_gap 的两侧必须给出不同结论。

    这条规则原来写成 ``heat >= 85``（全库最高 80.4，从未命中），
    后来改成 ``heat >= 70`` 仍然几乎不命中（只有 1 个梗 ≥70，且它的
    peak_gap 是 0.018）。现在判据换成 peak_gap，规则才真的在干活。
    """
    heat = 55.0

    def peak_for(gap):
        return heat / (1 - gap)

    # growth 取在 can_catch_min_growth 之下，避免被 can_catch 抢先
    growth = T.can_catch_min_growth - 0.05
    inside = _decide(stage="rising", heat=heat, growth=growth,
                     peak_heat=peak_for(T.caution_min_peak_gap + 0.03))
    outside = _decide(stage="rising", heat=heat, growth=growth,
                      peak_heat=peak_for(T.caution_min_peak_gap - 0.03))
    assert inside.rule in {"off_peak_mild", "off_peak_strong"}
    assert outside.rule != inside.rule


def test_caution_strong_peak_gap_boundary():
    """超过强离峰线时，措辞要从「收窄」升级为「明显收窄」，且仍不能提「放缓」。

    注意 growth 不能取在 can_catch 区间里：peak_gap 一旦超过
    ``can_catch_max_peak_gap``，spreading 就不成立，这时才轮到 off_peak 规则。
    """
    heat = 55.0
    growth = 0.60            # 明确在涨——所以绝不能说"增速放缓"

    def peak_for(gap):
        return heat / (1 - gap)

    # mild 这一档必须同时避开 spreading：peak_gap 要落在
    # [caution_min_peak_gap, can_catch_max_peak_gap] 之上，否则 can_catch 会先接住它。
    mild_gap = (T.can_catch_max_peak_gap + T.caution_strong_peak_gap) / 2
    mild = _decide(stage="rising", heat=heat, growth=growth,
                   peak_heat=peak_for(mild_gap))
    strong = _decide(stage="rising", heat=heat, growth=growth,
                     peak_heat=peak_for(T.caution_strong_peak_gap + 0.02))
    assert mild.rule == "off_peak_mild", f"gap={mild_gap:.3f} 命中 {mild.rule}"
    assert strong.rule == "off_peak_strong"
    for result in (mild, strong):
        assert "放缓" not in result.reason, (
            f"增速 +{growth:.0%} 却写成「{result.reason}」，与数字矛盾")


def test_caution_rule_does_not_steal_can_catch():
    """peak_gap 落在两条规则的重叠区间时，can_catch 必须优先。

    曾经把 peak_gap 规则排在 can_catch 之前，结果 peak_gap 在
    [caution_min_peak_gap, can_catch_max_peak_gap] 的梗明明在快速扩散，
    却永远拿不到"来得及"。
    """
    assert T.caution_min_peak_gap < T.can_catch_max_peak_gap, (
        "两条规则没有重叠区间的话，这个顺序问题就不存在了——"
        "如果哪天阈值调成不重叠，这条测试可以删掉")
    heat = 55.0
    gap = (T.caution_min_peak_gap + T.can_catch_max_peak_gap) / 2
    result = _decide(stage="rising", heat=heat, growth=0.80,
                     peak_heat=heat / (1 - gap))
    assert result.status == "can_catch", (
        f"peak_gap={gap:.3f} 落在重叠区间且增长 +80%，却判成 {result.label}"
        f"（规则 {result.rule}）")


def test_too_late_stages_and_can_catch_stages_are_actually_consulted():
    """阶段名单型阈值：名单里的阶段与非名单阶段必须走出不同结论。"""
    for stage in T.too_late_stages:
        assert _decide(stage=stage, heat=5.0, growth=None, peak_heat=40.0,
                       activity=0, view_7d=0).status == "too_late"
    # 不在名单里的阶段，即使参数一样也不该被判"你来晚了"
    assert _decide(stage="rising", heat=5.0, growth=None, peak_heat=40.0,
                   activity=0, view_7d=0).status != "too_late"

    for stage in T.can_catch_stages:
        result = _decide(stage=stage, heat=40.0, growth=0.0, peak_heat=40.0,
                         activity=5, view_7d=30_000)
        assert result.status in STATUSES


# --------------------------------------------------------------------------- #
# 2) 阈值必须落在系统真实能产生的数值范围内（这次 bug 的真正守门人）
# --------------------------------------------------------------------------- #
def test_caution_thresholds_are_reachable_by_real_peak_gaps():
    """慎赶门槛必须落在真实 peak_gap 分布之内。

    这次出问题的模式是：阈值本身合法（0<70<=100），但真实数据永远到不了。
    所以除了"数值合法"之外，还要有一条断言盯着"实际用得上"。
    当前库里 peak_gap 落在 0.10~0.35 的梗有 9 个（见 docs/改进建议.md A1）。
    """
    assert 0.0 < T.caution_min_peak_gap < T.caution_strong_peak_gap < 1.0
    # peak_gap 的实际可达上限就是 1.0（热度跌到 0），所以只需检查下界不能太高
    assert T.caution_min_peak_gap <= 0.15, (
        "门槛高于 0.15 会让大量梗直接掉进兜底分支——历史上就是这么出问题的")


def test_peak_gap_thresholds_are_within_range():
    """peak_gap 的定义域是 [0, 1)，所有用到它的阈值都必须落在这个区间。"""
    for name in ("too_late_min_peak_gap", "can_catch_max_peak_gap",
                 "caution_min_peak_gap", "caution_strong_peak_gap"):
        value = getattr(T, name)
        assert 0.0 <= value < 1.0, f"{name}={value} 不在 peak_gap 的定义域内"


def test_catchup_growth_thresholds_are_inside_the_scored_band():
    """增长阈值必须落在 growth_score 的可分辨区间内。

    打分把增长映射到 0-100：<= -30% 记 0 分、>= +120% 记 100 分。
    阈值超出这个区间就等于所有梗同分，规则失去区分力。
    """
    from app.config import GROWTH_SCORE_FULL, GROWTH_SCORE_ZERO

    for name in ("too_late_max_growth", "can_catch_min_growth"):
        value = getattr(T, name)
        assert GROWTH_SCORE_ZERO <= value <= GROWTH_SCORE_FULL, (
            f"{name}={value} 落在打分区间 [{GROWTH_SCORE_ZERO}, {GROWTH_SCORE_FULL}] 之外"
        )


# --------------------------------------------------------------------------- #
# 3) 生命周期阈值：边界两侧必须给出不同阶段
# --------------------------------------------------------------------------- #
def test_obsolete_thresholds_boundary():
    # stale_days
    assert _classify(heat=50.0, growth=0.5, peak_heat=50.0,
                     stale_days=L.obsolete_stale_days).stage == "obsolete"
    assert _classify(heat=50.0, growth=0.5, peak_heat=50.0,
                     stale_days=L.obsolete_stale_days - 1).stage != "obsolete"
    # activity / heat 一起看
    assert _classify(heat=L.obsolete_max_heat - 1, growth=0.0,
                     peak_heat=50.0, activity=L.obsolete_max_activity).stage == "obsolete"
    assert _classify(heat=L.obsolete_max_heat + 5, growth=0.0,
                     peak_heat=50.0, activity=L.obsolete_max_activity).stage != "obsolete"


def test_sprouting_thresholds_boundary():
    ok = dict(activity=L.sprouting_max_activity, view_7d=L.sprouting_max_view_7d,
              heat=L.sprouting_max_heat)
    assert _classify(growth=0.0, peak_heat=50.0, **ok).stage == "sprouting"
    bad_heat = dict(ok, heat=L.sprouting_max_heat + 5)
    assert _classify(growth=0.0, peak_heat=50.0, **bad_heat).stage != "sprouting"
    bad_activity = dict(ok, activity=L.sprouting_max_activity + 20)
    assert _classify(growth=0.0, peak_heat=50.0, **bad_activity).stage != "sprouting"


def test_explosive_thresholds_boundary():
    base = dict(activity=80, view_7d=900_000)
    # 热度门槛
    assert _classify(heat=L.explosive_min_heat, growth=L.explosive_min_growth,
                     peak_heat=L.explosive_min_heat, **base).stage == "explosive"
    assert _classify(heat=L.explosive_min_heat - 5, growth=L.explosive_min_growth,
                     peak_heat=L.explosive_min_heat, **base).stage != "explosive"
    # 增长门槛
    assert _classify(heat=L.explosive_min_heat, growth=L.explosive_min_growth - 0.05,
                     peak_heat=L.explosive_min_heat, **base).stage != "explosive"
    # peak_gap 门槛：峰值刻意抬高，让 gap 超过上限
    peak = L.explosive_min_heat / (1 - (L.explosive_max_peak_gap + 0.05))
    assert _classify(heat=L.explosive_min_heat, growth=L.explosive_min_growth,
                     peak_heat=peak, **base).stage != "explosive"


def test_rising_thresholds_boundary():
    base = dict(activity=80, view_7d=900_000, peak_heat=75.0)
    assert _classify(heat=L.rising_min_heat, growth=L.rising_min_growth, **base).stage == "rising"
    assert _classify(heat=L.rising_min_heat - 5, growth=L.rising_min_growth,
                     **base).stage != "rising"
    assert _classify(heat=L.rising_min_heat, growth=L.rising_min_growth - 0.05,
                     **base).stage != "rising"


def test_receding_thresholds_boundary():
    base = dict(activity=60, view_7d=800_000)
    # receding_max_growth
    assert _classify(heat=50.0, growth=L.receding_max_growth - 0.01,
                     peak_heat=55.0, **base).stage == "receding"
    # peak_gap + declining_days 这条分支：把它单独隔离出来
    peak = 70.0
    heat = peak * (1 - (L.receding_min_peak_gap + 0.05))
    assert _classify(heat=heat, growth=-0.06, peak_heat=peak,
                     declining_days=L.receding_min_declining_days, **base).stage == "receding"
    assert _classify(heat=heat, growth=-0.06, peak_heat=peak,
                     declining_days=L.receding_min_declining_days - 1, **base).stage != "receding"


def test_plateau_band_is_actually_used():
    """plateau_band 曾经配了却没人读：平稳期只是函数末尾的兜底 else。

    现在它是显式规则，所以必须能证明：增长落在中立带内 → 平稳期，
    且这条判定会随阈值变化。
    """
    peak = 61.0
    inside = _classify(heat=60.0, growth=L.plateau_band - 0.01, peak_heat=peak)
    assert inside.stage == "plateau"
    assert "持平" in inside.reasons[0]

    # 把带宽压到 0，同样的输入就不再是"持平"，说明阈值确实在参与判定
    import app.analytics.lifecycle as lifecycle_mod

    original = lifecycle_mod.LIFECYCLE_THRESHOLDS
    try:
        lifecycle_mod.LIFECYCLE_THRESHOLDS = dataclasses.replace(L, plateau_band=0.0)
        after = lifecycle_mod.classify(LifecycleInput(
            heat=60.0, growth=L.plateau_band - 0.01, activity=60, view_7d=800_000,
            peak_heat=peak, declining_days=5, observed_days_7=7, active_days_7=7))
    finally:
        lifecycle_mod.LIFECYCLE_THRESHOLDS = original
    assert "持平" not in after.reasons[0], (
        "plateau_band 被压到 0 后仍走「持平」分支，说明这个阈值没接线")


def test_min_observed_days_gate_boundary():
    base = dict(heat=50.0, growth=0.5, peak_heat=52.0)
    assert _classify(observed_days_7=L.min_observed_days, **base).stage != "insufficient"
    assert _classify(observed_days_7=L.min_observed_days - 1, **base).stage == "insufficient"


def test_insufficient_gate_never_reports_a_confidence():
    """闸门态必须给 0 置信度：界面上不能出现"0% 把握的某种判断"。"""
    result = _decide(stage="insufficient", heat=50.0, growth=0.5, peak_heat=52.0,
                     observed_days_7=L.min_observed_days - 1)
    assert result.status == "insufficient"
    assert result.confidence == 0.0


# --------------------------------------------------------------------------- #
# 4) 兜底文案不得与输入自相矛盾
# --------------------------------------------------------------------------- #
def test_fallback_never_claims_no_growth_when_growth_is_high():
    """上升期 + 高增长 + 已离峰：可以判"慎赶"，但不许说"没有往上走的迹象"。"""
    banned = ("没有明显往上走", "没有往上走", "没什么动静")
    for heat in (30.0, 45.0, 60.0, 70.0, 78.0):
        for growth in (0.16, 0.30, 0.60, 0.90):
            result = _decide(stage="rising", heat=heat, growth=growth,
                             peak_heat=min(100.0, heat * 1.4))
            for word in banned:
                assert word not in result.reason, (
                    f"heat={heat} growth={growth} 判成 {result.label}，"
                    f"理由却写成「{result.reason}」——与 +{growth:.0%} 的增长矛盾"
                )


def test_reason_never_predicts_the_future():
    """文档 §十九：不得出现"未来 7 天/一定会爆/预计增长"这类预测。"""
    banned = ["未来", "预测", "预计", "一定会", "明天", "下周", "AI认为", "大模型"]
    for case in [
        dict(stage="explosive", heat=80.0, growth=1.5, peak_heat=81.0),
        dict(stage="rising", heat=70.0, growth=0.9, peak_heat=71.0),
        dict(stage="plateau", heat=45.0, growth=0.0, peak_heat=47.0),
        dict(stage="receding", heat=30.0, growth=-0.3, peak_heat=60.0),
        dict(stage="obsolete", heat=3.0, growth=None, peak_heat=40.0, activity=0,
             view_7d=0),
    ]:
        reason = _decide(**case).reason
        for word in banned:
            assert word not in reason, f"{reason} 含有不该出现的 {word}"


# --------------------------------------------------------------------------- #
# 5) 热度权重
# --------------------------------------------------------------------------- #
def test_hotness_weights_sum_to_one():
    total = (HOTNESS_WEIGHTS.view + HOTNESS_WEIGHTS.interaction + HOTNESS_WEIGHTS.content
             + HOTNESS_WEIGHTS.creator + HOTNESS_WEIGHTS.growth)
    assert abs(total - 1.0) < 1e-9, f"五因子权重合计 {total}，不等于 1.0"


def test_creator_component_uses_peak_not_weekly_sum():
    """创作者分量必须用「单日去重峰值」，不能用「周累计」。

    历史问题：``creator_count`` 在采集层是当日去重作者数，而样本里几乎每条视频
    来自不同作者（实测 creator_count / video_count 中位数 = 1.000），
    聚合层再逐日累加，就等于「视频数换了个名字」：
    content 与 creator 分量的相关系数一度是 **0.9997**，
    权重 0.16 + 0.14 = 0.30 实际全给了一个因子。

    下面两组序列 video_count 完全相同，只有「作者是否重复出现」不同：
    只有用峰值打分，两组的 creator 分量才会不一样。
    """
    from datetime import date, timedelta

    def build(creators_per_day):
        return Series(meme_id=901, points=[
            DayPoint(day=date.today() - timedelta(days=n), video_count=20,
                     creator_count=creators_per_day[n], view=400_000,
                     reply=1_000, danmaku=500, observed=True)
            for n in range(14)])

    flat = build([8] * 14)            # 作者稳定：周累计 112，峰值 8
    bursty = build([8] * 13 + [24])   # 最后一天作者翻三倍：周累计 128，峰值 24

    a = compute_hotness(flat)
    b = compute_hotness(bursty)

    assert a.components["content"] == b.components["content"]
    assert b.components["creator"] > a.components["creator"], (
        "两组单日作者峰值是 8 vs 24，creator 分量却分不出来——"
        "说明打分用的还是周累计（112 vs 128，只差 14%）"
    )
    assert abs(128 - 112) / 112 < 0.15   # 周累计口径失效的原因


def test_metrics_expose_both_creator_measures():
    """两个口径都留在 metrics 里，但打分与界面百分比必须同用峰值。"""
    from datetime import date, timedelta

    series = Series(meme_id=902, points=[
        DayPoint(day=date.today() - timedelta(days=n), video_count=10,
                 creator_count=4, view=200_000, reply=300, danmaku=100, observed=True)
        for n in range(14)])
    metrics = compute_hotness(series).metrics
    assert metrics["creator_peak"] == 4
    assert metrics["creator_count"] == 4 * 7      # 日累计，会随天数膨胀
    assert metrics["prev_creator_peak"] == 4
    assert metrics["creator_growth"] == growth_rate(4, 4)
