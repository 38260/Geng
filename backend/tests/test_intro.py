"""详情页「这个梗是什么」的合成规则。

实测 55 个真实梗里有 31 个 description 是空的，点进详情页只剩一片空白，
用户会以为系统坏了。所以这里锁住三件事：
* 人工介绍优先，绝不被自动内容覆盖；
* 没有人工介绍时用真实证据原文拼，且**一个字都不改写**（LLM 不参与事实生产）；
* 拼不出来就显式空态，不靠占位文案糊过去。
"""

from __future__ import annotations

from datetime import datetime

from app.models import CertRole, VideoTranscript
from app.services.meme.certification import record_certification
from app.services.meme.intro import (
    MAX_EXCERPT_CHARS,
    MAX_FULL_CHARS,
    MAX_SEGMENT_CHARS,
    compose_intro,
    select_segment,
)

from .conftest import make_video

LONG_DESC = "这个梗出自一段老动画里的名场面，后来被大家拿来当万能回应句式，弹幕和评论区都在用。"


def _intro(meme, certifications=(), videos=(), transcripts=()):
    return compose_intro(meme, certifications, videos, transcripts)


def _transcript(bvid: str, text: str, *, kind: str = "cc", title: str = "解说视频标题", chars: int | None = None):
    """字幕行不用入库：介绍合成只读字段，构造对象就够了。"""
    return VideoTranscript(
        bvid=bvid,
        kind=kind,
        lang="zh-CN",
        text=text,
        chars=len(text) if chars is None else chars,
        video_title=title,
        logged_in=True,
        fetched_at=datetime(2026, 9, 29, 10, 0),
    )


def test_manual_description_wins(meme_factory):
    meme = meme_factory(description="  人工写好的介绍  ")
    result = _intro(meme)
    assert result["source"] == "manual"
    assert result["text"] == "人工写好的介绍", "顺手把首尾空白清掉，别把排版问题带进 UI"
    assert result["source_label"] == "人工撰写"


def test_empty_description_with_evidence_is_not_blank(meme_factory, session):
    """没有人工介绍时，用解说视频标题原文拼一句有出处的话。"""
    meme = meme_factory(description="")
    record_certification(
        session, meme, CertRole.GUIDE,
        bvid="BV1gui0001", video_title="测试梗是什么梗【梗指南】",
        published_at=datetime(2026, 9, 1, 12, 0), data_source="bilibili",
    )
    record_certification(
        session, meme, CertRole.ENCYCLOPEDIA,
        bvid="BV1enc0001", video_title="【梗百科】测试梗是啥梗？",
        published_at=datetime(2026, 8, 30, 12, 0), data_source="bilibili",
    )

    result = _intro(meme, meme.certifications)
    assert result["source"] == "evidence"
    assert result["text"], "详情页不能是空白"
    assert "【梗百科】测试梗是啥梗？" in result["text"]
    assert "测试梗是什么梗【梗指南】" in result["text"]
    # 梗百科是主源，排在前面（和详情页认证条、发现层顺序一致）
    assert [e["up_label"] for e in result["evidence"]] == ["梗百科", "梗指南"]
    assert result["evidence"][0]["video_url"] == "https://www.bilibili.com/video/BV1enc0001"
    assert "未做任何改写" in result["note"], "要让用户知道这段不是系统编的"


def test_no_evidence_no_description_is_explicit_empty_state(meme_factory):
    result = _intro(meme_factory(description=""))
    assert result["source"] == "none"
    assert result["text"] == ""
    assert result["evidence"] == []
    assert "去梗管理补一条" in result["note"] or "还没有介绍" in result["note"]


def test_excerpt_prefers_longest_viewed_real_description(meme_factory, session):
    meme = meme_factory(description="", aliases=["测试梗别名"])
    record_certification(
        session, meme, CertRole.ENCYCLOPEDIA,
        bvid="BV1enc0002", video_title="【梗百科】测试梗是啥梗？", data_source="bilibili",
    )
    videos = [
        # 播放量最高但简介只有一个「-」，属于占位噪声，不该进介绍
        make_video("BV1a00001", "测试梗 高播放", description="-", view=9_000_000),
        make_video("BV1a00002", "测试梗 有简介", description=LONG_DESC, view=5_000_000),
        # 太短的简介（求三连一类）信息量不足，直接跳过
        make_video("BV1a00003", "测试梗 短简介", description="记得三连", view=7_000_000),
    ]
    result = _intro(meme, meme.certifications, videos)
    assert result["excerpt"] is not None
    assert result["excerpt"]["text"] == LONG_DESC
    assert result["excerpt"]["video_title"] == "测试梗 有简介"
    # 原文只出现在摘录块里，不被塞进正文重复一遍
    assert LONG_DESC not in result["text"]
    assert "测试梗 高播放" not in result["text"]


