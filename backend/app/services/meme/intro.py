"""梗介绍：详情页「这个梗是什么」这一段的来源与合成规则。

原则只有一条：**不编造**。介绍只有四个来源，优先级从高到低：

1. ``manual``     —— 人工在梗管理里写好的 ``meme.description``；
2. ``transcript`` —— 解说视频**字幕原文**里挑出真正在讲这个梗的那几句
   （由 :mod:`app.scripts.fetch_transcripts` 抓进 ``video_transcripts``，需要 BILI_COOKIE）；
3. ``evidence``   —— 用已经抓到的真实证据原文拼出来：哪位 UP 主、哪一期解说视频
   （标题是 B 站返回的原文），再附上头部相关视频里字数够长的真实简介摘录；
4. ``none``       —— 什么都没有。这时界面必须显式说"还没有介绍"并给出补介绍的入口，
   不能留一片空白让人以为系统坏了。

``transcript`` 和 ``evidence`` 两条路都刻意不做任何改写和归纳：字幕选段只做
"按原顺序把命中线索词的句子拼起来"这一件事，挑不出线索句就退回 ``evidence``，
绝不为了有内容而凑话。LLM 没配 key 时不能凭空写，配了 key 也不该由它来定义
"这个梗是什么"（V1 约定：AI 只复述算法结论，不生产事实）。
所以这里拼出来的每个字都能在 ``videos`` / ``meme_certifications`` /
``video_transcripts`` 三张表里找到出处。
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.config import settings
from app.models import Meme, MemeCertification, Video, VideoTranscript
from app.models.transcript import TRANSCRIPT_LABELS, TranscriptKind, transcript_digest

from .certification import ENCYCLOPEDIA, GUIDE, UP_AUTHORS

# 短于此的视频简介基本是「求三连」「记得点赞」这类占位话，放进介绍里只会稀释信息
MIN_EXCERPT_CHARS = 40
# 摘录长度上限：详情页一屏要放得下热度、曲线、赶梗结论，介绍不该占满
MAX_EXCERPT_CHARS = 160

# 介绍里按「梗百科在前、梗指南在后」排，和详情页认证条、发现层的顺序保持一致
_ROLE_ORDER = {ENCYCLOPEDIA.role: 0, GUIDE.role: 1}
_HASHTAG = re.compile(r"#\S+")
# UP 主常把"求三连/记得关注"刷成一整段，字数够但零信息量。
# 必须带动词才剥——"弹幕""关注"本身是常用词，光匹配名词会把正常句子啃掉半截。
_PLEAD = re.compile(
    r"(?:(?:求|想要?|记得|顺便|欢迎|长按|双击|给个|来波)\s*(?:个)?\s*(?:一键)?(?:三连|点赞|投币|收藏|关注|转发|弹幕)"
    r"|一键三连)"
    r"\s*[~～!！。.、,，]*"
)
# 简介里的外链和 BV 号对"这是什么梗"没用，还会把摘录撑长
_LINK = re.compile(r"(?:https?://|www\.)\S+|BV[0-9A-Za-z]{5,}")
# 同一个片段被刷屏重复（"求三连~求三连~…"）时只留一次
_REPEATED = re.compile(r"(\S{2,}?)(?:\1){2,}")
# 简介里超过这个比例是求三连话术，整段就别摘了
_PLEAD_RATIO = 0.35
# 只由标点/空白/占位符组成的简介（B 站不少 UP 主留的就是一个「-」）
_NOISE = re.compile(r"^[\s\-—_·、,，.。!！?？/\\*#]*$")
# 简介里的句读，用来在超长处断开
_SENTENCE_END = re.compile(r"[。！？!?；;，\n]")

# -------------------------------- 字幕选段 ---------------------------------- #
# 解说视频讲"这是什么梗"是有固定话术的，命中这些词的句子才配进介绍。
# 只按词面挑，不做语义归纳——归纳就得靠模型，模型一开口我们就没了出处。
_CLUES = (
    "这个梗", "这梗", "梗的", "什么梗", "出处", "出自", "源自", "来源于", "来源",
    "来历", "由来", "最早", "起初", "本来", "其实", "所谓", "说的是", "指的是",
    "为什么", "怎么来", "什么意思", "背景", "原视频", "原梗", "评论区", "典故",
)
# 详情页正文的选段预算：再长就挤掉热度、曲线、赶梗结论了
MAX_SEGMENT_CHARS = 220
# 折叠区里的字幕原文上限。一条 10 分钟解说的字幕通常 2000~4000 字，
# 全塞进接口只是把详情页变成下载器，超出部分给"看视频"的出口。
MAX_FULL_CHARS = 1200
# 短于此的句子（"对""然后"）拼进去只会打断阅读
_MIN_SENTENCE_CHARS = 12
# 最多拼几句：再多就是在复述整期视频了
_MAX_SEGMENT_SENTENCES = 6

_LINE_BREAK = re.compile(r"\n+")
_AFTER_PUNCT = re.compile(r"(?<=[。！？!?；;])")
# 折叠区用一整段渲染，字幕的换行在这里是噪音
_SOFT_BREAK = re.compile(r"\s*\n\s*")


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _up_label(cert: MemeCertification) -> str:
    author = UP_AUTHORS.get(cert.role)
    return author.name if author else (cert.up_name or cert.role)


def _day(value: Any) -> str:
    return value.strftime("%Y-%m-%d") if value else ""


def _usable_excerpt(text: str | None) -> str:
    """把一条真实视频简介裁成可展示的摘录；不可用则返回空串。"""
    raw = _clean(_LINK.sub(" ", _HASHTAG.sub(" ", text or "")))
    if not raw:
        return ""
    # 整段大半是求三连话术的简介，剥完也剩不下什么，直接判不可用
    plead_chars = sum(len(match.group(0)) for match in _PLEAD.finditer(raw))
    if plead_chars / len(raw) > _PLEAD_RATIO:
        return ""
    body = _clean(_REPEATED.sub(r"\1", _PLEAD.sub(" ", raw)))
    if len(body) < MIN_EXCERPT_CHARS or _NOISE.match(body):
        return ""
    if len(body) > MAX_EXCERPT_CHARS:
        head = body[:MAX_EXCERPT_CHARS]
        # 在句读处断开，别把半句话甩给用户
        cut = max(head.rfind(m.group(0)) for m in _SENTENCE_END.finditer(head)) if _SENTENCE_END.search(head) else -1
        body = head[: cut + 1] if cut > 40 else head + "…"
    return body


def _sentences(text: str | None) -> list[str]:
    """字幕按行下发，行内再按句末标点切；不做任何改写，切完还是原文。"""
    parts: list[str] = []
    for line in _LINE_BREAK.split(text or ""):
        line = _clean(line)
        if not line:
            continue
        for chunk in _AFTER_PUNCT.split(line):
            chunk = _PLEAD.sub(" ", chunk).strip()
            if chunk and not _NOISE.match(chunk):
                parts.append(chunk)
    return parts


def _score(sentence: str, names: list[str]) -> int:
    score = sum(1 for clue in _CLUES if clue in sentence)
    # 点名了这个梗（或别名）的句子更可能是在解释它，权重给高一点
    score += 2 * sum(1 for name in names if len(name) >= 2 and name in sentence)
    return score


def select_segment(
    text: str | None,
    names: Iterable[str] = (),
    *,
    budget: int = MAX_SEGMENT_CHARS,
) -> tuple[str, int]:
    """从字幕里挑出真正在讲这个梗的句子，按原顺序拼成摘录。

    返回 ``(摘录, 命中线索的句子数)``。挑不出一句就返回 ``("", 0)``——
    这时退回上一档用标题和简介，而不是把随便一句开场白当成介绍。
    """
    hits = [
        (index, sentence, _score(sentence, list(names)))
        for index, sentence in enumerate(_sentences(text))
        if len(sentence) >= _MIN_SENTENCE_CHARS
    ]
    hits = [item for item in hits if item[2] > 0]
    if not hits:
        return "", 0

    picked: list[tuple[int, str]] = []
    used = 0
    for index, sentence, _ in sorted(hits, key=lambda item: (-item[2], item[0]))[:_MAX_SEGMENT_SENTENCES]:
        if used + len(sentence) > budget:
            continue
        picked.append((index, sentence))
        used += len(sentence)
    if not picked:
        # 预算里塞不进任何整句：取文档里最早的命中句，在次级句读处裁
        index, sentence, _ = hits[0]
        head = sentence[:budget]
        cut = max((head.rfind(mark) for mark in "，、；;"), default=-1)
        picked = [(index, head[: cut + 1] + "…" if cut > 20 else head)]
    picked.sort()
    return "".join(sentence for _, sentence in picked), len(hits)


def _clip_full(text: str) -> tuple[str, bool]:
    body = _clean(_SOFT_BREAK.sub(" ", text or ""))
    if len(body) <= MAX_FULL_CHARS:
        return body, False
    head = body[:MAX_FULL_CHARS]
    cut = max((head.rfind(mark) for mark in "。！？!?；"), default=-1)
    return (head[: cut + 1] if cut > 100 else head + "…"), True


def transcript_block(
    meme: Meme,
    certifications: Iterable[MemeCertification],
    transcripts: Iterable[VideoTranscript],
) -> dict[str, Any] | None:
    """选一条字幕、选一段原文，拼成详情页的「字幕原文」块；没有可用字幕返回 None。

    优先级：认证解说视频的人工 CC > 认证视频的 AI 字幕 > 其它来源，同档里选段更长的先用
    （长说明它讲到了内容，不是半句开场白）。
    """
    certs = [cert for cert in certifications if cert.confirmed]
    cert_by_bvid = {cert.bvid: cert for cert in certs if cert.bvid}
    names = [meme.name, *(meme.aliases or []), *(meme.keywords or [])]

    ranked: list[tuple[int, int, VideoTranscript, str, int]] = []
    for row in transcripts or ():
        if not (row.text or "").strip():
            continue
        segment, hits = select_segment(row.text, names)
        if not segment:
            continue
        is_cert = row.bvid in cert_by_bvid
        is_cc = row.kind == TranscriptKind.CC
        rank = 0 if (is_cert and is_cc) else 1 if is_cc else 2 if is_cert else 3
        ranked.append((rank, -len(segment), row, segment, hits))
    if not ranked:
        return None

    rank, _, row, segment, hits = sorted(ranked, key=lambda item: (item[0], item[1]))[0]
    cert = cert_by_bvid.get(row.bvid)
    full, truncated = _clip_full(row.text)
    return {
        "bvid": row.bvid,
        "video_title": row.video_title or (cert.video_title if cert else ""),
        "url": f"https://www.bilibili.com/video/{row.bvid}" if row.bvid else "",
        "kind": row.kind,
        "kind_label": TRANSCRIPT_LABELS.get(row.kind, row.kind),
        # AI 识别的字幕错字多，界面要用这个提示把预期说清楚，而不是让用户以为我们在瞎摘
        "kind_hint": (
            "B 站自动识别的字幕，专有名词错字较多，摘录时未做纠正"
            if row.kind == TranscriptKind.AI else "UP 主或字幕组上传的人工字幕"
        ),
        "role": cert.role if cert else "",
        "up_label": _up_label(cert) if cert else "",
        # 非认证视频的字幕也能佐证内容，但来源要能被认出来，不能伪装成双 UP 的说法
        "certified": cert is not None,
        "chars": row.chars or len(row.text or ""),
        # 字幕内容的指纹：AI 浓缩的缓存键用它，重抓过字幕就不会命中旧结果
        "version": transcript_digest(row.bvid, row.text),
        "excerpt": segment,
        "excerpt_chars": len(segment),
        "matched_sentences": hits,
        "full": full,
        "full_truncated": truncated,
        "fetched_at": row.fetched_at.strftime("%Y-%m-%d") if row.fetched_at else "",
    }


def evidence_lines(certifications: Iterable[MemeCertification]) -> list[dict[str, Any]]:
    """按「梗百科在前、梗指南在后」列出真实介绍过这个梗的解说视频。"""
    rows = [
        cert for cert in certifications
        if cert.confirmed and (cert.video_title or cert.bvid)
    ]
    rows.sort(key=lambda cert: (_ROLE_ORDER.get(cert.role, 9), cert.up_name))
    real = settings.data_source == "bilibili"
    return [
        {
            "role": cert.role,
            "up_label": _up_label(cert),
            "up_name": cert.up_name,
            "video_title": _clean(cert.video_title),
            "bvid": cert.bvid,
            # 只有真实抓到的投稿才给链接，演示证据点进去是 404
            "video_url": (
                cert.video_url or (f"https://www.bilibili.com/video/{cert.bvid}" if cert.bvid else "")
                if cert.data_source == "bilibili" else ""
            ),
            "published_at": _day(cert.published_at),
            "verified": cert.data_source == "bilibili",
        }
        for cert in rows
        if cert.data_source == "bilibili" or not real
    ]


def _source_line(item: dict[str, Any]) -> str:
    when = f"{item['published_at']} " if item["published_at"] else ""
    return f"「{item['up_label']}」{when}的解说视频《{item['video_title']}》里介绍过这个梗"


def compose_intro(
    meme: Meme,
    certifications: Iterable[MemeCertification] = (),
    videos: Iterable[Video] = (),
    transcripts: Iterable[VideoTranscript] = (),
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """组装详情页要用的介绍结构体。

    ``videos`` 传进来时应当已按播放量降序（取第一条简介够长的做摘录）；
    ``transcripts`` 是这些视频的字幕，只有配了 BILI_COOKIE 才可能有；
    ``summary`` 是字幕的 AI 浓缩版（已通过逐字校验，由调用方从缓存读来），
    没校验过的绝不该传进来。
    """
    evidence = evidence_lines(certifications)
    manual = _clean(meme.description)
    # 字幕块就算有人工介绍也照样给：详情页要能点开对照，看这句话到底是不是视频里说的
    transcript = transcript_block(meme, certifications, transcripts)
    if transcript is not None:
        transcript["summary"] = summary

    excerpt = None
    for video in videos:
        body = _usable_excerpt(video.description)
        if body:
            excerpt = {
                "text": body,
                "video_title": _clean(video.title),
                "author": video.author,
                "bvid": video.bvid,
                "url": f"https://www.bilibili.com/video/{video.bvid}" if video.bvid else "",
                "data_source": video.data_source,
            }
            break

    if manual:
        return {
            "text": manual,
            "source": "manual",
            "source_label": "人工撰写",
            "note": "这条介绍由梗管理里人工维护。",
            "evidence": evidence,
            "excerpt": excerpt,
            "transcript": transcript,
        }

    if transcript:
        # 浓缩版能当正文，只因为它被证明是原文句子的子集；证据不足时退回规则摘录，
        # 两者都是逐字原文，区别只在长短和来源标签。
        condensed = (summary or {}).get("text") if (summary or {}).get("verified") else ""
        return {
            "text": _clean(condensed) or transcript["excerpt"],
            "source": "transcript",
            "source_label": "字幕原文摘录" if not condensed else "字幕原文（AI 缩短）",
            "note": (
                "还没有人工介绍。这段摘自解说视频的字幕原文，"
                "系统只按「出自/来历/这个梗」这类说法把在讲这个梗的句子挑出来，没有改写也没有归纳。"
                if not condensed
                else (
                    "还没有人工介绍。这段是 AI 从字幕原文里挑出来的整句，"
                    "逐字核对过：它只负责决定留哪几句，一个字都没写。"
                )
            ),
            "evidence": evidence,
            "excerpt": excerpt,
            "transcript": transcript,
        }

    if evidence or excerpt:
        # text 只放"谁介绍过"这一句；简介摘录单独给 excerpt 字段，
        # 由界面渲染成引用块——同一段原文在详情页出现两次很难看。
        text = "；".join(_source_line(item) for item in evidence)
        text += "。" if text else ""
        if not text and excerpt:
            text = f"暂无解说视频证据，只抓到相关视频《{excerpt['video_title']}》的简介原文。"
        return {
            "text": text,
            "source": "evidence",
            "source_label": "证据原文拼出",
            "note": (
                "还没有人工介绍，也还没抓到这条梗的解说视频字幕"
                "（字幕要 BILI_COOKIE）。上面这段全部来自抓取到的真实数据"
                "（解说视频标题与简介原文），未做任何改写或归纳。"
            ),
            "evidence": evidence,
            "excerpt": excerpt,
            "transcript": None,
        }

    return {
        "text": "",
        "source": "none",
        "source_label": "暂无介绍",
        "note": (
            "这个梗还没有介绍：没有人工稿，没有抓到字幕，也没有可用的解说视频原文。"
            "去梗管理补一条，或跑 app.scripts.fetch_transcripts 抓字幕。"
        ),
        "evidence": [],
        "excerpt": None,
        "transcript": None,
    }
