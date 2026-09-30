"""梗的分类：主题标签（LLM 打标）与算法专题（规则现算）。

这个功能最容易出的问题不是「崩了」，而是**数对不上**：
筛选行写着 74、点进去只有 46，或者标签清单里挂着一排点进去没结果的死标签。
所以下面重点测**一致性**，而不是只测「接口返回 200」。

模型输出那一侧同样要钉死：它只能从固定清单里挑，清单外的必须被丢掉——
标签一旦碎掉（「打工人」「职场」「牛马」各算一个），筛选就失去意义了。
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import (
    COLLECTION_KEYS,
    FALLBACK_TAG,
    MAX_TAGS_PER_MEME,
    MEME_TAGS,
    TAG_KEYS,
)
from app.main import app
from app.services.meme.collections import collection_labels
from app.services.meme.tagging import parse_response


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:  # lifespan 会建表并灌演示数据
        yield test_client


# --------------------------------------------------------------------------- #
# 清单本身要自洽
# --------------------------------------------------------------------------- #
def test_tag_keys_are_unique_and_complete():
    keys = [tag.key for tag in MEME_TAGS]
    assert len(keys) == len(set(keys)), "标签 key 有重复"
    assert set(TAG_KEYS) == set(keys)
    # 兜底标签必须在清单里，否则「一个都没选中」时会写出一个越界的值
    assert FALLBACK_TAG in TAG_KEYS
    for tag in MEME_TAGS:
        assert tag.label and tag.emoji and tag.hint, f"{tag.key} 少了展示信息"


def test_collection_labels_render_current_period():
    labels = collection_labels()
    for key in COLLECTION_KEYS:
        assert key in labels and labels[key], f"{key} 没有可展示的名字"


# --------------------------------------------------------------------------- #
# 模型输出必须被压回固定清单
# --------------------------------------------------------------------------- #
def test_parse_keeps_only_known_tags():
    result = parse_response('{"tags": ["workplace", "不存在的标签"], "reason": "x"}')
    assert result["ok"] is True
    assert result["tags"] == ["workplace"]
    assert result["dropped"] == ["不存在的标签"]


def test_parse_truncates_to_max():
    result = parse_response(json.dumps({"tags": list(TAG_KEYS)}))
    assert result["ok"] is True
    assert len(result["tags"]) == MAX_TAGS_PER_MEME


def test_parse_dedupes():
    result = parse_response('{"tags": ["animal", "animal"]}')
    assert result["tags"] == ["animal"]


def test_parse_falls_back_to_other_when_nothing_valid():
    """全是清单外的值 → 落「其他」，而不是返回空。空表示"没标过"，是另一回事。"""
    result = parse_response('{"tags": ["bogus1", "bogus2"]}')
    assert result["ok"] is True
    assert result["tags"] == [FALLBACK_TAG]
    assert len(result["dropped"]) == 2


def test_parse_falls_back_on_empty_list():
    result = parse_response('{"tags": []}')
    assert result["ok"] is True
    assert result["tags"] == [FALLBACK_TAG]


def test_parse_rejects_non_json():
    """模型只会在正文为空时才吐出思考过程，那不是 JSON，必须如实报错。"""
    result = parse_response("我想了想，这个梗讲的应该是上班族的疲惫感，所以属于职场类。")
    assert result["ok"] is False
    assert result["tags"] == []
    assert "JSON" in result["reason"]


def test_parse_extracts_answer_from_reasoning_text():
    """带思考段的模型常把正文 token 全花在 reasoning 上（实测 reasoning 能到 1500 字、
    正文一个字不剩），答案就混在思考里。这时候必须能把它抠出来。

    注意取**最后一次**出现：思考途中往往先写草稿，最后的才是结论。
    """
    reasoning = (
        "我先想想这个梗在讲什么。它说的是上班很累，像职场话题。\n"
        '草稿：{"tags": ["workplace"], "reason": "讲上班"}\n'
        "不过视频里也有很多沙雕整活，应该再补一个。\n"
        '结论：{"tags": ["workplace", "abstract"], "reason": "职场疲惫 + 整活"}'
    )
    result = parse_response(reasoning)
    assert result["ok"] is True
    assert result["tags"] == ["workplace", "abstract"], "应取思考末尾的结论，而不是草稿"


def test_parse_survives_truncated_json():
    """输出被 max_tokens 截断时，只要 tags 部分是完整的就还能用。"""
    result = parse_response('...思考...结论是 {"tags": ["music"], "reason": "洗脑 BGM，输出被')
    assert result["ok"] is True
    assert result["tags"] == ["music"]


def test_parse_handles_markdown_fence():
    result = parse_response('```json\n{"tags": ["animal"]}\n```')
    assert result["ok"] is True
    assert result["tags"] == ["animal"]


# --------------------------------------------------------------------------- #
# 接口：清单与筛选必须对得上
# --------------------------------------------------------------------------- #
def test_meta_exposes_classification_lists(client):
    meta = client.get("/api/meta").json()
    assert "collections" in meta and "tags" in meta
    assert {item["key"] for item in meta["collections"]} == set(COLLECTION_KEYS)
    for item in meta["collections"]:
        assert item["label"] and item["emoji"] and item["description"]
        assert item["count"] >= 0


def test_collection_count_matches_list(client):
    """筛选行上的数字必须等于点进去看到的条数——这是本功能最容易出错的地方。"""
    meta = client.get("/api/meta").json()
    for item in meta["collections"]:
        listed = client.get(f"/api/memes?collection={item['key']}&scope=all&limit=100").json()
        assert item["count"] == len(listed["items"]), (
            f"「{item['label']}」计数 {item['count']} 与列表 {len(listed['items'])} 不一致"
        )


def test_tag_count_matches_list(client):
    """标签清单的计数同理。一个梗都还没打标时清单为空，循环自然跳过。"""
    meta = client.get("/api/meta").json()
    for item in meta["tags"]:
        listed = client.get(f"/api/memes?tag={item['key']}&scope=all&limit=100").json()
        assert item["count"] == len(listed["items"]), (
            f"标签「{item['label']}」计数 {item['count']} 与列表 {len(listed['items'])} 不一致"
        )


def test_unknown_tag_and_collection_are_rejected(client):
    """写错的参数要给 400，不能静默返回空列表——
    静默返回空会让人以为「这个标签下没有梗」，其实是参数写错了。"""
    assert client.get("/api/memes?tag=不存在的标签").status_code == 400
    assert client.get("/api/memes?collection=nope").status_code == 400


def test_tag_filter_actually_filters(client):
    """选一个真实存在的标签，结果必须都带这个标签。"""
    meta = client.get("/api/meta").json()
    if not meta["tags"]:
        pytest.skip("库里还没有打过标的梗")
    tag = meta["tags"][0]["key"]
    listed = client.get(f"/api/memes?tag={tag}&scope=all&limit=100").json()
    for item in listed["items"]:
        assert tag in item["tags"], f"{item['name']} 不该出现在标签 {tag} 的结果里"


def test_collection_and_lifecycle_stack(client):
    """专题与生命周期筛选是可叠加的：叠加后的条数不该超过专题本身。"""
    meta = client.get("/api/meta").json()
    for item in meta["collections"]:
        base = client.get(f"/api/memes?collection={item['key']}&scope=all&limit=100").json()
        for stage_filter in ("hot", "taking_off", "receding"):
            narrowed = client.get(
                f"/api/memes?collection={item['key']}&filter={stage_filter}&scope=all&limit=100"
            ).json()
            assert len(narrowed["items"]) <= len(base["items"])


def test_cards_carry_tags_field(client):
    data = client.get("/api/memes?scope=all&limit=5").json()
    assert data["items"], "测试库里应该有梗"
    for item in data["items"]:
        assert "tags" in item
        assert isinstance(item["tags"], list)
