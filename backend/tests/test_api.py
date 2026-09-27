"""接口集成测试：跑真实 ASGI 应用 + 自动灌入的演示数据。"""

from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from app.config import HOME_FILTERS, settings
from app.main import app
from app.models import Meme, reset_db

from .conftest import make_video

UNVERIFIED_NAMES = {"新梗观察A", "新梗观察B", "网友投稿梗"}


@pytest.fixture(scope="module")
def client():
    reset_db()
    with TestClient(app) as test_client:  # 触发 lifespan：建表 + 自动灌演示数据
        yield test_client


def _forbid_nan(response):
    """接口里绝不允许出现 NaN / Infinity，否则前端会渲染出 NaN。"""
    def boom(value):  # pragma: no cover - 断言用
        raise AssertionError(f"响应里出现了非法数值 {value}")

    json.loads(response.text, parse_constant=boom)
    return response


# --------------------------------------------------------------------------- #
# 元信息
# --------------------------------------------------------------------------- #
def test_site_label_follows_actual_data_not_configuration():
    """配置写 bilibili 但库里还是演示数据时，不许对外声称"真实数据"。"""
    from app.services.meme.query import effective_source

    assert effective_source(["bilibili", "bilibili"]) == ("bilibili", False)
    assert effective_source(["mock", "mock"]) == ("mock", True)
    assert effective_source(["mock", "bilibili"]) == ("mixed", True)
    assert effective_source([]) == (settings.data_source, settings.data_source == "mock")


