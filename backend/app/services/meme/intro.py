"""梗介绍：详情页「这个梗是什么」这一段的来源与合成规则。

原则只有一条：**不编造**。介绍只有三个来源，优先级从高到低：

1. ``manual``  —— 人工在梗管理里写好的 ``meme.description``；
2. ``evidence`` —— 用已经抓到的真实证据原文拼出来：哪位 UP 主、哪一期解说视频
   （标题是 B 站返回的原文），再附上头部相关视频里字数够长的真实简介摘录；
3. ``none``     —— 什么都没有。这时界面必须显式说"还没有介绍"并给出补介绍的入口，
   不能留一片空白让人以为系统坏了。

``evidence`` 这条路刻意不做任何改写和归纳：LLM 没配 key 时不能凭空写，配了 key
也不该由它来定义"这个梗是什么"（V1 约定：AI 只复述算法结论，不生产事实）。
所以这里拼出来的每个字都能在 ``videos`` / ``meme_certifications`` 两张表里找到出处。
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.config import settings
from app.models import Meme, MemeCertification, Video

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
_SENTENCE_END = re.compile(r"[。！？!?；;，\n]")


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
) -> dict[str, Any]:
    """组装详情页要用的介绍结构体。

    ``videos`` 传进来时应当已按播放量降序（取第一条简介够长的做摘录）。
    """
    evidence = evidence_lines(certifications)
    manual = _clean(meme.description)

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
                "还没有人工介绍。上面这段全部来自抓取到的真实数据"
                "（解说视频标题与简介原文），未做任何改写或归纳。"
            ),
            "evidence": evidence,
            "excerpt": excerpt,
        }

    return {
        "text": "",
        "source": "none",
        "source_label": "暂无介绍",
        "note": "这个梗还没有介绍，也没有可用的解说视频原文，去梗管理补一条即可上详情页。",
        "evidence": [],
        "excerpt": None,
    }
