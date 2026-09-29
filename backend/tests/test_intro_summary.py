"""AI 浓缩介绍：只许挑原句，逐字校验拦住编造。

这层唯一的风险就是"顺"——模型把字幕改成一句更顺的话，读者就再也分不清
哪半句是 UP 主说的、哪半句是模型猜的。所以这里锁死三件事：
* 校验按**整句照抄**做，半句、改词、加连接词都不算；
* 拼接顺序永远按原文顺序，模型换了顺序也不跟；
* 校验不过就返回 None，界面继续用规则摘录，绝不拿一半可信的话上详情页。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import AIInsight, InsightStatus, VideoTranscript
from app.services.llm.config import LLMConfig
from app.services.meme import summary as mod
from app.services.meme.intro import compose_intro, transcript_block

SOURCE = (
    "哈喽大家好，欢迎来到本期视频，今天聊一个新东西。"
    "这个梗出自 2019 年的一场直播，主播在逆风局里反复念同一句话。"
    "所谓逆风局就是快输了的局面。"
    "后来评论区把它做成了万能回应，谁不想解释就发一句。"
    "记得三连加个关注，我们下期再见。"
)
LINE_2 = "这个梗出自 2019 年的一场直播，主播在逆风局里反复念同一句话。"
LINE_3 = "所谓逆风局就是快输了的局面。"
LINE_4 = "后来评论区把它做成了万能回应，谁不想解释就发一句。"

CONFIG = LLMConfig(
    provider="longcat",
    base_url="https://example.test/v1",
    api_key="sk-test",
    model="test-model",
    temperature=0.1,
    max_tokens=900,
    timeout=5.0,
    max_retries=0,
    backoff_base=0.1,
)


class FakeChat:
    """替掉真实补全：记录被调了几次，返回固定的模型输出。"""

    def __init__(self, text: str):
        self.text = text
        self.calls: list[str] = []

    def __call__(self, config, messages, **kwargs):
        self.calls.append(messages[0]["content"])
        return SimpleNamespace(text=self.text, model=config.model, latency_ms=12, usage={})


@pytest.fixture()
def fake_chat(monkeypatch):
    def _bind(text: str) -> FakeChat:
        fake = FakeChat(text)
        monkeypatch.setattr(mod, "chat", fake)
        return fake

    return _bind


# --------------------------------------------------------------------------- #
# 逐字校验


def test_verbatim_keeps_only_whole_source_sentences():
    check = mod.check_verbatim(LINE_2 + LINE_4, SOURCE)
    assert check["ok"] and check["text"] == LINE_2 + LINE_4
    assert check["sentences"] == [LINE_2, LINE_4]
    assert check["invented"] == []


def test_paraphrase_and_invented_numbers_are_rejected():
    """模型把"逆风局"改成"电竞比赛"、把年份补全 —— 这类顺口的话必须整段作废。"""
    check = mod.check_verbatim("这个梗源自 2019 年一场电竞比赛，后来火了。", SOURCE)
    assert not check["ok"] and check["text"] == ""
    assert check["invented"], "自加的句子要留下证据，不能静默丢掉"


def test_half_a_sentence_is_not_a_quote():
    """只抄半句同样会改意思：整句都在原文里才算引用。"""
    check = mod.check_verbatim("这个梗出自 2019 年的一场春晚舞台。", SOURCE)
    assert not check["ok"]


def test_reordering_is_ignored_and_source_order_wins():
    check = mod.check_verbatim(LINE_4 + LINE_2, SOURCE)
    assert check["ok"]
    assert check["text"] == LINE_2 + LINE_4, "拼接顺序跟着原文走，不跟模型走"


def test_over_budget_drops_whole_sentences():
    text = LINE_2 + LINE_3 + LINE_4
    check = mod.check_verbatim(text, SOURCE, budget=len(LINE_2 + LINE_3) - 1)
    assert check["ok"] and check["truncated"]
    assert len(check["text"]) < len(text)
    assert check["text"].endswith("。"), "整句丢弃，不能留半句"
    assert all(item in SOURCE for item in check["sentences"])


def test_predictions_the_model_added_never_survive():
    """模型自己加的那句"预计明天还会火"被逐字校验挡在外面——介绍不许预测未来。"""
    check = mod.check_verbatim(SOURCE + "预计它明天还会再火一轮。", SOURCE)
    assert "预计" not in check["text"] and "预计" not in "".join(check["sentences"])
    assert any("预计" in item for item in check["invented"]), "被拒的话要留证据"


def test_newlines_on_either_side_do_not_break_the_match():
    """字幕按行下发，模型也爱加换行：空白差异不该让同一句被判成"不是原文"。"""
    NL = chr(10)
    candidate = "这个梗出自 2019 年的一场直播，" + NL + "主播在逆风局里反复念同一句话。"
    assert mod.check_verbatim(candidate, SOURCE)["ok"]
    assert mod.check_verbatim(LINE_2, SOURCE.replace("。", "。" + NL))["ok"]


# --------------------------------------------------------------------------- #
# 生成 / 缓存


def test_generate_stores_result_and_second_call_hits_cache(session, meme_factory, fake_chat):
    meme = meme_factory(description="")
    fake = fake_chat(LINE_2 + LINE_4)

    result = mod.generate_intro_summary(
        session, meme_id=meme.id, bvid="BV1x", text=SOURCE, meme_name=meme.name, config=CONFIG
    )
    session.commit()
    assert result and result["verified"] and result["source"] == "llm"
    assert result["text"] == LINE_2 + LINE_4
    assert result["data_version"] == mod.digest("BV1x", SOURCE)
    assert len(fake.calls) == 1
    assert "整句照抄" in fake.calls[0], "提示词要把规矩写死，而不是靠模型自觉"

    again = mod.generate_intro_summary(
        session, meme_id=meme.id, bvid="BV1x", text=SOURCE, meme_name=meme.name, config=CONFIG
    )
    assert again["source"] == "cache" and len(fake.calls) == 1, "同版本字幕不再打模型"


def test_subtitle_change_invalidates_the_cache(session, meme_factory, fake_chat):
    meme = meme_factory(description="")
    fake_chat(LINE_2)
    mod.generate_intro_summary(session, meme_id=meme.id, bvid="BV1x", text=SOURCE, config=CONFIG)
    session.commit()

    fake2 = fake_chat(LINE_3)
    moved = mod.generate_intro_summary(
        session, meme_id=meme.id, bvid="BV1x", text=SOURCE + "补充一句新剪的素材。", config=CONFIG
    )
    session.commit()
    assert moved and len(fake2.calls) == 1, "字幕重抓过就不该继续用旧结论"


def test_failed_check_is_not_readable_as_a_summary(session, meme_factory, fake_chat):
    """校验不过的行不许被读出来用，也不许被当成缓存命中。"""
    meme = meme_factory(description="")
    fake_chat("这个梗大概来自某个直播间吧，反正就是挺火的。")
    result = mod.generate_intro_summary(
        session, meme_id=meme.id, bvid="BV1x", text=SOURCE, meme_name=meme.name, config=CONFIG
    )
    assert result is None

    rows = list(
        session.scalars(
            select(AIInsight).where(AIInsight.kind == mod.INTRO_KIND, AIInsight.meme_id == meme.id)
        )
    )
    assert rows and rows[0].status == InsightStatus.ERROR, "失败也要留档，方便统计模型有多不听话"
    assert rows[0].result["invented"], "自加的句子要记下来"
    assert mod.read_cached_summary(session, meme_id=meme.id, version=mod.digest("BV1x", SOURCE)) is None


def test_missing_key_skips_quietly(session, meme_factory, fake_chat):
    meme = meme_factory(description="")
    fake = fake_chat(LINE_2)
    unconfigured = replace(CONFIG, api_key="")

    assert mod.generate_intro_summary(
        session, meme_id=meme.id, bvid="BV1x", text=SOURCE, config=unconfigured
    ) is None
    assert fake.calls == [], "没配 key 就别打模型"


# --------------------------------------------------------------------------- #
# 与介绍合成的衔接


def _transcript(text: str = SOURCE):
    return VideoTranscript(
        bvid="BV1x", kind="cc", lang="zh-CN", text=text, chars=len(text),
        video_title="这条梗到底哪来的", logged_in=True, fetched_at=datetime(2026, 9, 29),
    )


def test_verified_summary_becomes_the_intro_text(meme_factory):
    meme = meme_factory(description="")
    summary = {"verified": True, "text": LINE_2, "chars": len(LINE_2), "sentences": [LINE_2]}
    result = compose_intro(meme, [], [], [_transcript()], summary)

    assert result["text"] == LINE_2
    assert "AI 缩短" in result["source_label"]
    assert "逐字核对" in result["note"]
    assert result["transcript"]["summary"] == summary
    # 规则摘录仍在，界面上要能对照"没缩短的那版"
    assert result["transcript"]["excerpt"] != LINE_2


def test_unverified_summary_never_reaches_the_page(meme_factory):
    meme = meme_factory(description="")
    block = transcript_block(meme, [], [_transcript()])
    result = compose_intro(meme, [], [], [_transcript()], {"verified": False, "text": "模型编的句子"})

    assert result["text"] == block["excerpt"]
    assert result["source_label"] == "字幕原文摘录"


def test_manual_intro_ignores_the_summary(meme_factory):
    meme = meme_factory(description="人工写好的介绍")
    result = compose_intro(
        meme, [], [], [_transcript()], {"verified": True, "text": LINE_2, "sentences": [LINE_2]}
    )
    assert result["source"] == "manual" and result["text"] == "人工写好的介绍"


def test_summary_note_states_what_the_model_did(meme_factory):
    meme = meme_factory(description="")
    block = transcript_block(meme, [], [_transcript()])
    note = mod.summary_note(
        block, {"sentences": [LINE_2, LINE_4], "chars": len(LINE_2 + LINE_4)}
    )
    assert "挑了 2 句" in note and "整句照抄" in note


# --------------------------------------------------------------------------- #
# 批处理脚本：计数要能直接写进刷新报告


def test_condense_all_writes_then_hits_cache(session, meme_factory, fake_chat):
    from app.scripts.condense_intros import condense_all

    meme = meme_factory(description="", name="浓缩脚本梗")
    session.add(
        VideoTranscript(
            bvid="BV1batch", meme_id=meme.id, kind="cc", lang="zh-CN",
            text=SOURCE, chars=len(SOURCE), video_title="批量测试", logged_in=True,
        )
    )
    session.flush()
    fake = fake_chat(LINE_2 + LINE_4)

    first = condense_all(session, ids=[meme.id], config=CONFIG)
    assert first["targets"] == 1 and first["ok"] == 1 and first["rejected"] == 0
    assert len(fake.calls) == 1

    second = condense_all(session, ids=[meme.id], config=CONFIG)
    assert second["cached"] == 1 and second["ok"] == 0, "同版本字幕不该每天重打一次模型"
    assert len(fake.calls) == 1

    forced = condense_all(session, ids=[meme.id], config=CONFIG, force=True)
    assert forced["ok"] == 1 and len(fake.calls) == 2, "--force 才是真重跑"

    dry = condense_all(session, ids=[meme.id], config=CONFIG, dry_run=True)
    assert dry["skipped"] is True and dry["planned_calls"] == 1
    assert len(fake.calls) == 2, "dry-run 一次模型都不该打"


def test_condense_all_counts_memes_without_usable_subtitle(session, meme_factory, fake_chat):
    from app.scripts.condense_intros import condense_all

    meme = meme_factory(description="", name="闲聊字幕梗")
    chatter = "哈喽大家好。今天天气不错。我们下期再见。"
    session.add(
        VideoTranscript(
            bvid="BV1chat", meme_id=meme.id, kind="ai", lang="zh-CN",
            text=chatter, chars=len(chatter), video_title="闲聊", logged_in=True,
        )
    )
    session.flush()
    fake = fake_chat(LINE_2)

    out = condense_all(session, ids=[meme.id], config=CONFIG)
    assert out["targets"] == 0 and out["no_usable_transcript"] == 1
    assert fake.calls == [], "字幕里没一句在讲这个梗，就不该花钱缩短"
