"""LLM 业务层：趋势解释 + 赶梗建议。

业务代码只调用这里的两个函数，不直接接触 LongCat：

    generate_trend_explanation(...)
    generate_catch_up_advice(...)

三条硬规则在这里落地：
1. **AI 不是单点故障**：没配 Key、超时、429、返回不合法，一律降级，
   核心数据（热度/生命周期/图表）照常返回，AI 位置给出可重试的提示。
2. **AI 不能改事实**：赶梗状态由算法决定，模型返回的 status 与算法不一致时，
   以算法为准，只采纳它写的文案。
3. **结果按数据版本缓存**：``(meme_id, kind, data_version)`` 命中就不再打接口。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger, settings
from app.models import AIInsight, InsightKind, InsightSource, InsightStatus

from .client import LLMError, LLMNotConfiguredError, chat
from .config import LLMConfig, load_config

log = get_logger(__name__)

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"
PROMPT_TOKEN = "{{DATA}}"

# 模型输出里不该出现的词：预测未来 / 自我指认为 AI
BANNED_OUTPUT_WORDS = ("未来7天", "未来 7 天", "预计", "一定会爆", "明天会", "AI认为", "AI 认为", "大模型", "模型判断")
MAX_TREND_CHARS = 140


@dataclass
class InsightOutput:
    kind: str
    status: str                      # ok | unavailable
    source: str                      # llm | rule | cache | none
    model: str = ""
    data_version: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.status == InsightStatus.OK

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind,
            "status": self.status,
            "source": self.source,
            "data_version": self.data_version,
            "generated_at": self.generated_at.isoformat(),
            **self.result,
        }
        if self.model:
            payload["model"] = self.model
        if self.error:
            payload["error"] = self.error
        return payload


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
_prompt_cache: dict[str, str] = {}


def load_prompt(name: str) -> str:
    if name not in _prompt_cache:
        path = PROMPT_DIR / f"{name}.txt"
        if not path.exists():
            raise FileNotFoundError(f"缺少提示词文件：{path}")
        _prompt_cache[name] = path.read_text(encoding="utf-8")
    return _prompt_cache[name]


def render_prompt(name: str, data: dict[str, Any]) -> str:
    return load_prompt(name).replace(PROMPT_TOKEN, json.dumps(data, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- #
# 输出清洗
# --------------------------------------------------------------------------- #
def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip().strip('"').strip()


def parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = _strip_fences(text)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def looks_like_prediction(text: str) -> bool:
    return any(word in text for word in BANNED_OUTPUT_WORDS)


# --------------------------------------------------------------------------- #
# 规则兜底文案（LLM 不可用时也能把卡片填满）
# --------------------------------------------------------------------------- #
def rule_based_trend(data: dict[str, Any]) -> str:
    stage = data.get("lifecycle_label") or ""
    growth = data.get("growth")
    peak_gap = data.get("peak_gap") or 0
    creator_growth = data.get("creator_growth")

    if data.get("lifecycle") == "obsolete":
        return "这个梗已经没什么新内容了，现在看到的基本都是考古向二创。"
    if data.get("lifecycle") == "sprouting":
        return "才刚有 UP 主开始做，量还不大，属于早看到的阶段。"
    if growth is None:
        return f"目前处于{stage}，近两周样本还不多，先观察一下节奏。"

    if growth >= 1.0:
        first = "最近一周相关内容在快速翻倍式增长，讨论和弹幕也跟着起来。"
    elif growth >= 0.15:
        first = "最近一周相关内容增长明显，参与创作的 UP 主数量也在增加。"
    elif growth > -0.12:
        first = "最近一周的量基本持平，没有明显往上冲，也没有往下掉。"
    else:
        first = "最近一周新增内容和讨论都在往下走，热度已经过了最猛的那一段。"

    second = ""
    if creator_growth is not None and creator_growth > 0.1:
        second = "还有新 UP 主持续进来做，扩散没停。"
    elif peak_gap >= 0.25:
        second = "已经离近期峰值有一段距离了。"
    elif data.get("lifecycle") == "plateau":
        second = "属于稳定存在、不太会突然爆的类型。"

    return (first + second).strip()


# --------------------------------------------------------------------------- #
# 缓存 + 调用
# --------------------------------------------------------------------------- #
def _find_cached(session: Session, meme_id: int, kind: str, data_version: str) -> AIInsight | None:
    return session.scalar(
        select(AIInsight).where(
            AIInsight.meme_id == meme_id,
            AIInsight.kind == kind,
            AIInsight.data_version == data_version,
            AIInsight.status == InsightStatus.OK,
        )
    )


def _save(
    session: Session,
    *,
    meme_id: int,
    kind: str,
    data_version: str,
    result: dict[str, Any],
    source: str,
    model: str,
    status: str = InsightStatus.OK,
    latency_ms: int = 0,
) -> AIInsight:
    row = _find_cached(session, meme_id, kind, data_version)
    if row is None:
        row = AIInsight(meme_id=meme_id, kind=kind, data_version=data_version)
        session.add(row)
    row.result = result
    row.source = source
    row.model = model
    row.status = status
    row.latency_ms = latency_ms
    row.generated_at = datetime.now()
    session.flush()
    return row


def _insight_from_row(row: AIInsight, kind: str) -> InsightOutput:
    return InsightOutput(
        kind=kind,
        status=row.status,
        source=InsightSource.CACHE,
        model=row.model,
        data_version=row.data_version,
        generated_at=row.generated_at or datetime.now(),
        result=dict(row.result or {}),
    )


def generate(
    session: Session,
    *,
    meme_id: int,
    kind: str,
    data: dict[str, Any],
    data_version: str,
    config: LLMConfig | None = None,
    force_refresh: bool = False,
) -> InsightOutput:
    """生成一类 AI 结果，自动走缓存 / 降级。"""
    config = config or load_config()

    if not force_refresh:
        cached = _find_cached(session, meme_id, kind, data_version)
        if cached is not None:
            return _insight_from_row(cached, kind)

    prompt_name = "trend-explanation" if kind == InsightKind.TREND_EXPLANATION else "catch-up-advice"
    expected_status = data.get("status") if kind == InsightKind.CATCH_UP_ADVICE else None

    if not config.is_configured:
        reason = "未配置 LLM_API_KEY"
        if settings.llm_allow_rule_based_fallback:
            if kind == InsightKind.TREND_EXPLANATION:
                result = {"text": rule_based_trend(data)}
            else:
                # 赶梗建议优先复用算法已经写好的那句判断
                result = _catch_up_result(data, str(data.get("algorithm_reason") or ""))
            row = _save(
                session, meme_id=meme_id, kind=kind, data_version=data_version,
                result=result, source=InsightSource.RULE, model="rule-based",
            )
            log.info("LLM 未配置，%s/%s 使用算法兜底文案", meme_id, kind)
            return InsightOutput(
                kind=kind, status=InsightStatus.OK, source=InsightSource.RULE,
                model="rule-based", data_version=data_version,
                generated_at=row.generated_at, result=result, error=reason,
            )
        return InsightOutput(
            kind=kind, status=InsightStatus.UNAVAILABLE, source="none",
            data_version=data_version, result={}, error=reason,
        )

    try:
        completion = chat(config, [{"role": "user", "content": render_prompt(prompt_name, data)}])
    except (LLMError, LLMNotConfiguredError) as exc:
        log.warning("LLM 调用失败（%s/%s）：%s", meme_id, kind, exc)
        if settings.llm_allow_rule_based_fallback and kind == InsightKind.TREND_EXPLANATION:
            text = rule_based_trend(data)
            _save(
                session, meme_id=meme_id, kind=kind, data_version=data_version,
                result={"text": text}, source=InsightSource.RULE, model="rule-based",
            )
            return InsightOutput(
                kind=kind, status=InsightStatus.OK, source=InsightSource.RULE,
                data_version=data_version, result={"text": text}, error=str(exc),
            )
        return InsightOutput(
            kind=kind, status=InsightStatus.UNAVAILABLE, source="none",
            data_version=data_version, result={}, error=str(exc),
        )

    if kind == InsightKind.TREND_EXPLANATION:
        text = _strip_fences(completion.text)
        if not text or len(text) > MAX_TREND_CHARS or looks_like_prediction(text):
            log.warning("LLM 趋势解释不合格，改用算法文案：%r", text[:60])
            text = rule_based_trend(data)
            source = InsightSource.RULE
        else:
            source = InsightSource.LLM
        result = {"text": text}
    else:
        parsed = parse_json_object(completion.text) or {}
        result = _catch_up_result(data, str(parsed.get("reason") or ""), expected_status)
        source = InsightSource.LLM if parsed else InsightSource.RULE

    row = _save(
        session, meme_id=meme_id, kind=kind, data_version=data_version,
        result=result, source=source, model=completion.model, latency_ms=completion.latency_ms,
    )
    session.commit()
    return InsightOutput(
        kind=kind, status=InsightStatus.OK, source=source, model=completion.model,
        data_version=data_version, generated_at=row.generated_at, result=result,
    )


def _catch_up_result(
    data: dict[str, Any],
    reason: str,
    expected_status: str | None = None,
) -> dict[str, Any]:
    """把模型返回收敛成合法结构；status 永远以算法为准。"""
    from app.config import CATCHUP_LABELS

    status = expected_status or data.get("status") or "caution"
    if status not in CATCHUP_LABELS:
        status = "caution"

    cleaned = _strip_fences(reason or "")
    if not cleaned or len(cleaned) > MAX_TREND_CHARS or looks_like_prediction(cleaned):
        cleaned = rule_based_trend(data)

    # 置信度只认算法给的，模型可以润色文案但不能给自己打分
    confidence = float(data.get("confidence") or 0.5)

    return {
        "status": status,
        "label": CATCHUP_LABELS[status],
        "reason": cleaned,
        "confidence": round(max(0.0, min(0.95, confidence)), 2),
    }


# --------------------------------------------------------------------------- #
# 业务入口（文档 §二十二 要求的两个函数）
# --------------------------------------------------------------------------- #
def generate_trend_explanation(
    session: Session,
    *,
    meme_id: int,
    data: dict[str, Any],
    data_version: str,
    force_refresh: bool = False,
    config: LLMConfig | None = None,
) -> InsightOutput:
    return generate(
        session, meme_id=meme_id, kind=InsightKind.TREND_EXPLANATION,
        data=data, data_version=data_version, force_refresh=force_refresh, config=config,
    )


def generate_catch_up_advice(
    session: Session,
    *,
    meme_id: int,
    data: dict[str, Any],
    data_version: str,
    force_refresh: bool = False,
    config: LLMConfig | None = None,
) -> InsightOutput:
    return generate(
        session, meme_id=meme_id, kind=InsightKind.CATCH_UP_ADVICE,
        data=data, data_version=data_version, force_refresh=force_refresh, config=config,
    )
