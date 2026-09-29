"""赶梗判断：现在赶这个梗还来得及吗？

结论落在三个枚举上：``can_catch`` / ``caution`` / ``too_late``。
另有第四个值 ``insufficient``——它不是结论，是**闸门**：最近 7 天真正观测到的
天数不够时，宁可不给结论，也不给一个建在接口空洞上的结论。

**由算法决定，不由 LLM 决定。** LLM 只拿到这里算好的指标，把结论讲成人话；
LLM 不可用时，本模块给出的规则文案也能直接把卡片填满，产品不瘸腿。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import CATCHUP_EMOJI, CATCHUP_LABELS, CATCHUP_THRESHOLDS

from .lifecycle import LifecycleInput

STATUSES = ("can_catch", "caution", "too_late")
# 闸门值：出现在观测天数不足时，不属于"结论"
INSUFFICIENT = "insufficient"


@dataclass
class CatchUpResult:
    status: str
    label: str
    emoji: str
    reason: str
    confidence: float
    indicators: dict[str, Any] = field(default_factory=dict)
    # 哪一条规则给出的结论。同一种 status 可能由多条规则产出
    # （比如"慎赶"既可能来自退潮、也可能来自高热度离峰、还可能是兜底），
    # 所以只断言 status 是不够的——测试与排查都需要知道到底是哪条命中。
    rule: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "label": self.label,
            "emoji": self.emoji,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
        }


def _stability(inp: LifecycleInput) -> float:
    """数据稳定性：近 7 天有多少天真的在产出内容。"""
    return max(0.0, min(1.0, inp.active_days_7 / 7.0))


def decide(
    inp: LifecycleInput,
    *,
    stage: str,
    heat: float,
    growth: float | None,
    peak_gap: float,
    creator_growth: float | None = None,
) -> CatchUpResult:
    t = CATCHUP_THRESHOLDS
    g = 0.0 if growth is None else growth
    stability = _stability(inp)
    margin = 0.0

    # 闸门：观测天数不够就不给结论。这里的 confidence 必须是 0，
    # 界面上"置信度 0"就是"算法没敢说"，不能显示成 0% 把握的某种判断。
    if stage == "insufficient":
        return CatchUpResult(
            status=INSUFFICIENT,
            label=CATCHUP_LABELS[INSUFFICIENT],
            emoji=CATCHUP_EMOJI[INSUFFICIENT],
            reason=(
                f"最近 7 天只观测到 {inp.observed_days_7} 天数据，说不准是在涨还是在退。"
                f"先等采集把洞补上再决定赶不赶。"
            ),
            confidence=0.0,
            rule="insufficient_data",
            indicators={
                "stage": stage,
                "heat": round(heat, 1),
                "growth": None if growth is None else round(growth, 3),
                "peak_gap": round(peak_gap, 3),
                "creator_growth": None if creator_growth is None else round(creator_growth, 3),
                "stability": round(stability, 2),
                "observed_days_7": inp.observed_days_7,
                "rule": "insufficient_data",
            },
        )

    if stage == "obsolete":
        status, reason = "too_late", "这个梗已经没什么人做了，现在赶上去会被当成考古。"
        margin, rule = 0.9, "obsolete"
    elif stage == "receding" and (g <= t.too_late_max_growth or peak_gap >= t.too_late_min_peak_gap):
        status = "too_late"
        reason = "热度已经从峰值掉下来一截，新增内容也在减少，现在赶有点晚了。"
        margin, rule = 0.6, "receding_off_peak"
    elif stage == "receding":
        status = "caution"
        reason = "整体还在往下走，发出去可能没什么水花，除非你有特别新的玩法。"
        margin, rule = 0.3, "receding_mild"
    elif stage == "sprouting":
        status = "can_catch"
        reason = "这个梗才刚冒头，现在进去算早的，做起来还有空间。"
        margin, rule = 0.5, "sprouting"
    elif g >= t.can_catch_min_growth and peak_gap <= t.can_catch_max_peak_gap:
        status = "can_catch"
        creators = (
            "，参与创作的 UP 主也还在增加"
            if (creator_growth or 0) > 0
            else ""
        )
        reason = f"最近仍在快速扩散{creators}，现在赶还来得及。"
        margin, rule = min(1.0, g / max(t.can_catch_min_growth, 1e-6) / 4), "spreading"
    elif peak_gap >= t.caution_min_peak_gap:
        # 窗口在收窄 = 已经离开近期峰值一段。判据是 peak_gap，不是热度：
        # 热度高低已经由上升/爆发/退潮那几条规则管过了，这里只管"还剩多少"。
        #
        # 位置很关键：必须排在 can_catch **之后**。否则 peak_gap 落在
        # [caution_min_peak_gap, can_catch_max_peak_gap] 的梗会被这条抢先吃掉，
        # 明明还在快速扩散却永远拿不到"来得及"。
        status = "caution"
        if peak_gap >= t.caution_strong_peak_gap:
            # 明确离峰：即使还在涨也不能说"增速放缓"，那与数字矛盾。
            reason = "已经离开近期峰值一段，热度在往下走，窗口明显收窄了。"
            rule = "off_peak_strong"
        else:
            reason = "已经离开近期峰值一点，窗口在收窄，想赶得快点。"
            rule = "off_peak_mild"
        margin = 0.4
    elif stage == "plateau" and heat < 50:
        status = "can_catch"
        reason = "热度不高但一直很稳，属于还能塞得下新内容的类型。"
        margin, rule = 0.2, "plateau_low_heat"
    elif stage == "plateau":
        status = "caution"
        reason = "这个梗已经稳定下来了，不太会再爆一波，赶上去更多是蹭个脸熟。"
        margin, rule = 0.25, "plateau_settled"
    else:
        # 兜底：既没涨到能明确说"来得及"，也没退到该说"你晚了"。
        # 这里**不能**断言"没有往上走的迹象"——历史版本就是这么写的，
        # 结果它落在 growth +82% 的上升期梗上，用户一眼就能看出自相矛盾。
        # 兜底文案只描述"现在还不够明确"，不替数据下结论。
        status = "caution"
        reason = "热度和增速都还没有明确方向，现在赶性价比一般，可以再等等更清楚的信号。"
        margin, rule = 0.2, "fallback"

    confidence = 0.55 + 0.25 * stability + 0.20 * min(1.0, margin)
    if inp.view_7d <= 0 and inp.activity == 0:
        confidence = 0.4

    return CatchUpResult(
        status=status,
        label=CATCHUP_LABELS[status],
        emoji=CATCHUP_EMOJI[status],
        reason=reason,
        confidence=max(0.3, min(0.95, confidence)),
        rule=rule,
        indicators={
            "stage": stage,
            "heat": round(heat, 1),
            "growth": None if growth is None else round(growth, 3),
            "peak_gap": round(peak_gap, 3),
            "creator_growth": None if creator_growth is None else round(creator_growth, 3),
            "stability": round(stability, 2),
            # 具体命中的规则名（不再是笼统的 "algorithm"）：
            # 同一种 status 可能来自多条规则，排查时必须分得清。
            "rule": rule,
        },
    )
