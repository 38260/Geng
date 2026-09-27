"""LLM 业务层：降级、缓存、以及"AI 不能改事实"。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.config import settings
from app.models import InsightKind, InsightSource, InsightStatus
from app.services.llm import client as client_module
from app.services.llm import service as service_module
from app.services.llm.client import LLMError, chat
from app.services.llm.config import LLMConfig, load_config
from app.services.llm.service import (
    generate_catch_up_advice,
    generate_trend_explanation,
    parse_json_object,
    render_prompt,
    rule_based_trend,
)

NOT_CONFIGURED = LLMConfig(
    provider="longcat", base_url="https://api.longcat.chat/openai/v1", api_key="",
    model="LongCat-2.5-Preview", temperature=0.3, max_tokens=300, timeout=5,
    max_retries=1, backoff_base=0.01,
)
CONFIGURED = LLMConfig(
    provider="longcat", base_url="https://api.longcat.chat/openai/v1", api_key="sk-test-1234567890",
    model="LongCat-2.5-Preview", temperature=0.3, max_tokens=300, timeout=5,
    max_retries=1, backoff_base=0.01,
)

TREND_DATA = {
    "hotness": 87,
    "growth": 0.68,
    "video_growth": 0.68,
    "discussion_growth": 0.51,
    "danmaku_growth": 0.74,
    "creator_growth": 0.42,
    "lifecycle": "rising",
    "lifecycle_label": "上升期",
    "peak_gap": 0.02,
}

CATCH_DATA = {
    "hotness": 87,
    "growth": 0.68,
    "creator_growth": 0.42,
    "lifecycle": "rising",
    "lifecycle_label": "上升期",
    "peak_gap": 0.02,
    "status": "can_catch",
    "confidence": 0.82,
}


def _fake_completion(text: str):
    def _chat(config, messages, **kwargs):
        return client_module.ChatResult(text=text, model=config.model, latency_ms=12, usage={})

    return _chat


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
def test_missing_key_is_reported_as_not_configured():
    assert NOT_CONFIGURED.is_configured is False
    with pytest.raises(Exception) as excinfo:
        chat(NOT_CONFIGURED, [{"role": "user", "content": "hi"}])
    assert excinfo.value.kind == "not_configured"


def test_masked_config_never_exposes_the_key():
    masked = CONFIGURED.masked()
    assert "sk-test-1234567890" not in json.dumps(masked)
    assert masked["api_key_set"] is True
    assert masked["api_key_masked"].startswith("sk-") and masked["api_key_masked"].endswith("7890")


def test_url_helpers():
    assert CONFIGURED.chat_completions_url.endswith("/chat/completions")
    assert CONFIGURED.models_url == "https://api.longcat.chat/openai/v1"
    assert LLMConfig(**{**CONFIGURED.__dict__, "base_url": "https://x/v1/chat/completions"}).models_url == "https://x/v1"


# --------------------------------------------------------------------------- #
# 提示词
# --------------------------------------------------------------------------- #
def test_prompts_are_external_files_and_get_filled():
    rendered = render_prompt("trend-explanation", {"hotness": 87})
    assert "{{DATA}}" not in rendered
    assert '"hotness": 87' in rendered
    assert "不要预测未来" in rendered or "不要预测" in rendered


def test_rule_based_trend_covers_every_stage():
    for stage, label in [
        ("sprouting", "萌芽期"), ("rising", "上升期"), ("explosive", "爆发期"),
        ("plateau", "平稳期"), ("receding", "退潮期"), ("obsolete", "过气"),
    ]:
        text = rule_based_trend({**TREND_DATA, "lifecycle": stage, "lifecycle_label": label})
        assert text and len(text) <= 140
        assert "AI" not in text


# --------------------------------------------------------------------------- #
# 降级
# --------------------------------------------------------------------------- #
def test_trend_explanation_falls_back_to_rule_text_without_key(session, meme_factory):
    meme = meme_factory()
    output = generate_trend_explanation(
        session, meme_id=meme.id, data=TREND_DATA, data_version="v1", config=NOT_CONFIGURED
    )
    assert output.status == InsightStatus.OK
    assert output.source == InsightSource.RULE
    assert output.result["text"]
    assert "LLM_API_KEY" in (output.error or "")


def test_fallback_can_be_disabled_for_a_strict_unavailable(session, meme_factory, monkeypatch):
    meme = meme_factory()
    monkeypatch.setattr(settings, "llm_allow_rule_based_fallback", False)
    output = generate_trend_explanation(
        session, meme_id=meme.id, data=TREND_DATA, data_version="v1-strict", config=NOT_CONFIGURED
    )
    assert output.status == InsightStatus.UNAVAILABLE
    assert output.result == {}


def test_llm_error_does_not_break_trend_or_catchup(session, meme_factory, monkeypatch):
    meme = meme_factory()

    def boom(config, messages, **kwargs):
        raise LLMError("LLM 返回 429：rate limited", kind="rate_limited", status=429)

    monkeypatch.setattr(service_module, "chat", boom)

    trend = generate_trend_explanation(
        session, meme_id=meme.id, data=TREND_DATA, data_version="v-err-1", config=CONFIGURED
    )
    assert trend.status == InsightStatus.OK and trend.source == InsightSource.RULE

    advice = generate_catch_up_advice(
        session, meme_id=meme.id, data=CATCH_DATA, data_version="v-err-2", config=CONFIGURED
    )
    assert advice.status == InsightStatus.UNAVAILABLE


# --------------------------------------------------------------------------- #
# 正常路径 + 约束
# --------------------------------------------------------------------------- #
def test_trend_explanation_uses_model_output(session, meme_factory, monkeypatch):
    meme = meme_factory()
    monkeypatch.setattr(
        service_module, "chat",
        _fake_completion("最近一周相关内容涨得很猛，进来做的 UP 主也明显变多了。"),
    )
    output = generate_trend_explanation(
        session, meme_id=meme.id, data=TREND_DATA, data_version="v-ok", config=CONFIGURED
    )
    assert output.source == InsightSource.LLM
    assert "涨得很猛" in output.result["text"]


def test_model_cannot_change_the_algorithm_decision(session, meme_factory, monkeypatch):
    """AI 不能修改事实：status 永远以算法给出的 can_catch 为准。"""
    meme = meme_factory()
    payload = {"status": "too_late", "label": "你来晚了", "reason": "现在赶还来得及，热度还在往上走。", "confidence": 0.99}
    monkeypatch.setattr(service_module, "chat", _fake_completion(f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"))

    output = generate_catch_up_advice(
        session, meme_id=meme.id, data=CATCH_DATA, data_version="v-guard", config=CONFIGURED
    )
    assert output.result["status"] == "can_catch"
    assert output.result["label"] == "还来得及"
    assert output.result["confidence"] <= 0.95


def test_prediction_flavoured_output_is_rejected(session, meme_factory, monkeypatch):
    meme = meme_factory()
    payload = {
        "status": "can_catch",
        "reason": "预计未来7天热度会达到92，这个梗明天一定爆。",
        "confidence": 0.9,
    }
    monkeypatch.setattr(service_module, "chat", _fake_completion(json.dumps(payload, ensure_ascii=False)))

    output = generate_catch_up_advice(
        session, meme_id=meme.id, data=CATCH_DATA, data_version="v-predict", config=CONFIGURED
    )
    assert "预计" not in output.result["reason"]
    assert "一定会爆" not in output.result["reason"]


# --------------------------------------------------------------------------- #
# 缓存
# --------------------------------------------------------------------------- #
def test_same_data_version_is_served_from_cache(session, meme_factory, monkeypatch):
    meme = meme_factory()
    calls = {"n": 0}
    real = _fake_completion("热度还在往上走，参与创作的人越来越多。")

    def counting_chat(config, messages, **kwargs):
        calls["n"] += 1
        return real(config, messages, **kwargs)

    monkeypatch.setattr(service_module, "chat", counting_chat)

    first = generate_trend_explanation(
        session, meme_id=meme.id, data=TREND_DATA, data_version="v-cache", config=CONFIGURED
    )
    second = generate_trend_explanation(
        session, meme_id=meme.id, data=TREND_DATA, data_version="v-cache", config=CONFIGURED
    )
    assert first.source == InsightSource.LLM
    assert second.source == InsightSource.CACHE
    assert calls["n"] == 1

    third = generate_trend_explanation(
        session, meme_id=meme.id, data=TREND_DATA, data_version="v-cache-2", config=CONFIGURED
    )
    assert calls["n"] == 2
    assert third.data_version == "v-cache-2"


def test_force_refresh_bypasses_cache(session, meme_factory, monkeypatch):
    meme = meme_factory()
    calls = {"n": 0}
    real = _fake_completion("还在涨，参与的人越来越多。")

    def counting_chat(config, messages, **kwargs):
        calls["n"] += 1
        return real(config, messages, **kwargs)

    monkeypatch.setattr(service_module, "chat", counting_chat)
    generate_trend_explanation(session, meme_id=meme.id, data=TREND_DATA, data_version="v-force", config=CONFIGURED)
    generate_trend_explanation(
        session, meme_id=meme.id, data=TREND_DATA, data_version="v-force",
        config=CONFIGURED, force_refresh=True,
    )
    assert calls["n"] == 2


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw", [
    '{"status":"can_catch"}',
    '```json\n{"status":"can_catch"}\n```',
    '好的，结果如下：{"status":"can_catch"} 希望有帮助',
])
def test_json_extractor_tolerates_wrappers(raw):
    parsed = parse_json_object(raw)
    assert parsed and parsed["status"] == "can_catch"


def test_json_extractor_returns_none_on_garbage():
    assert parse_json_object("这完全不是 JSON") is None


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "abc")
    config = load_config()
    assert config.api_key == "abc" and config.is_configured
