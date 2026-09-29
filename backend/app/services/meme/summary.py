"""梗介绍的 AI 浓缩：只允许「从字幕原文里挑句子」，不允许写句子。

为什么要这一层：规则选段挑出来的摘录常有 200 字，读起来像复述。缩短是文案工作，
恰好是模型擅长的；但一放手让它"归纳"，我们就没了出处——它会把"主播在逆风局里
说的这句话"写成"源自一场电竞比赛"，读起来更顺，可没人能证明视频里说过。

所以校验按**逐字子集**做，比"数字与专名要能在原文找到"更硬：

* 只承认模型整句照抄的原句（半句不算，截半句会改意思）；
* 拼接顺序永远按原文顺序，模型改了顺序也不采纳它的顺序；
* 模型自己加的句子全部记进 ``invented`` 留证据，不进结果；
* 一个字都没通过校验 → 返回 ``None``，界面退回规则摘录，不硬凑。

结果缓存在 ``ai_insights``（kind=intro_summary），键是 ``bvid + 字幕文本摘要``：
字幕没重抓过就不再打模型。生成只由脚本/刷新触发，详情接口只读缓存——
不为一行文案让页面多等 60 秒。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger, settings
from app.models import AIInsight, InsightSource, InsightStatus
from app.models.transcript import transcript_digest
from app.services.llm.client import LLMError, LLMNotConfiguredError, chat
from app.services.llm.config import LLMConfig, load_config
from app.services.llm.service import load_prompt, looks_like_prediction

log = get_logger(__name__)

# AIInsight.kind 的新档位：与趋势解释、赶梗建议并列，但只在有字幕时才存在
INTRO_KIND = "intro_summary"
# 浓缩后的介绍上限：比规则摘录短，否则缩短没有意义
MAX_SUMMARY_CHARS = 140
# 模型至少要说全一句原句才有意义
_MIN_SOURCE_SENTENCE_CHARS = 6

_SENTENCE_TAIL = re.compile(r"(?<=[。！？!?])")
_WS = re.compile(r"\s+")
# 字幕是一行一行下发的，一句话常被拆到两行；展示时把这个换行吃掉，
# 但保留「2019 年」这种正常空格——去掉空格就不算逐字原文了。
_SUB_LINE = re.compile(r"\s*\n\s*")


def digest(bvid: str, text: str) -> str:  # pragma: no cover - 见 transcript_digest
    return transcript_digest(bvid, text)


def _flat(text: str) -> str:
    """匹配用的形态：所有空白都不参与比较，模型加的空格和换行不该影响"是不是原文"。"""
    return _WS.sub("", text or "")


def shown_sentences(text: str) -> list[str]:
    """可展示的原文句子：折回字幕换行，但逐字保留其余内容。"""
    return [
        chunk.strip()
        for chunk in _SENTENCE_TAIL.split(_SUB_LINE.sub("", text or ""))
        if chunk.strip() and len(_flat(chunk)) >= _MIN_SOURCE_SENTENCE_CHARS
    ]


def source_sentences(text: str) -> list[str]:
    """匹配用的句子形态（空白全去掉）；展示请走 :func:`shown_sentences`。"""
    return [_flat(item) for item in shown_sentences(text)]


def check_verbatim(candidate: str, source: str, *, budget: int = MAX_SUMMARY_CHARS) -> dict[str, Any]:
    """把模型输出压回"原文句子的子集"，并如实报告它想加什么。

    返回 ``{"text", "sentences", "invented", "truncated", "ok", "reason"}``；
    ``ok=False`` 时 ``text`` 不可用，调用方要退回规则摘录。
    """
    flat_candidate = _flat(candidate)
    pairs = [(shown, _flat(shown)) for shown in shown_sentences(source)]
    # 只承认"整句都在模型输出里"的原句：半句不算，改一个词也不算，顺序按原文
    sentences = [shown for shown, flat in pairs if flat and flat in flat_candidate]

    # 模型自己写的句子：压掉空白后在原文里找不到的那几段，全部记下来当证据
    flat_source = _flat(source)
    invented = [
        chunk.strip()
        for chunk in _SENTENCE_TAIL.split(_flat(candidate))
        if chunk.strip() and chunk.strip().rstrip("。！？!?；;") not in flat_source
    ]

    text = "".join(sentences)
    truncated = False
    while len(text) > budget and len(sentences) > 1:
        # 整句丢掉末尾的，绝不做半句截断：截半句就是在改意思
        sentences.pop()
        text = "".join(sentences)
        truncated = True

    if not sentences:
        return {
            "text": "",
            "sentences": [],
            "invented": invented,
            "truncated": False,
            "ok": False,
            "reason": "模型没有整句照抄任何原文句子",
        }
    if looks_like_prediction(text):
        return {
            "text": text,
            "sentences": sentences,
            "invented": invented,
            "truncated": truncated,
            "ok": False,
            "reason": "结果里出现了对未来的说法，介绍不许预测",
        }
    return {
        "text": text,
        "sentences": sentences,
        "invented": invented,
        "truncated": truncated,
        # 原样就已经够短时不需要缩短；这时也别装出"AI 帮你压过了"
        "shortened": len(text) < len("".join(shown_sentences(source))),
        "ok": True,
        "reason": "",
    }


def _cached(session: Session, meme_id: int, version: str) -> AIInsight | None:
    return session.scalar(
        select(AIInsight).where(
            AIInsight.meme_id == meme_id,
            AIInsight.kind == INTRO_KIND,
            AIInsight.data_version == version,
            AIInsight.status == InsightStatus.OK,
        )
    )


def _store(
    session: Session,
    *,
    meme_id: int,
    version: str,
    result: dict[str, Any],
    source: str,
    model: str,
    status: str = InsightStatus.OK,
    latency_ms: int = 0,
) -> AIInsight:
    row = _cached(session, meme_id, version)
    if row is None:
        row = AIInsight(meme_id=meme_id, kind=INTRO_KIND, data_version=version)
        session.add(row)
    row.result = result
    row.source = source
    row.model = model
    row.status = status
    row.latency_ms = latency_ms
    row.generated_at = datetime.now()
    session.flush()
    return row


def _shape(row: AIInsight, version: str) -> dict[str, Any]:
    result = dict(row.result or {})
    return {
        **result,
        "source": row.source,
        "model": row.model,
        "data_version": version,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "verified": bool(result.get("ok")),
    }


def read_cached_summary(session: Session, *, meme_id: int, version: str) -> dict[str, Any] | None:
    """详情接口只用这一条：读到就给，读不到不现调模型。

    命中缓存时把 source 改标成 ``cache``，否则界面会以为自己刚看了模型输出——
    趋势/赶梗那两类文案就是这么标的，保持一致。
    """
    row = _cached(session, meme_id, version)
    if row is None:
        return None
    shape = _shape(row, version)
    if not (shape.get("verified") and shape.get("text")):
        return None
    return {**shape, "source": InsightSource.CACHE}


def build_prompt(text: str, meme_name: str, *, budget: int = MAX_SUMMARY_CHARS) -> str:
    return (
        load_prompt("intro-summary")
        .replace("{{MAX}}", str(budget))
        .replace("{{NAME}}", meme_name)
        .replace("{{TRANSCRIPT}}", text or "")
    )


def generate_intro_summary(
    session: Session,
    *,
    meme_id: int,
    bvid: str,
    text: str,
    meme_name: str = "",
    config: LLMConfig | None = None,
    force_refresh: bool = False,
    budget: int = MAX_SUMMARY_CHARS,
) -> dict[str, Any]:
    """让模型挑原句，校验通过才入库；返回 None 表示这条梗没有可用的浓缩版。"""
    version = digest(bvid, text)
    if not force_refresh:
        cached = read_cached_summary(session, meme_id=meme_id, version=version)
        if cached is not None:
            return cached

    config = config or load_config()
    if not config.is_configured:
        log.info("没配 LLM_API_KEY，%s 的介绍浓缩跳过", meme_name or meme_id)
        return None

    try:
        completion = chat(
            config,
            [{"role": "user", "content": build_prompt(text, meme_name or "", budget=budget)}],
            temperature=0.1,
            # 只是复述几句，不需要长输出；卡住了还会连带把思考段截空
            max_tokens=max(config.max_tokens, 600),
        )
    except (LLMError, LLMNotConfiguredError) as exc:
        log.warning("介绍浓缩调用失败（%s/%s）：%s", meme_id, bvid, exc)
        return None

    check = check_verbatim(completion.text, text, budget=budget)
    if not check["ok"]:
        # 编造没被拦住就是这个功能的失败；如实记下，界面继续用规则摘录
        log.warning(
            "介绍浓缩未通过逐字校验（%s/%s）：%s；模型自加句子 %d 条",
            meme_id, bvid, check["reason"], len(check["invented"]),
        )
        _store(
            session,
            meme_id=meme_id,
            version=version,
            result={**check, "text": "", "bvid": bvid},
            source=InsightSource.RULE,
            model=completion.model,
            status=InsightStatus.ERROR,
            latency_ms=completion.latency_ms,
        )
        session.commit()
        return None

    result = {
        "text": check["text"],
        "sentences": check["sentences"],
        "invented": check["invented"],
        "truncated": check["truncated"],
        "shortened": check.get("shortened", True),
        "ok": True,
        "reason": "",
        "bvid": bvid,
        "budget": budget,
        "chars": len(check["text"]),
    }
    row = _store(
        session,
        meme_id=meme_id,
        version=version,
        result=result,
        source=InsightSource.LLM,
        model=completion.model,
        latency_ms=completion.latency_ms,
    )
    session.commit()
    return _shape(row, version)


def summary_note(block: dict[str, Any], summary: dict[str, Any]) -> str:
    """界面上那句自解释：说清 AI 干了什么、没干什么。"""
    picked = len(summary.get("sentences") or [])
    return (
        f"AI 从字幕的 {block.get('matched_sentences', 0)} 句相关原句里挑了 {picked} 句，"
        f"压到 {summary.get('chars', 0)} 字。每句都是整句照抄，顺序也按原文，"
        "系统逐字核对过——对不上就退回未缩短的摘录。"
        + ("（未配置 LLM 时不会出现这一段）" if not settings.llm_api_key else "")
    )