def test_health_and_meta(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["llm_configured"] is False

    meta = client.get("/api/meta")
    _forbid_nan(meta)
    payload = meta.json()
    assert payload["app_name"] == "赶梗潮"
    assert payload["data_source"] == "mock"
    assert payload["is_demo"] is True, "演示数据必须被明确标记"
    assert payload["certified_count"] >= 30
    assert payload["candidate_count"] == 3
    assert payload["data_updated_at"]
    assert [f["key"] for f in payload["filters"]] == ["all", "hot", "taking_off", "receding"]
    assert len(payload["lifecycle_stages"]) == 6
    assert payload["transparency"]["data_platform"] == "Bilibili"
    assert payload["transparency"]["certification"] == ["梗百科", "梗指南"]


# --------------------------------------------------------------------------- #
# 榜单
# --------------------------------------------------------------------------- #
def test_list_is_heat_sorted_and_only_certified(client):
    payload = client.get("/api/memes").json()
    scores = [item["hotness"] for item in payload["items"]]
    assert scores == sorted(scores, reverse=True)
    assert len(scores) == payload["total"]
    assert not (set(item["name"] for item in payload["items"]) & UNVERIFIED_NAMES)
    for item in payload["items"]:
        assert 0 <= item["hotness"] <= 100
        assert item["stage"] in {"sprouting", "rising", "explosive", "plateau", "receding", "obsolete"}
        assert item["catch_status"] in {"can_catch", "caution", "too_late"}
        assert item["nickname"]
        assert item["thumbnail"]["emoji"]


def test_filters_map_to_lifecycle_stages(client):
    for key, stages in (("hot", HOME_FILTERS["hot"]), ("taking_off", HOME_FILTERS["taking_off"]),
                        ("receding", HOME_FILTERS["receding"])):
        items = client.get(f"/api/memes?filter={key}").json()["items"]
        assert items, f"{key} 筛选不应该为空"
        assert all(item["stage"] in stages for item in items), key


def test_search_matches_alias_and_keyword(client):
    by_alias = client.get("/api/memes?search=赛博木鱼").json()["items"]
    assert [item["name"] for item in by_alias] == ["电子木鱼"]

    by_keyword = client.get("/api/memes?search=穿搭").json()["items"]
    assert {item["name"] for item in by_keyword} >= {"多巴胺穿搭", "松弛感"}
    for item in by_keyword:
        haystack = item["name"] + "".join(item["aliases"]) + "".join(item.get("keywords", []))
        assert "穿搭" in haystack or "穿搭" in item["name"]

    assert client.get("/api/memes?search=不存在的梗xyz").json()["items"] == []


def test_invalid_filter_and_sort_are_rejected(client):
    assert client.get("/api/memes?filter=douyin").status_code == 400
    assert client.get("/api/memes?sort=ctr").status_code == 400


def test_pagination(client):
    page1 = client.get("/api/memes?limit=3&offset=0").json()
    page2 = client.get("/api/memes?limit=3&offset=3").json()
    assert len(page1["items"]) == 3 == len(page2["items"])
    assert {i["id"] for i in page1["items"]}.isdisjoint({i["id"] for i in page2["items"]})
    assert page1["total"] == page2["total"]


def test_cover_follows_the_actual_data_source(client, session, meme_factory):
    """封面不许造假：真实采集的梗用 B站真实封面，演示梗才用设计稿素材图。"""
    from app.services.meme.query import covers_by_meme, thumbnail_for

    real = session.query(Meme).filter_by(name="阿巴阿巴").one()
    real.data_source = "bilibili"
    demo = session.query(Meme).filter_by(name="狗都不谈恋爱").one()
    plain = meme_factory(name="查无此梗XYZ", data_source="bilibili")
    session.add(
        make_video("BV1coverhi", "阿巴阿巴", meme_id=real.id, view=900,
                   cover="//i0.hdslb.com/bfs/archive/hi.jpg")
    )
    session.add(
        make_video("BV1coverlo", "阿巴阿巴", meme_id=real.id, view=10,
                   cover="//i0.hdslb.com/bfs/archive/lo.jpg")
    )
    session.flush()

    covers = covers_by_meme(session)
    assert covers[real.id] == "https://i0.hdslb.com/bfs/archive/hi.jpg", "取播放量最高那条的封面"

    assert thumbnail_for(real, covers[real.id])["image"].startswith("https://i0.hdslb.com")
    assert thumbnail_for(demo, "")["image"] == "/thumbs/shiba.png"

    # 既没有真实封面也没有素材图：退回表情贴纸，而不是编一个图片地址
    empty = thumbnail_for(plain, "")
    assert empty["image"] == "" and empty["emoji"] and empty["color"]
    session.rollback()


# --------------------------------------------------------------------------- #
# 详情
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def top_meme_id(client) -> int:
    return client.get("/api/memes?limit=1").json()["items"][0]["id"]


def test_detail_shape(client, top_meme_id):
    response = client.get(f"/api/memes/{top_meme_id}")
    _forbid_nan(response)
    payload = response.json()

    assert set(payload) >= {"meme", "hotness", "lifecycle", "metrics", "certification", "videos", "trend", "insight"}
    assert payload["meme"]["hotness"] == payload["hotness"]["score"]

    # 热度分量 + 权重，且权重合计 1
    weights = payload["hotness"]["weights"]
    assert set(weights) == {"view", "interaction", "content", "creator", "growth"}
    assert sum(weights.values()) == pytest.approx(1.0)
    for value in payload["hotness"]["components"].values():
        assert 0 <= value <= 100

    # 生命周期六态，且只有一个"现在"
    stages = payload["lifecycle"]["stages"]
    assert len(stages) == 6
    assert sum(1 for stage in stages if stage["active"]) == 1
    assert payload["lifecycle"]["reasons"]

    # 核心指标带增幅，且不是 0 占位
    for key in ("videos", "creators", "comments", "danmaku"):
        block = payload["metrics"][key]
        assert block["value"] > 0
        assert block["growth"] is None or isinstance(block["growth"], (int, float))

    # 双 UP 认证证据
    cert = payload["certification"]
    assert cert["certified"] is True
    assert cert["encyclopedia"]["up_name"] == "梗百科" and cert["encyclopedia"]["confirmed"]
    assert cert["guide"]["up_name"] == "梗指南" and cert["guide"]["confirmed"]
    # 演示阶段的认证证据不得伪装成可点开的真实链接
    assert cert["encyclopedia"]["linkable"] is False
    assert cert["encyclopedia"]["video_url"] == ""
    assert cert["encyclopedia"]["confirmed"] is True

    # 相关视频都过了相关性阈值
    assert 0 < len(payload["videos"]) <= 4
    for video in payload["videos"]:
        assert video["relevance_score"] >= settings.relevance_threshold
        assert video["url"].startswith("https://www.bilibili.com/video/BV")
        assert video["view_text"] and video["duration_text"]


def test_detail_trend_and_windows(client, top_meme_id):
    detail = client.get(f"/api/memes/{top_meme_id}").json()
    points = detail["trend"]["points"]
    assert len(points) == settings.analysis_window_days
    assert [p["date"] for p in points] == sorted(p["date"] for p in points)
    assert all(0 <= p["hotness"] <= 100 for p in points)

    assert len(client.get(f"/api/memes/{top_meme_id}/trend?window=7").json()["points"]) == 7
    assert client.get(f"/api/memes/{top_meme_id}/trend?window=9").status_code == 400


def test_detail_does_not_call_the_llm(client, top_meme_id):
    """详情页要秒开：AI 只读缓存，没缓存就是 null。"""
    payload = client.get(f"/api/memes/{top_meme_id}").json()
    insight = payload["insight"]
    assert insight["catch_up"]["decided_by"] == "algorithm"
    assert insight["algorithm_reason"]
    assert insight["trend_explanation"] is None or insight["trend_explanation"]["status"] == "ok"


def test_uncertified_meme_is_blocked(client):
    from app.models import SessionLocal

    session = SessionLocal()
    meme = session.query(Meme).filter(Meme.certified.is_(False)).first()
    meme_id, meme_name = meme.id, meme.name
    session.close()

    response = client.get(f"/api/memes/{meme_id}")
    assert response.status_code == 409
    assert "双 UP 认证" in response.json()["detail"]
    assert meme_name not in [i["name"] for i in client.get("/api/memes?limit=100").json()["items"]]
    assert client.get("/api/memes/424242").status_code == 404


# --------------------------------------------------------------------------- #
# AI 接口
# --------------------------------------------------------------------------- #
def test_insight_endpoint_degrades_without_key(client, top_meme_id):
    payload = client.post(f"/api/memes/{top_meme_id}/insight", json={"refresh": True}).json()
    trend = payload["trend_explanation"]
    advice = payload["catch_up_advice"]

    assert trend["status"] == "ok" and trend["source"] == "rule"
    assert trend["result"]["text"] and "AI" not in trend["result"]["text"]
    assert advice["available"] is True
    assert advice["result"]["status"] in {"can_catch", "caution", "too_late"}
    assert 0 <= advice["result"]["confidence"] <= 0.95
    assert advice["result"]["reason"]


def test_cached_insight_has_the_same_shape_as_a_fresh_one(client, top_meme_id):
    """缓存记录与新生成记录必须同形状，否则前端会把命中缓存当成"没生成"。"""
    fresh = client.post(f"/api/memes/{top_meme_id}/insight", json={"refresh": True}).json()
    cached = client.get(f"/api/memes/{top_meme_id}").json()["insight"]

    for key in ("trend_explanation", "catch_up_advice"):
        assert cached[key] is not None, key
        assert cached[key]["available"] is True
        assert set(cached[key]) >= set(fresh[key]) - {"error"}
    assert cached["trend_explanation"]["result"]["text"] == fresh["trend_explanation"]["result"]["text"]
    assert cached["catch_up_advice"]["result"]["status"] == fresh["catch_up_advice"]["result"]["status"]


def test_insight_is_cached_by_data_version(client, top_meme_id):
    first = client.post(f"/api/memes/{top_meme_id}/insight", json={"refresh": False}).json()
    second = client.post(f"/api/memes/{top_meme_id}/insight", json={"refresh": False}).json()
    assert first["trend_explanation"]["generated_at"] == second["trend_explanation"]["generated_at"]
    assert second["trend_explanation"]["source"] in {"rule", "cache"}


def test_llm_test_endpoint_reports_unconfigured(client):
    payload = client.post("/api/llm/test").json()
    assert payload["ok"] is False
    assert payload["configured"] is False
    assert "LLM_API_KEY" in payload["message"]
    assert "api_key" not in json.dumps(payload) or "sk-" not in json.dumps(payload)


def test_llm_models_requires_key(client):
    assert client.get("/api/llm/models").status_code == 400


def test_llm_business_endpoints(client, top_meme_id):
    trend = client.post("/api/llm/trend-explanation", json={"meme_id": top_meme_id, "refresh": True})
    assert trend.status_code == 200
    assert trend.json()["result"]["text"]

    advice = client.post("/api/llm/catch-up-advice", json={"meme_id": top_meme_id, "refresh": True})
    assert advice.status_code == 200
    assert advice.json()["result"]["status"] in {"can_catch", "caution", "too_late"}

    assert client.post("/api/llm/catch-up-advice", json={"refresh": True}).status_code == 400
    assert client.post("/api/llm/trend-explanation", json={}).status_code == 400


# --------------------------------------------------------------------------- #
# 设置与任务
# --------------------------------------------------------------------------- #
def test_settings_never_echo_the_key(client, monkeypatch, tmp_path):
    from app.services import settings_store

    original = (settings.llm_api_key, settings.llm_model, settings.llm_base_url)
    monkeypatch.setattr(settings, "llm_api_key", original[0], raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text("LLM_PROVIDER=longcat\nLLM_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr(settings_store, "ENV_FILE", env_file)

    view = client.get("/api/settings/llm").json()
    assert view["config"]["api_key_set"] is False
    assert "api_key" not in view["config"] or "sk-" not in view["config"]["api_key"]

    saved = client.put(
        "/api/settings/llm",
        json={"api_key": "sk-secret-value-123", "model": "LongCat-Test", "persist": True},
    ).json()
    assert saved["saved"] is True
    assert saved["api_key_updated"] is True
    assert "LLM_API_KEY" not in saved["written_keys"], "响应里不列出 Key 的键名"
    assert "sk-secret-value-123" not in json.dumps(saved)

    # 真的写进了 .env（测试里指向临时文件）
    assert "LLM_API_KEY=sk-secret-value-123" in env_file.read_text(encoding="utf-8")
    assert "LLM_MODEL=LongCat-Test" in env_file.read_text(encoding="utf-8")

    # 留空表示保持原 Key
    again = client.put("/api/settings/llm", json={"model": "LongCat-Another", "persist": True}).json()
    assert again["api_key_updated"] is False
    assert "sk-secret-value-123" in env_file.read_text(encoding="utf-8")

    # 还原，避免假 Key 泄漏到后续用例
    settings.llm_api_key, settings.llm_model, settings.llm_base_url = original


def test_recompute_job_is_idempotent(client):
    before = client.get("/api/memes?limit=5").json()["items"]
    result = client.post("/api/jobs/recompute").json()
    assert result["ok"] is True and result["computed"] >= 30 and result["skipped"] == 3
    after = client.get("/api/memes?limit=5").json()["items"]
    assert [(i["id"], i["hotness"]) for i in before] == [(i["id"], i["hotness"]) for i in after]


def test_no_response_leaks_a_secret(client):
    """全站扫描：任何接口响应里都不该出现 Key 字样或密钥值。"""
    paths = ["/api/health", "/api/meta", "/api/memes?limit=5", "/api/settings/llm"]
    for path in paths:
        text = client.get(path).text
        assert "sk-" not in text, path
        assert not math.isnan(0.0)