def test_plead_storm_is_not_an_excerpt(meme_factory, session):
    """"求三连"刷屏的简介字数够，但没有信息量，不该被当成介绍。"""
    meme = meme_factory(description="")
    noisy = "求三连~" * 30
    result = _intro(meme, [], [make_video("BV1c00001", "整活视频", description=noisy)])
    assert result["excerpt"] is None
    assert result["source"] == "none"


def test_hashtags_are_stripped_and_excerpt_is_capped(meme_factory, session):
    meme = meme_factory(description="")
    long_text = (
        "这个梗来自一段游戏直播，主播在逆风局里反复念同一句台词，"
        "于是弹幕开始集体复读，后来被剪成各种整活视频，"
        "甚至有人把它做成了表情包和手机壳，传播范围远超原视频。"
    )
    noisy = "#游戏直播 #整活 #每日复读 " + long_text + " #梗百科"
    result = _intro(meme, [], [make_video("BV1b00001", "带话题标签的视频", description=noisy)])
    assert result["excerpt"] is not None
    assert "#" not in result["excerpt"]["text"]
    assert result["excerpt"]["text"].startswith("这个梗来自一段游戏直播")
    assert len(result["excerpt"]["text"]) <= MAX_EXCERPT_CHARS + 20


def test_demo_evidence_gets_no_clickable_link(meme_factory, session, monkeypatch):
    """演示证据不许给链接：点进去是 404，比不链接更糟。"""
    from app.config import settings

    monkeypatch.setattr(settings, "data_source", "mock")
    meme = meme_factory(description="")
    record_certification(
        session, meme, CertRole.ENCYCLOPEDIA,
        bvid="BV1mock001", video_title="【演示】测试梗", data_source="mock",
    )
    result = _intro(meme, meme.certifications)
    assert result["evidence"][0]["video_url"] == ""
    assert result["evidence"][0]["verified"] is False


# --------------------------------------------------------------------------- #
# 第②档：字幕原文。视频里说的话才是内容，标题和简介都只是包装


CC_TEXT = (
    "哈喽大家好，欢迎来到本期视频，我们直接开始。"
    "这个梗出自 2019 年的一场游戏直播，主播在逆风局里反复念同一句话。"
    "所谓逆风局就是快输了的局面。"
    "后来评论区把它做成了万能回应，谁不想解释就发一句。"
    "记得三连加个关注，我们下期再见。"
)


def _certified(session, meme):
    record_certification(
        session, meme, CertRole.ENCYCLOPEDIA,
        bvid="BV1enc0009", video_title="【梗百科】测试梗是啥梗？", data_source="bilibili",
    )


def test_transcript_beats_title_and_description_evidence(meme_factory, session):
    """有人工介绍之前，字幕原文优先于「标题+简介拼出来的证据」——那是内容，这不是。"""
    meme = meme_factory(description="")
    _certified(session, meme)
    result = _intro(meme, meme.certifications, [], [_transcript("BV1enc0009", CC_TEXT)])

    assert result["source"] == "transcript"
    assert result["source_label"] == "字幕原文摘录"
    block = result["transcript"]
    assert block["kind"] == "cc" and block["kind_label"] == "人工字幕"
    assert block["certified"] is True and block["up_label"] == "梗百科"
    assert block["bvid"] == "BV1enc0009"
    assert block["url"] == "https://www.bilibili.com/video/BV1enc0009"
    assert "没有改写也没有归纳" in result["note"]


def test_segment_only_keeps_sentences_that_explain_the_meme(meme_factory, session):
    """开场白、求三连、道别都不该进介绍；留下的每句都还能在原文里找到。"""
    meme = meme_factory(description="")
    _certified(session, meme)
    block = _intro(meme, meme.certifications, [], [_transcript("BV1enc0009", CC_TEXT)])["transcript"]

    assert "欢迎来到本期视频" not in block["excerpt"]
    assert "三连" not in block["excerpt"]
    assert "下期再见" not in block["excerpt"]
    assert block["excerpt"] == (
        "这个梗出自 2019 年的一场游戏直播，主播在逆风局里反复念同一句话。"
        "所谓逆风局就是快输了的局面。"
        "后来评论区把它做成了万能回应，谁不想解释就发一句。"
    )
    assert block["matched_sentences"] == 3
    assert block["excerpt_chars"] == len(block["excerpt"]) <= MAX_SEGMENT_CHARS
    # 没超长的字幕就该整段给折叠区，不截
    assert block["full_truncated"] is False and block["full"] == CC_TEXT


