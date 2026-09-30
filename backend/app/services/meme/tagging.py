"""梗的主题标签：让 LLM 在**固定清单**里挑，挑不中就归到「其他」。

与 :mod:`app.services.meme.summary` 是同一套约束思路——模型只做「选」，不做「造」：

* 只能从 :data:`app.config.MEME_TAGS` 里挑 key，清单外的直接丢弃（并记账）；
* 最多 ``MAX_TAGS_PER_MEME`` 个，多了截断；
* 模型一个都没选 → 记 ``other``。这是「已判定为其他类」，
  与「压根没标过」（tags 为空）是两回事，界面上要能区分；
* 输出解析失败 / LLM 不可用 → **不写库**，保持未标状态，下次重跑还能补上。

关于输入：库里**一半以上的梗没有简介**（采集时只拿到了标题），
所以解说视频标题与相关视频标题不是可有可无的补充——对没有简介的梗它就是主要依据。

缓存：打标结果另存一份到 ``ai_insights``（kind=meme_tagging），键是输入文本的摘要。
梗的介绍或引用视频没变就不重复调模型，否则每次刷新都把额度重烧一遍。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    FALLBACK_TAG,
    MAX_TAGS_PER_MEME,
    TAG_HINTS,
    TAG_KEYS,
    get_logger,
)
from app.models import AIInsight, InsightSource, InsightStatus, Meme, MemeCertification, Video
from app.services.llm.client import LLMError, LLMNotConfiguredError, chat
from app.services.llm.config import LLMConfig, load_config
from app.services.llm.service import load_prompt

log = get_logger(__name__)

TAGGING_KIND = "meme_tagging"
# 打标是「判断」不是「写作」，温度压到 0；输出也就几十个 token
TAG_TEMPERATURE = 0.0
# 取几条视频标题当输入：多了没用，还容易把模型带偏
_MAX_TITLES = 6


def _digest(name: str, description: str, titles: list[str]) -> str:
    payload = "|".join([name or "", description or "", *titles])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def collect_inputs(session: Session, meme: Meme) -> dict[str, Any]:
    """打标的输入：名称 + 简介 + 解说视频标题 + 相关视频标题。"""
    cert_titles = [
        row.video_title
        for row in session.scalars(
            select(MemeCertification).where(MemeCertification.meme_id == meme.id)
        )
        if row.video_title
    ]
    video_titles = [
        row.title
        for row in session.scalars(
            select(Video)
            .where(Video.meme_id == meme.id)
            .order_by(Video.view.desc())
            .limit(_MAX_TITLES)
        )
        if row.title
    ]
    return {
        "name": meme.name or "",
        "description": (meme.description or "").strip(),
        "cert_titles": cert_titles[:_MAX_TITLES],
        "video_titles": video_titles,
    }


def input_version(inputs: dict[str, Any]) -> str:
    return _digest(
        inputs.get("name", ""),
        inputs.get("description", ""),
        [*inputs.get("cert_titles", []), *inputs.get("video_titles", [])],
    )


def build_prompt(inputs: dict[str, Any]) -> str:
    tag_lines = "\n".join(f"- {key}：{TAG_HINTS[key]}" for key in TAG_KEYS)
    return (
        load_prompt("meme-tagging")
        .replace("{{TAGS}}", tag_lines)
        .replace("{{MAX}}", str(MAX_TAGS_PER_MEME))
        .replace("{{NAME}}", inputs.get("name") or "（无）")
        .replace("{{DESC}}", inputs.get("description") or "（无简介）")
        .replace("{{TITLES}}", " / ".join(inputs.get("cert_titles") or []) or "（无）")
        .replace("{{VIDEOS}}", " / ".join(inputs.get("video_titles") or []) or "（无）")
    )


# 只抠 tags 数组本身，不要求整个对象完整：带思考段的模型输出常被截断
# （{"tags": [...], "reason": "讲...），只认完整对象会白白丢掉本来可用的答案。
_TAGS_ARRAY = re.compile(r'"tags"\s*:\s*\[[^\]]*\]')


def _extract_tag_block(text: str) -> Any:
    """从一大段文字里抠出 ``"tags": [...]``，再补成一个对象。

    带思考段的模型常把正文的 token 全花在 reasoning 上，答案就混在思考里
    （实测 reasoning 能写到 1500 字、正文一个字不剩）。
    取**最后一次**出现的位置：思考途中往往先写草稿，最后的才是结论。
    """
    hits = _TAGS_ARRAY.findall(text or "")
    for candidate in reversed(hits):
        try:
            return json.loads("{" + candidate + "}")
        except ValueError:
            continue
    return None


def _validate_tags(data: Any, original: str) -> dict[str, Any]:
    """把解析出来的对象压回固定清单。

    任何一步不成立都如实报告，绝不猜——猜出来的标签会污染整个筛选。
    """
    if not isinstance(data, dict):
        return {
            "ok": False,
            "tags": [],
            "dropped": [],
            "reason": "模型输出的不是对象",
            "raw": (original or "")[:180],
        }

    raw_tags = data.get("tags")
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    if not isinstance(raw_tags, list):
        raw_tags = []

    picked: list[str] = []
    dropped: list[str] = []
    for item in raw_tags:
        key = str(item or "").strip().lower()
        if not key:
            continue
        if key in TAG_KEYS:
            if key not in picked:
                picked.append(key)
        else:
            dropped.append(str(item))

    picked = picked[:MAX_TAGS_PER_MEME]
    # 一个都没选中 = 「判定为其他类」，与「没标过」不是一回事，所以兜底成 other
    if not picked:
        picked = [FALLBACK_TAG]

    return {
        "ok": True,
        "tags": picked,
        "dropped": dropped,
        "reason": str(data.get("reason") or "")[:80],
        "raw": "",
    }


def parse_response(text: str) -> dict[str, Any]:
    """解析模型输出并压回固定清单。

    两步：先当整体 JSON 解析；解析不了就从文本里抠 ``{"tags": [...]}``——
    带思考段的模型在正文被截断时，答案往往已经写在思考过程里了。
    """
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]

    try:
        return _validate_tags(json.loads(raw), text)
    except (json.JSONDecodeError, ValueError):
        pass

    block = _extract_tag_block(raw)
    if block is None:
        return {
            "ok": False,
            "tags": [],
            "dropped": [],
            "reason": "模型输出里找不到可用的 JSON",
            "raw": (text or "")[:180],
        }
    return _validate_tags(block, text)


def _cached_row(session: Session, meme_id: int, version: str) -> AIInsight | None:
    return session.scalar(
        select(AIInsight).where(
            AIInsight.meme_id == meme_id,
            AIInsight.kind == TAGGING_KIND,
            AIInsight.data_version == version,
        )
    )


def _apply(meme: Meme, tags: list[str], *, source: str) -> None:
    meme.tags = list(tags)
    meme.tags_source = source
    meme.tags_updated_at = datetime.now()


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
    row = _cached_row(session, meme_id, version)
    if row is None:
        row = AIInsight(meme_id=meme_id, kind=TAGGING_KIND, data_version=version)
        session.add(row)
    row.result = result
    row.source = source
    row.model = model
    row.status = status
    row.latency_ms = latency_ms
    row.generated_at = datetime.now()
    session.flush()
    return row


def read_cached_tags(session: Session, *, meme: Meme) -> list[str] | None:
    """读缓存（不打模型）。梗库列表之类的高频路径只走这里。"""
    inputs = collect_inputs(session, meme)
    row = _cached_row(session, meme.id, input_version(inputs))
    if row is None or row.status != InsightStatus.OK:
        return None
    tags = [tag for tag in (row.result or {}).get("tags", []) if tag in TAG_KEYS]
    return tags or None


def tag_meme(
    session: Session,
    meme: Meme,
    *,
    config: LLMConfig | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """给一个梗打标。

    返回 ``{"ok", "tags", "source", "reason", "skipped"}``；
    ``ok=False`` 时**什么都没改**（保持未标），调用方下次还能重试。
    """
    inputs = collect_inputs(session, meme)
    version = input_version(inputs)

    # 已经标过且输入没变 → 不重打（force 才覆盖）
    if not force and (meme.tags or []) and meme.tags_source:
        cached = _cached_row(session, meme.id, version)
        if cached is not None and cached.status == InsightStatus.OK:
            tags = [tag for tag in (cached.result or {}).get("tags", []) if tag in TAG_KEYS]
            if tags:
                return {"ok": True, "tags": tags, "source": meme.tags_source,
                        "reason": "", "skipped": "already_tagged"}

    # 命中缓存（同输入标注过）→ 直接用，省一次模型调用
    if not force:
        cached = _cached_row(session, meme.id, version)
        if cached is not None and cached.status == InsightStatus.OK:
            tags = [tag for tag in (cached.result or {}).get("tags", []) if tag in TAG_KEYS]
            if tags:
                if not dry_run:
                    _apply(meme, tags, source=InsightSource.CACHE)
                    session.commit()
                return {"ok": True, "tags": tags, "source": InsightSource.CACHE,
                        "reason": (cached.result or {}).get("reason", ""), "skipped": "cached"}

    config = config or load_config()
    if not config.is_configured:
        return {"ok": False, "tags": [], "source": "", "reason": "LLM 未配置", "skipped": "not_configured"}

    try:
        completion = chat(
            config,
            [{"role": "user", "content": build_prompt(inputs)}],
            temperature=TAG_TEMPERATURE,
            # 不能给太小：LongCat 这类带思考段的模型会先把 token 花在 reasoning 上。
            # 实测给 200 时正文一个字都剩不下（finish_reason=length、content 为空），
            # 给 900 时仍有约三成被打到上限——思考段能写到 1400+ 字。
            # 打标正文只要几十个 token，多给的这些都是思考段的余量。
            max_tokens=max(config.max_tokens, 2000),
        )
    except (LLMError, LLMNotConfiguredError) as exc:
        log.warning("打标调用失败（%s %s）：%s", meme.id, meme.name, exc)
        return {"ok": False, "tags": [], "source": "", "reason": str(exc), "skipped": "llm_error"}

    parsed = parse_response(completion.text)
    if not parsed["ok"]:
        # 解析失败不写库：保持未标，下次重跑还能补
        log.warning("打标输出解析失败（%s %s）：%s", meme.id, meme.name, parsed["reason"])
        if not dry_run:
            _store(
                session,
                meme_id=meme.id,
                version=version,
                result=parsed,
                source=InsightSource.LLM,
                model=completion.model,
                status=InsightStatus.ERROR,
                latency_ms=completion.latency_ms,
            )
            session.commit()
        return {"ok": False, "tags": [], "source": "", "reason": parsed["reason"], "skipped": "parse_error"}

    if parsed["dropped"]:
        log.info("打标丢弃清单外的标签（%s %s）：%s", meme.id, meme.name, parsed["dropped"])

    if not dry_run:
        _apply(meme, parsed["tags"], source=InsightSource.LLM)
        _store(
            session,
            meme_id=meme.id,
            version=version,
            result={**parsed, "name": inputs["name"]},
            source=InsightSource.LLM,
            model=completion.model,
            latency_ms=completion.latency_ms,
        )
        session.commit()

    return {
        "ok": True,
        "tags": parsed["tags"],
        "source": InsightSource.LLM,
        "reason": parsed["reason"],
        "skipped": "",
    }


def tag_all(
    session: Session,
    *,
    only_untagged: bool = True,
    limit: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    config: LLMConfig | None = None,
) -> dict[str, Any]:
    """批量打标。给脚本用，也可以被刷新流程调用。"""
    rows = list(session.scalars(select(Meme).order_by(Meme.id)))
    if only_untagged and not force:
        rows = [meme for meme in rows if not (meme.tags or [])]
    if limit:
        rows = rows[: int(limit)]

    stats: dict[str, Any] = {
        "targets": len(rows),
        "tagged": 0,
        "cached": 0,
        "already": 0,
        "failed": 0,
        "by_tag": {},
        "failures": [],
    }
    for meme in rows:
        result = tag_meme(session, meme, config=config, force=force, dry_run=dry_run)
        if not result["ok"]:
            stats["failed"] = int(stats["failed"]) + 1
            stats["failures"].append({"id": meme.id, "name": meme.name, "reason": result["reason"]})
            continue
        if result["skipped"] == "cached":
            stats["cached"] = int(stats["cached"]) + 1
        elif result["skipped"] == "already_tagged":
            stats["already"] = int(stats["already"]) + 1
        else:
            stats["tagged"] = int(stats["tagged"]) + 1
        for tag in result["tags"]:
            stats["by_tag"][tag] = int(stats["by_tag"].get(tag, 0)) + 1
    return stats
