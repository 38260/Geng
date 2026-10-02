"""AI 梗介绍：材料拼装、事实锚点核对、缓存与降级。

这个模块是"允许模型写句子"的唯一一档，所以守的重点全在**能不能被核对**：
输出里编一个数字、编一个作品名、把思考过程当正文，都必须被拦下并退回原文摘录。

注意：``check_grounded`` 还有一条 60 字的下限，所以用例里的"合格文本"都要写得够长，
否则会因为"过短"被拒，测不到真正想测的那条规则。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import AIInsight, InsightSource, InsightStatus
from app.services.llm.client import ChatResult
from app.services.llm.config import LLMConfig
from app.services.meme import ai_intro, intro
from app.services.meme.certification import record_certification

from .conftest import make_video

MATERIAL = """梗名：冰冰冰
别名/常见叫法：冰冰冰是啥梗
主题标签：音乐 & 舞蹈
梗解说视频（梗百科，2026-09-29）：《【梗百科】冰冰冰是啥梗？🧊🧊🧊》
站内相关视频（按播放量降序）：
· 《冰冰冰10小时纯享版》（267,022 播放）
· 《10.7亿个“冰冰冰”相继播放》（490,216 播放）"""

# 测试环境的 LLM_API_KEY 是空的（见 conftest），所以这几条用例要显式传一个"已配置"的
# config，否则 generate_meme_intro 会在打模型之前就返回 None，测不到后面的逻辑。
STUB_CONFIG = LLMConfig(
    provider="stub",
    base_url="http://stub.local/v1",
    api_key="sk-test",
    model="stub-model",
    temperature=0.3,
    max_tokens=900,
    timeout=5,
    max_retries=0,
    backoff_base=0.1,
)

# 生成类用例用的是**光杆梗**（没视频、没认证），它的材料里只有梗名一行，
# 所以这类用例要用不带数字/专名的版本，否则会被事实核对正确地拦下。
GOOD_PLAIN = (
    "缓存梗是一段反复出现在循环合集里的音效，常被做成动辄几小时的纯享版在站内传播，"
    "很多人把它当成写作业和打游戏时的洗脑背景音，相关二创也越来越多。"
)

# 一段"合格"的摘要：数字与《专名》都能在 MATERIAL 里找到，且长度过 60 字下限
GOOD = (
    "冰冰冰是一段反复出现在循环合集里的音效，常被做成动辄几小时的纯享版在站内传播，"
    "播放量最高的一条达到了 490,216 次，很多人把它当成写作业和打游戏时的洗脑背景音。"
)


# --------------------------------------------------------------------------- #
# 材料
# --------------------------------------------------------------------------- #
def test_material_includes_every_evidence_kind(session, meme_factory):
    meme = meme_factory("材料梗", aliases=["材料梗别名"], keywords=["材料关键词"], tags=["music"])
    record_certification(
        session, meme, "encyclopedia",
        bvid="BV1aa", video_title="【梗百科】材料梗是啥梗",
        published_at=datetime.now() - timedelta(days=2), data_source="bilibili",
    )
    videos = [
        make_video("BV1bb", "材料梗纯享版", view=12345, description="一闪二踢三哆嗦四摇头", data_source="bilibili"),
        make_video("BV1cc", "无关视频", view=100, data_source="bilibili"),
    ]

    material = ai_intro.build_material(meme, meme.certifications, videos)

    assert "梗名：材料梗" in material
    assert "材料梗别名" in material
    assert "材料关键词" in material
    assert "音乐 & 舞蹈" in material          # 标签存的是 key，材料里要翻成中文
    assert "【梗百科】材料梗是啥梗" in material
    assert "材料梗纯享版" in material
    assert "12,345 播放" in material
    assert "一闪二踢三哆嗦四摇头" in material


def test_material_drops_production_credits(session, meme_factory):
    """制作人员名单与推广话术对"这是什么梗"没用，喂给模型只会被抄进摘要。"""
    meme = meme_factory("署名梗")
    noisy = (
        "这音效小时候抱过我 CV：伊闪闪 文案：灵念卿 后期：MrChenBeta "
        "若发现视频中存在问题，欢迎附上材料，发邮件到gengwiki@sina.com，一经查实会给予辛苦费 "
        "▶微博：某某 ▶网易云：某某"
    )
    videos = [make_video("BV1dd", "署名梗", view=10, description=noisy, data_source="bilibili")]

    material = ai_intro.build_material(meme, [], videos)

    assert "这音效小时候抱过我" in material      # 真正在说内容的那半句要留下
    assert "伊闪闪" not in material
    assert "@sina.com" not in material
    assert "微博" not in material


def test_material_highlights_origin_clues(session, meme_factory):
    """标题/简介里明确写了来源的，要单独进「出处线索」块。

    这一块决定摘要能不能写出"它从哪来"：实测入池 48 只里 35 只有线索，
    但混在十几条标题里时模型常常整段跳过来源。
    """
    meme = meme_factory("出处梗")
    videos = [
        make_video("BV1e1", "出处梗原版视频", view=1000, data_source="bilibili"),
        make_video(
            "BV1e2", "出处梗二创合集", view=900,
            description="油管原作者是某某老师", data_source="bilibili",
        ),
        make_video(
            "BV1e3", "出处梗随便拍拍", view=100,
            description="今天随手拍了一点东西", data_source="bilibili",
        ),
    ]

    material = ai_intro.build_material(meme, [], videos)

    assert "出处线索" in material
    # 出处块只到下一个标题为止，否则会把「其它简介」也圈进来
    origin_block = material.split("出处线索", 1)[1].split("其它相关视频的简介原文", 1)[0]
    assert "出处梗原版视频" in origin_block              # 标题里带"原版"
    assert "油管原作者是某某老师" in origin_block          # 简介里带"原作者"
    # 不带出处信息的简介走另一块，别混进出处线索
    assert "其它相关视频的简介原文" in material
    assert "今天随手拍了一点东西" not in origin_block


def test_material_digest_changes_with_material_and_prompt_version(monkeypatch):
    base = ai_intro.material_digest(MATERIAL)
    assert ai_intro.material_digest(MATERIAL + "\n新增一行") != base
    # 空白差异不该改变指纹：材料是按行拼的，多一个换行不算新材料
    assert ai_intro.material_digest(MATERIAL + "\n") == base

    monkeypatch.setattr(ai_intro, "PROMPT_VERSION", "v99")
    assert ai_intro.material_digest(MATERIAL) != base


# --------------------------------------------------------------------------- #
# 事实锚点核对
# --------------------------------------------------------------------------- #
def test_grounded_summary_passes():
    check = ai_intro.check_grounded(GOOD, MATERIAL)
    assert check["ok"] is True
    assert check["text"] == GOOD
    assert check["invented"] == []


@pytest.mark.parametrize(
    ("text", "keyword"),
    [
        (
            "冰冰冰最早出现在 2019 年的一段广告里，后来被搬到 B 站，成了循环歌单的常客，"
            "很多人拿它当洗脑背景音，相关的纯享版合集也越做越多。",
            "2019",
        ),
        (
            "冰冰冰出自《冰雪奇缘》的插曲，后来被剪成音效在站内传播，常见于各种循环合集，"
            "不少人拿它当写作业时的背景音，相关的纯享版也越做越多。",
            "冰雪奇缘",
        ),
        (
            "冰冰冰是一段用 FLStudio 制作的音效，常出现在循环合集里被反复使用，"
            "很多人拿它当写作业时的背景音，相关的纯享版合集也越做越多。",
            "FLStudio",
        ),
    ],
)
def test_invented_facts_are_rejected(text, keyword):
    """数字 / 书名号里的作品名 / 英文字母串都要能在材料里找到，否则整段作废。"""
    check = ai_intro.check_grounded(text, MATERIAL)
    assert check["ok"] is False
    assert keyword in check["reason"]


@pytest.mark.parametrize(
    "text",
    [
        "根据提供的材料，冰冰冰是一段反复出现的音效，常见于各种循环合集，被大量二创使用，整体传播度很高。",
        "上述内容表明，冰冰冰是一段反复出现的音效，常见于各种循环合集，被大量二创使用，整体传播度很高。",
        "冰冰冰接下来一定会更火，预计下个月会突破千万播放，成为站内最流行的音效之一，值得持续关注。",
    ],
)
def test_meta_talk_and_predictions_are_rejected(text):
    assert ai_intro.check_grounded(text, MATERIAL)["ok"] is False


def test_fact_tokens_ignore_ascii_case():
    """材料里是 vlog、模型写 Vlog，不该算编造（实测误报过一次）。"""
    material = MATERIAL + "\n某条相关视频的简介原文：vlog 记录"
    text = (
        "冰冰冰是一段反复出现在循环合集里的音效，常被做成纯享版，也有人用 Vlog 的形式记录，"
        "播放量最高的一条达到了 490,216 次，很多人拿它当洗脑背景音。"
    )
    assert ai_intro.check_grounded(text, material)["ok"] is True


def test_generic_platform_words_are_not_fabrication():
    """UP主 / emoji / meme 这类平台通用词不是"关于这个梗的事实"，别冤杀整段。"""
    text = (
        "冰冰冰是一段反复出现在循环合集里的音效，UP主们常把它做成纯享版配上 emoji 封面，"
        "播放量最高的一条达到了 490,216 次，很多人拿它当洗脑背景音。"
    )
    assert ai_intro.check_grounded(text, MATERIAL)["ok"] is True


def test_invented_ascii_token_is_still_rejected():
    """白名单只放通用词：真编一个软件名照样要拦下。"""
    text = (
        "冰冰冰是一段用 FLStudio 制作的音效，常出现在循环合集里被反复使用，"
        "播放量最高的一条达到了 490,216 次，很多人拿它当洗脑背景音。"
    )
    assert ai_intro.check_grounded(text, MATERIAL)["ok"] is False


def test_too_short_and_insufficient_are_rejected():
    assert ai_intro.check_grounded("冰冰冰是一段音效。", MATERIAL)["ok"] is False
    assert ai_intro.check_grounded("INSUFFICIENT", MATERIAL)["ok"] is False


def test_overlong_output_is_cut_at_sentence_boundary():
    sentence = "冰冰冰是一段反复出现的音效，常见于各种循环合集。"
    check = ai_intro.check_grounded(sentence * 30, MATERIAL, budget=80)
    assert check["ok"] is True
    assert check["truncated"] is True
    assert len(check["text"]) <= 80
    assert check["text"].endswith("。")


# --------------------------------------------------------------------------- #
# 生成与缓存
# --------------------------------------------------------------------------- #
def _completion(text: str, *, reasoning_only: bool = False) -> ChatResult:
    return ChatResult(
        text=text, model="stub-model", latency_ms=1, usage={}, reasoning_only=reasoning_only
    )


def test_generate_stores_cache_and_reads_back(session, meme_factory, monkeypatch):
    meme = meme_factory("缓存梗")
    monkeypatch.setattr(ai_intro, "chat", lambda *a, **k: _completion(GOOD_PLAIN))

    result = ai_intro.generate_meme_intro(session, meme, videos=[], config=STUB_CONFIG)
    assert result is not None
    assert result["verified"] is True
    assert result["text"] == GOOD_PLAIN

    material = ai_intro.build_material(meme, [], [])
    cached = ai_intro.read_cached_ai_intro(
        session, meme_id=meme.id, version=ai_intro.material_digest(material)
    )
    assert cached is not None
    assert cached["text"] == GOOD_PLAIN
    assert cached["source"] == InsightSource.CACHE
    # 材料要一起存下来：界面上「依据可核对」靠它
    assert "梗名：缓存梗" in cached["material"]


def test_ungrounded_output_is_recorded_as_error_and_returns_none(session, meme_factory, monkeypatch):
    meme = meme_factory("编造梗")
    fabricated = (
        "编造梗最早出自 1998 年的一部国产动画短片，后来被网友搬到 B 站做成音效，"
        "在循环合集里反复出现，很多人拿它当洗脑背景音，相关二创也越来越多。"
    )
    monkeypatch.setattr(ai_intro, "chat", lambda *a, **k: _completion(fabricated))

    assert ai_intro.generate_meme_intro(session, meme, videos=[], config=STUB_CONFIG) is None

    row = session.query(AIInsight).filter(AIInsight.meme_id == meme.id).one()
    assert row.status == InsightStatus.ERROR
    assert row.result["text"] == ""
    assert "1998" in row.result["reason"]


def test_reasoning_only_output_is_retried_with_bigger_budget(session, meme_factory, monkeypatch):
    """客户端在 content 为空时会退回 reasoning_content——那是思考过程，不是介绍。

    第一次拿到思考段必须换更大预算重试，绝不把它当正文写进库。
    """
    meme = meme_factory("思考段梗")
    calls: list[int] = []

    def fake_chat(config, messages, *, temperature=0, max_tokens=0):
        calls.append(max_tokens)
        if len(calls) == 1:
            return _completion("Let me analyze the material carefully.", reasoning_only=True)
        return _completion(GOOD_PLAIN)

    monkeypatch.setattr(ai_intro, "chat", fake_chat)

    result = ai_intro.generate_meme_intro(session, meme, videos=[], config=STUB_CONFIG)
    assert len(calls) == 2
    assert calls[1] > calls[0]
    assert result is not None and result["text"] == GOOD_PLAIN


def test_both_attempts_reasoning_only_gives_up_without_writing(session, meme_factory, monkeypatch):
    meme = meme_factory("全是思考段梗")
    monkeypatch.setattr(ai_intro, "chat", lambda *a, **k: _completion("thinking…", reasoning_only=True))
    assert ai_intro.generate_meme_intro(session, meme, videos=[], config=STUB_CONFIG) is None
    assert session.query(AIInsight).filter(AIInsight.meme_id == meme.id).count() == 0


# --------------------------------------------------------------------------- #
# 与既有的四档拼装
# --------------------------------------------------------------------------- #
def test_ai_tier_sits_between_manual_and_evidence():
    from app.models import Meme

    def make(description: str = "") -> Meme:
        return Meme(name="档位梗", slug="tier", aliases=[], keywords=[], description=description)

    ai = {"text": GOOD, "material": MATERIAL}

    assert intro.compose_intro(make(), [], [], [], None, ai)["source"] == "ai"
    # 人工稿优先级最高
    assert intro.compose_intro(make("人工写的一段"), [], [], [], None, ai)["source"] == "manual"
    # 没有 AI 摘要、也没有原文证据 → 显式空态，而不是留白
    empty = intro.compose_intro(make(), [], [], [], None, None)
    assert empty["source"] == "none"
    assert empty["text"] == ""
    assert empty["note"]


def test_compose_intro_exposes_ai_for_verification():
    from app.models import Meme

    meme = Meme(name="留证梗", slug="proof", aliases=[], keywords=[], description="")
    payload = intro.compose_intro(meme, [], [], [], None, {"text": GOOD, "material": MATERIAL})
    assert payload["ai"]["material"] == MATERIAL
    assert "AI" in payload["source_label"]
