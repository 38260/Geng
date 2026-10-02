"""「这个梗是什么」的 AI 摘要层：允许模型写句子，但每一条事实都要有出处。

为什么需要这一层（2026-10-01 实测）：原来的介绍只有四档，其中三档都不"写"字
——人工稿、字幕原文摘录、证据原文拼出。可真实数据里，**能说明"这是什么"的信息
往往不在简介里**：全库 10,861 条真实视频只有 15% 的简介 ≥40 字，而抓到的那些
又常是制作人员名单（"CV：… 文案：… 后期：…"）。于是详情页那一栏就成了
「1 位 UP 主介绍过」加一段毫无信息量的名单——用户看不到任何关于梗本身的说明。

真正带信息量的是**一大批相关视频的标题**：它们自己就写着这个梗被用在哪、以什么
形式传播（"循环歌单丨…【冰冰冰の小曲】"、"不同版本的冰冰冰"）。把这些摆给模型，
它能归纳出人话；不给模型，读者就只能自己去猜。

与既有的 ``intro_summary``（字幕逐字子集）分工明确、互不替代：

* ``intro_summary``：**一个字都不许写**，只从字幕里挑整句——适合有字幕时做缩短；
* ``meme_intro``（本模块）：**允许写**，但要求"可核对"——
  输出里出现的每一个数字、书名号/引号里的专名、英数字串，都必须在材料里找得到，
  否则整段作废退回原文；并且界面必须**如实标注这是 AI 写的**，
  同时把材料（证据原文）留在可展开区里供人核对。

材料本身只由真实抓取的数据构成（认证投稿标题、相关视频标题与简介、主题标签），
没有任何人工编造的内容——所以"可核对"这条底线是能真正执行的。
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import MEME_TAGS, get_logger, settings
from app.models import AIInsight, InsightSource, InsightStatus, Meme, MemeCertification, Video
from app.services.llm.client import LLMError, LLMNotConfiguredError, chat
from app.services.llm.config import LLMConfig, load_config
from app.services.llm.service import load_prompt, looks_like_prediction

from .certification import UP_AUTHORS
from .intro import _clean, _usable_excerpt

log = get_logger(__name__)

# AIInsight.kind 的新档位：与趋势解释、赶梗建议、字幕浓缩并列
INTRO_AI_KIND = "meme_intro"
# 摘要字数区间：太短说不清，太长又把详情页撑爆
MIN_CHARS = 60
MAX_CHARS = 260
# 材料里最多摆多少条相关视频标题：再多是噪声，模型也容易抓着长尾乱归纳
MAX_MATERIAL_TITLES = 12
# 材料指纹里带上提示词版本：改了提示词就该重新生成，而不是命中旧缓存。
# v2（2026-10-02）：收紧 INSUFFICIENT 逃生口（实测 12 只被模型"懒得写"挡掉）
# + 再加一类推广噪声（微博/网易云/公众号…），材料变了指纹也要跟着变。
# v3（2026-10-02）：新增「出处线索」材料块 + 要求摘要必须写出"从哪来"。
PROMPT_VERSION = "v3"

_WS = re.compile(r"\s+")
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
# 禁止出现的"元话语"：模型一旦开始讲"材料里说"，读者就看不到梗本身了
_META_PHRASES = (
    "材料", "上述", "上面提到", "根据提供", "视频里说", "文中", "本文",
    "作为一个AI", "作为AI", "以下是我", "总结如下",
)
# 硬事实 token：数字串、书名号/引号里的专名、连续英数字串
# 平台通用词：它们不是"关于这个梗的事实"，模型用了不该判成编造。
# 实测误报：模型写 "UP主"/"Vlog"/"emoji"，材料里没有这几个词，于是整段被冤杀。
_GENERIC_TOKENS = {
    "ai", "up", "emoji", "vlog", "bgm", "dj", "meme", "mv", "pv", "cg",
    "3d", "2d", "id", "app", "vip", "funk", "jumpstyle", "live",
}
_NUM = re.compile(r"\d+")
_TITLED = re.compile(r"《([^》]{1,30})》|「([^」]{1,30})」|“([^”]{1,30})”|\"([^\"]{1,30})\"")
_ASCII_RUN = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,}")
# 出处线索关键词。实测入池 48 只里 35 只的标题或简介**明确写了来源**
# （「原版油管老师@KotteAnimation」「《黑街DJ》原版MV」「原曲作者亲自remix」
#  「素材来源：@江肥肠」），但原先这些混在十几条标题里，模型经常不写"从哪来"。
# 单独拎成一块，它才会照实转述而不是自己猜。
_ORIGIN_KEYWORDS = (
    "原版", "原视频", "原曲", "原作", "原出处", "出处", "来源", "素材", "搬运",
    "来自", "首次", "最早", "官方", "首发", "改编自", "引用", "翻拍", "转载",
)
# 句末，用于超长时在句子边界收尾
_SENTENCE_END = re.compile(r"[。！？!?]")
_INSUFFICIENT = "INSUFFICIENT"


def _flat(text: str) -> str:
    return _WS.sub("", text or "")


def _tag_labels(meme: Meme) -> list[str]:
    """主题标签的展示名（存的是 key，展示要翻成中文别硬塞 key 给模型）。"""
    labels = {spec.key: spec.label for spec in MEME_TAGS}
    return [labels.get(key, key) for key in (meme.tags or [])]


def _up_label(cert: MemeCertification) -> str:
    author = UP_AUTHORS.get(cert.role)
    return author.name if author else (cert.up_name or cert.role)


def build_material(
    meme: Meme,
    certifications: Iterable[MemeCertification] = (),
    videos: Iterable[Video] = (),
    *,
    transcript_excerpt: str = "",
    max_titles: int = MAX_MATERIAL_TITLES,
) -> str:
    """把"关于这个梗我们真有的东西"排成一段给模型的材料。

    顺序刻意固定（梗名 → 别名关键词 → 主题标签 → 解说视频 → 相关视频标题 → 简介 →
    字幕摘录），这样材料指纹稳定，同一批数据不会因为字典序变化而反复重算。
    """
    lines = [f"梗名：{meme.name}"]
    aliases = [a for a in (meme.aliases or []) if a and a != meme.name]
    if aliases:
        lines.append("别名/常见叫法：" + "、".join(aliases[:10]))
    keywords = [k for k in (meme.keywords or []) if k and k != meme.name]
    if keywords:
        lines.append("关键词：" + "、".join(keywords[:10]))
    labels = _tag_labels(meme)
    if labels:
        lines.append("主题标签：" + "、".join(labels))

    certs = [cert for cert in certifications if cert.confirmed and cert.video_title]
    certs.sort(key=lambda cert: cert.published_at or datetime.min)
    for cert in certs:
        when = cert.published_at.strftime("%Y-%m-%d") if cert.published_at else "日期未知"
        lines.append(f"梗解说视频（{_up_label(cert)}，{when}）：《{_clean(cert.video_title)}》")

    titles: list[str] = []
    for video in list(videos)[:max_titles]:
        if not video.title:
            continue
        play = f"{video.view:,} 播放" if video.view else "播放量未知"
        titles.append(f"· 《{_clean(video.title)}》（{play}）")
    if titles:
        lines.append("站内相关视频（按播放量降序）：")
        lines.extend(titles)

    # 简介与标题分成两块：**带出处信息的**单独进「出处线索」，其余当普通补充材料。
    # 简介必须先过噪声清洗：制作人员名单、邮箱、商务合作这些对"这是什么梗"毫无用处，
    # 喂给模型只会被它抄进摘要。阈值压到 8 字是因为清洗后常只剩半句真东西
    # （"这音效小时候抱过我"才 9 字），而它往往正是全库最有信息量的一句；
    # 详情页那条摘录仍按自己的 40 字门槛来。
    origin_lines: list[str] = []
    other_desc: list[str] = []
    for video in list(videos)[:max_titles]:
        title = _clean(video.title)
        if title and any(word in title for word in _ORIGIN_KEYWORDS):
            play = f"{video.view:,} 播放" if video.view else "播放量未知"
            origin_lines.append(f"· 《{title}》（{play}）")
        body = _usable_excerpt(video.description, min_chars=8)
        if not body:
            continue
        if any(word in body for word in _ORIGIN_KEYWORDS):
            origin_lines.append(f"· 简介原文：{body}")
        else:
            other_desc.append(f"· 简介原文：{body}")

    if origin_lines:
        lines.append("出处线索（标题或简介里明确提到来源的；照实转述，不许添油加醋）：")
        lines.extend(origin_lines[:8])
    if other_desc:
        # 非出处类简介也要留几条：有时候它们才是"这梗怎么玩"的唯一线索
        lines.append("其它相关视频的简介原文：")
        lines.extend(other_desc[:6])

    if transcript_excerpt:
        lines.append(f"解说视频字幕摘录：{_clean(transcript_excerpt)}")
    return "\n".join(lines)


def material_digest(material: str) -> str:
    """材料指纹：材料或提示词版本一变，缓存就失效。"""
    payload = f"{PROMPT_VERSION}\n{_flat(material)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _hard_tokens(text: str) -> list[str]:
    """输出里"可被核对"的硬事实：数字、书名号/引号专名、英数字串。"""
    tokens: list[str] = [match.group(0) for match in _NUM.finditer(text)]
    for match in _TITLED.finditer(text):
        tokens.append(next(group for group in match.groups() if group))
    tokens.extend(match.group(0) for match in _ASCII_RUN.finditer(text))
    return tokens


def check_grounded(candidate: str, material: str, *, budget: int = MAX_CHARS) -> dict[str, Any]:
    """校验 AI 摘要：能不能用、哪些事实核对不上。

    与字幕那层的"逐字子集"不同——这里允许改写与归纳，所以校验的是**事实锚点**：
    数字 / 《专名》/ 引号里的说法 / 英数字串，必须能在材料里逐字找到。
    编一个年份、编一个作品名都会被这里拦下，整段作废（宁可退回原文摘录）。
    """
    text = _WS.sub(" ", _FENCE.sub("", (candidate or "").strip())).strip()
    if not text:
        return {"text": "", "ok": False, "reason": "模型返回空", "tokens": [], "invented": []}
    if _INSUFFICIENT in text.upper() and len(text) <= len(_INSUFFICIENT) + 12:
        return {"text": "", "ok": False, "reason": "模型自认材料不足", "tokens": [], "invented": []}

    truncated = False
    if len(text) > budget:
        head = text[:budget]
        cut = max((match.end() for match in _SENTENCE_END.finditer(head)), default=-1)
        if cut < budget * 0.5:
            return {"text": "", "ok": False, "reason": f"输出过长（{len(text)} 字）且找不到句末", "tokens": [], "invented": []}
        text = head[:cut]
        truncated = True

    if len(text) < MIN_CHARS:
        return {"text": "", "ok": False, "reason": f"输出过短（{len(text)} 字）", "tokens": [], "invented": []}
    if looks_like_prediction(text):
        return {"text": "", "ok": False, "reason": "出现对未来的说法", "tokens": [], "invented": []}
    hit = [phrase for phrase in _META_PHRASES if phrase in text]
    if hit:
        return {"text": "", "ok": False, "reason": f"出现元话语：{'、'.join(hit)}", "tokens": [], "invented": []}

    flat_material = _flat(material)
    # 比对一律忽略大小写：材料里是 "vlog"、模型写 "Vlog" 不该算编造
    flat_material_lower = flat_material.lower()
    tokens = _hard_tokens(text)
    ungrounded = [
        token for token in tokens
        if _flat(token).lower() not in flat_material_lower
        and _flat(token).lower() not in _GENERIC_TOKENS
    ]
    if ungrounded:
        return {
            "text": "",
            "ok": False,
            # 这条日志是排查"AI 又编了什么"的第一现场，token 要原样记下来
            "reason": f"有 {len(ungrounded)} 个事实在材料里找不到出处：{'、'.join(ungrounded[:6])}",
            "tokens": tokens,
            "invented": ungrounded,
        }
    return {"text": text, "ok": True, "reason": "", "tokens": tokens, "invented": [], "truncated": truncated}


def _cached(session: Session, meme_id: int, version: str) -> AIInsight | None:
    return session.scalar(
        select(AIInsight).where(
            AIInsight.meme_id == meme_id,
            AIInsight.kind == INTRO_AI_KIND,
            AIInsight.data_version == version,
            AIInsight.status == InsightStatus.OK,
        )
    )


def read_cached_ai_intro(session: Session, *, meme_id: int, version: str) -> dict[str, Any] | None:
    """详情接口只读这条：读到就给，读不到不现调模型（不为一段文案让页面等几十秒）。"""
    row = _cached(session, meme_id, version)
    if row is None:
        return None
    result = dict(row.result or {})
    if not result.get("text"):
        return None
    return {
        **result,
        "source": InsightSource.CACHE,
        "model": row.model,
        "data_version": version,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "verified": True,
    }


def _store(
    session: Session,
    *,
    meme_id: int,
    version: str,
    result: dict[str, Any],
    source: str,
    model: str,
    status: str,
    latency_ms: int,
) -> AIInsight:
    row = session.scalar(
        select(AIInsight).where(
            AIInsight.meme_id == meme_id,
            AIInsight.kind == INTRO_AI_KIND,
            AIInsight.data_version == version,
        )
    )
    if row is None:
        row = AIInsight(meme_id=meme_id, kind=INTRO_AI_KIND, data_version=version)
        session.add(row)
    row.result = result
    row.source = source
    row.model = model
    row.status = status
    row.latency_ms = latency_ms
    row.generated_at = datetime.now()
    session.flush()
    return row


def build_prompt(material: str, meme_name: str) -> str:
    return (
        load_prompt("meme-intro")
        .replace("{{NAME}}", meme_name or "")
        .replace("{{MATERIAL}}", material or "")
    )


def generate_meme_intro(
    session: Session,
    meme: Meme,
    *,
    certifications: Iterable[MemeCertification] = (),
    videos: Iterable[Video] = (),
    transcript_excerpt: str = "",
    force_refresh: bool = False,
    config: LLMConfig | None = None,
    override_model: str = "",
) -> dict[str, Any] | None:
    """生成一条 AI 摘要并入库；材料撑不起一段介绍时返回 None（界面退回原文摘录）。

    调用一次就打一次模型，所以调用方要么走脚本批量、要么由用户点按钮触发；
    详情接口永远只读缓存。
    """
    material = build_material(meme, certifications, videos, transcript_excerpt=transcript_excerpt)
    version = material_digest(material)

    if not force_refresh:
        cached = read_cached_ai_intro(session, meme_id=meme.id, version=version)
        if cached is not None:
            return cached

    config = config or load_config()
    if not config.is_configured:
        log.info("没配 LLM_API_KEY，「%s」的 AI 摘要跳过", meme.name)
        return None
    # 这个任务单独挑模型：写一段介绍要先读十几条标题再归纳，而带思考段的模型
    # （LongCat-2.5-Preview）会把输出预算全烧在 reasoning 上——实测 900 与 2500
    # tokens 都被吃光、content 为空、只剩英文思考过程，这个任务在它上面必然失败。
    if settings.llm_intro_model and settings.llm_intro_model != config.model:
        log.info("AI 摘要改用 %s（而非主模型 %s）", settings.llm_intro_model, config.model)
        config = dataclasses.replace(config, model=settings.llm_intro_model)
    if override_model and override_model != config.model:
        config = dataclasses.replace(config, model=override_model)

    prompt = build_prompt(material, meme.name)
    completion = None
    # 预算刻意给足：实测 LongCat-2.0 偶尔也会先"想"一大段，900/1200 tokens
    # 会被思考段吃光、content 返回空。这时客户端只能退回 reasoning_content，
    # 而那是**思考过程**（常常还是英文），不是介绍——绝不能当正文用。
    for budget in (max(config.max_tokens, 3000), 6000):
        try:
            candidate = chat(
                config,
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=budget,
            )
        except (LLMError, LLMNotConfiguredError) as exc:
            log.warning("AI 摘要调用失败（%s）：%s", meme.id, exc)
            return None
        if not candidate.reasoning_only:
            completion = candidate
            break
        log.warning("AI 摘要只拿到思考段（%s，预算 %s tokens），加倍预算重试", meme.id, budget)

    if completion is None:
        # 两次都只拿到推理：这一轮放弃，界面继续显示证据原文。
        log.warning("AI 摘要两次都只拿到思考段，本轮放弃（%s/%s）", meme.id, meme.name)
        return None

    check = check_grounded(completion.text, material)
    if not check["ok"]:
        # 编造没被拦住就是这个功能的失败，如实记进库里（status=error），界面继续用原文
        log.warning("AI 摘要未通过核对（%s/%s）：%s", meme.id, meme.name, check["reason"])
        _store(
            session,
            meme_id=meme.id,
            version=version,
            result={"text": "", "reason": check["reason"], "invented": check.get("invented", [])},
            source=InsightSource.LLM,
            model=completion.model,
            status=InsightStatus.ERROR,
            latency_ms=completion.latency_ms,
        )
        session.commit()
        return None

    result = {
        "text": check["text"],
        "chars": len(check["text"]),
        "tokens": check["tokens"],
        "truncated": check.get("truncated", False),
        "material": material,
        "material_chars": len(material),
    }
    row = _store(
        session,
        meme_id=meme.id,
        version=version,
        result=result,
        source=InsightSource.LLM,
        model=completion.model,
        status=InsightStatus.OK,
        latency_ms=completion.latency_ms,
    )
    session.commit()
    return {
        **result,
        "source": InsightSource.LLM,
        "model": row.model,
        "data_version": version,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "verified": True,
    }
