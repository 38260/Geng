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


# --------------------------------------------------------------------------- #
# 热度公式：这是页面重点，也是全项目最容易"页面写一套、算法跑另一套"的地方
# --------------------------------------------------------------------------- #
def test_hotness_formula_is_complete(client):
    """五个分量齐全、权重合计为 1，且绝对量分量都带归一化区间。"""
    spec = client.get("/api/pipeline").json()["modeling"]["hotness"]
    assert spec["expression"].startswith("Hotness =")
    assert len(spec["terms"]) == 5
    assert abs(spec["weights_total"] - 1.0) < 1e-9, "权重合计必须为 1，否则总分到不了 100"
    assert {item["key"] for item in spec["terms"]} == {
        "view",
        "interaction",
        "content",
        "creator",
        "growth",
    }
    for item in spec["terms"]:
        if item["key"] == "growth":
            # 增长率是相对量，没有绝对量区间
            assert item["floor"] is None and item["ceiling"] is None
        else:
            assert item["floor"] is not None and item["ceiling"] is not None
            assert item["ceiling"] > item["floor"], f"{item['key']} 的区间上界必须大于下界"
    assert spec["normalization"]["formula"]
    assert spec["growth"]["score_formula"]
    assert spec["growth"]["rate_formula"]
    assert spec["damping"]["rules"]
    assert spec["notes"], "口径说明不能为空——页面靠这些说明"


def test_hotness_weights_come_from_algorithm_config(client):
    """页面上的权重与区间必须**现读**自算法配置，不能在前端/服务里另抄一份。"""
    from app.config import HOTNESS_REFERENCE, HOTNESS_WEIGHTS

    spec = client.get("/api/pipeline").json()["modeling"]["hotness"]
    by_key = {item["key"]: item for item in spec["terms"]}

    assert by_key["view"]["weight"] == HOTNESS_WEIGHTS.view
    assert by_key["interaction"]["weight"] == HOTNESS_WEIGHTS.interaction
    assert by_key["content"]["weight"] == HOTNESS_WEIGHTS.content
    assert by_key["creator"]["weight"] == HOTNESS_WEIGHTS.creator
    assert by_key["growth"]["weight"] == HOTNESS_WEIGHTS.growth

    for key in ("view", "interaction", "content", "creator"):
        assert (by_key[key]["floor"], by_key[key]["ceiling"]) == HOTNESS_REFERENCE[key]


def test_hotness_example_is_reconcilable(client):
    """算例要能对账：逐项「得分 × 权重 = 贡献」，求和等于快照总分。

    这条是给答辩兜底的——被问「权重是不是拍的」时，页面上的算例必须真的算得通。
    """
    spec = client.get("/api/pipeline").json()["modeling"]["hotness"]
    example = spec["example"]
    if example is None:
        pytest.skip("库里还没有热度快照，无法对账")

    for item in example["terms"]:
        expected = item["score"] * item["weight"]
        assert abs(expected - item["contribution"]) <= 0.01, (
            f"{item['key']} 的贡献 ≠ 得分 × 权重"
        )

    total = sum(item["contribution"] for item in example["terms"])
    assert abs(total - example["sum_of_contributions"]) <= 0.05
    # 快照把总分四舍五入到 0.1，所以留一点舍入余量
    assert abs(total - example["score"]) <= 0.15, "逐项求和与快照总分对不上"


def test_hotness_example_terms_are_not_duplicated(client):
    """算例里各分量的得分不应两两雷同——雷同通常说明两个分量算的是同一个东西。"""
    spec = client.get("/api/pipeline").json()["modeling"]["hotness"]
    example = spec["example"]
    if example is None:
        pytest.skip("库里还没有热度快照")

    scores = [item["score"] for item in example["terms"] if item["key"] != "growth"]
    assert len(set(scores)) == len(scores), f"绝对量分量得分出现重复 {scores}，检查口径"

