"""数据管线接口（``/api/pipeline``）：结构完整、数字自洽、只读免令牌。

这个接口是给「数据管线」页看的，页面直接渲染它返回的每一条，所以这里钉两件事：
1. **五段结构一个都不能少**——少一段页面上就是一片空白；
2. **数字内部自洽**——真实数 ≤ 总数、讨论量 ≤ 互动量这种关系不该被写反。

口径关系写错时最不容易被发现（页面照样渲染，只是数字互相矛盾），所以专门测。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

SECTIONS = ("acquisition", "processing", "modeling", "quality", "ai")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:  # lifespan 会建表并灌演示数据
        yield test_client


def test_pipeline_returns_all_sections(client):
    response = client.get("/api/pipeline")
    assert response.status_code == 200
    body = response.json()
    for key in ("generated_at", "counts", "source", *SECTIONS):
        assert key in body, f"payload 缺少「{key}」段，页面会渲染成空白"


def test_each_section_has_renderable_content(client):
    """每段都要有可渲染的条目，否则页面只有标题没有内容。"""
    body = client.get("/api/pipeline").json()
    assert body["acquisition"]["steps"], "数据获取步骤为空"
    assert body["acquisition"]["params"], "采集参数为空"
    assert body["processing"]["steps"], "数据处理步骤为空"
    assert body["processing"]["derived"], "派生指标为空"
    assert body["modeling"]["items"], "分析建模条目为空"
    assert body["quality"]["checks"], "数据质量自查项为空"
    assert body["ai"]["boundaries"], "AI 边界说明为空"


def test_acquisition_numbers_are_consistent(client):
    body = client.get("/api/pipeline").json()
    acq = body["acquisition"]
    assert acq["video_real"] >= 0
    # 真实样本不可能多于总样本
    assert acq["video_total"] >= acq["video_real"]
    # 演示样本 = 总数 - 真实数，不能为负
    assert acq["video_demo"] == acq["video_total"] - acq["video_real"]
    assert acq["est_requests_total"] == acq["est_requests_daily"] + acq["est_requests_enrich"]
    assert acq["window_days"] > 0


def test_processing_numbers_are_consistent(client):
    body = client.get("/api/pipeline").json()
    proc = body["processing"]
    assert proc["observation_points"] >= proc["observed_points"] >= 0
    assert proc["unobserved_points"] == proc["observation_points"] - proc["observed_points"]
    assert proc["view_total"] >= 0
    assert proc["discussion_total"] >= 0
    # 派生指标不能出现两项数值完全相同——那通常说明口径重复计算了
    # （曾经把「互动量」与「讨论量」并列，而日序列里点赞/投币/收藏恒为 0，两者必然相等）
    values = [item["value"] for item in proc["derived"]]
    assert len(set(values)) == len(values) or all(v == 0 for v in values), (
        f"派生指标出现重复数值 {values}，检查口径是否重复计算"
    )


def test_quality_ratios_stay_in_range(client):
    """比例字段要么是 null（没有数据），要么落在 [0,1]——不能出现 1.02 这种数。"""
    body = client.get("/api/pipeline").json()
    quality = body["quality"]
    for key in ("demo_ratio", "missing_ratio", "observed_ratio"):
        value = quality.get(key)
        assert value is None or 0.0 <= value <= 1.0, f"{key}={value} 越界"


def test_source_flag_matches_demo_counts(client):
    """站点级「是否演示数据」要和实际样本构成对得上，不能自相矛盾。"""
    body = client.get("/api/pipeline").json()
    acq = body["acquisition"]
    if body["source"]["is_demo"]:
        assert acq["video_real"] == 0, "标着演示数据却混进了真实样本"
    else:
        assert acq["video_real"] > 0, "标着真实数据却一条真实样本都没有"


def test_pipeline_stays_public_with_token_configured(client, monkeypatch):
    """只读接口不受 ADMIN_TOKEN 影响：Web 与小程序都不该被令牌挡住。"""
    monkeypatch.setattr(settings, "admin_token", "test-token-0123456789")
    assert client.get("/api/pipeline").status_code == 200


def test_pipeline_payload_has_no_credentials(client):
    """画像页是公开的，payload 里不许出现凭据字段。"""
    text = client.get("/api/pipeline").text.lower()
    for leaked in ("api_key", "apikey", "admin_token", "password", "secret"):
        assert leaked not in text, f"payload 泄漏了「{leaked}」"
