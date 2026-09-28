"""详情页「这个梗是什么」的合成规则。

实测 55 个真实梗里有 31 个 description 是空的，点进详情页只剩一片空白，
用户会以为系统坏了。所以这里锁住三件事：
* 人工介绍优先，绝不被自动内容覆盖；
* 没有人工介绍时用真实证据原文拼，且**一个字都不改写**（LLM 不参与事实生产）；
* 拼不出来就显式空态，不靠占位文案糊过去。
"""

from __future__ import annotations

from datetime import datetime

from app.models import CertRole
from app.services.meme.certification import record_certification
from app.services.meme.intro import MAX_EXCERPT_CHARS, compose_intro

from .conftest import make_video

LONG_DESC = "这个梗出自一段老动画里的名场面，后来被大家拿来当万能回应句式，弹幕和评论区都在用。"


def _intro(meme, certifications=(), videos=()):
    return compose_intro(meme, certifications, videos)


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