def test_ai_subtitle_is_labelled_as_ai(meme_factory, session):
    """AI 识别的字幕错字多，界面必须说清这是机器听写的，不是 UP 主写的。"""
    meme = meme_factory(description="")
    _certified(session, meme)
    result = _intro(
        meme, meme.certifications, [],
        [_transcript("BV1enc0009", CC_TEXT, kind="ai")],
    )
    block = result["transcript"]
    assert block["kind"] == "ai" and block["kind_label"] == "AI 识别字幕"
    assert "错字" in block["kind_hint"]


def test_human_cc_preferred_over_ai_subtitle(meme_factory, session):
    meme = meme_factory(description="")
    _certified(session, meme)
    result = _intro(
        meme, meme.certifications, [],
        [
            _transcript("BV1enc0009", CC_TEXT, kind="ai"),
            _transcript("BV1enc0009", "这个梗的来历是主播口误，后来被剪成了鬼畜素材。", kind="cc"),
        ],
    )
    assert result["transcript"]["kind"] == "cc"
    assert result["transcript"]["excerpt"] == "这个梗的来历是主播口误，后来被剪成了鬼畜素材。"


def test_subtitle_without_any_explaining_line_falls_back_to_evidence(meme_factory, session):
    """整期都在闲聊／念弹幕时宁可退回证据档，也不随便挑一句当「这个梗是什么」。"""
    meme = meme_factory(description="")
    _certified(session, meme)
    chatter = "哈喽大家好。今天天气不错。弹幕别说我听不清。我们下期再见。"
    result = _intro(meme, meme.certifications, [], [_transcript("BV1enc0009", chatter)])
    assert result["source"] == "evidence"
    assert result["transcript"] is None
    assert result["text"], "证据档仍要有内容"


def test_subtitle_from_uncertified_video_is_marked(meme_factory, session):
    """非认证视频的字幕也能用，但要标出来，不能伪装成双 UP 的说法。"""
    meme = meme_factory(description="")
    _certified(session, meme)
    block = _intro(
        meme, meme.certifications, [],
        [_transcript("BV1random", "这个梗出自一条整活视频，后来才火起来的。")],
    )["transcript"]
    assert block["certified"] is False and block["bvid"] == "BV1random"


def test_manual_intro_still_ships_the_subtitle_for_comparison(meme_factory, session):
    """人工介绍排第一，但字幕块照样给：详情页要能点开对照，看这句话是不是视频真说过。"""
    meme = meme_factory(description="人工写好的介绍")
    _certified(session, meme)
    result = _intro(meme, meme.certifications, [], [_transcript("BV1enc0009", CC_TEXT)])
    assert result["source"] == "manual"
    assert result["transcript"] is not None


def test_full_transcript_truncated(meme_factory, session):
    """折叠区只给前 MAX_FULL_CHARS 字，剩下的引导去看视频，别把详情接口变成下载器。"""
    meme = meme_factory(description="")
    _certified(session, meme)
    block = _intro(
        meme, meme.certifications, [],
        [_transcript("BV1enc0009", "这个梗的来历是主播口误。" * 200)],
    )["transcript"]
    assert block["full_truncated"] is True
    assert len(block["full"]) <= MAX_FULL_CHARS + 10
    assert block["chars"] == 12 * 200
    # 正文选段仍然受更小的预算管住，不受全文长度影响
    assert len(block["excerpt"]) <= MAX_SEGMENT_CHARS


def test_select_segment_returns_empty_when_nothing_matches():
    assert select_segment("今天心情不错，随便聊聊。", ["测试梗"]) == ("", 0)


def test_segment_keeps_document_order_not_score_order():
    """分数决定谁先进预算，原文顺序决定读起来的顺序。"""
    text = (
        "这个梗的来历其实很简单。"
        "所谓出处就是那场直播里的一句话。"
        "测试梗的说法来自一句口误。"
    )
    excerpt, hits = select_segment(text, ["测试梗"])
    assert hits == 3
    assert excerpt == text, "三句都命中且预算够，就按原文顺序全留"
