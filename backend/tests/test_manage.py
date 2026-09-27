"""梗管理：人工只能改展示与检索字段，改不到算法结论。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models import HotnessSnapshot, LifecycleSnapshot, Meme, Video, reset_db
from app.services.meme.query import thumbnail_for

from .conftest import make_video

BAD_COVERS = ["javascript:alert(1)", "data:image/png;base64,AA", "not-a-url", "C:/x.png"]


@pytest.fixture(scope="module")
def client():
    reset_db()
    with TestClient(app) as test_client:  # lifespan 会建表并灌演示数据
        yield test_client


def _session():
    from app.models import SessionLocal

    return SessionLocal()


# --------------------------------------------------------------------------- #
# 接口
# --------------------------------------------------------------------------- #
def test_manage_list_covers_candidates_too(client):
    """公开榜单只给正式梗，管理列表必须连候选梗一起给（否则候选梗没法补介绍）。"""
    public = {item["name"] for item in client.get("/api/memes?limit=100").json()["items"]}
    managed = client.get("/api/manage/memes").json()
    names = {item["name"] for item in managed["items"]}

    assert public <= names
    assert managed["candidate_count"] >= 3
    assert any(not item["certified"] for item in managed["items"])


def test_read_manage_view_and_cover_options(client):
    meme_id = client.get("/api/memes?limit=1").json()["items"][0]["id"]
    view = client.get(f"/api/manage/memes/{meme_id}").json()

    assert view["id"] == meme_id
    assert {"description", "aliases", "keywords", "cover_url", "auto_cover", "cover_options"} <= set(view)
    assert view["cover_url"] == "", "新库里不该有人工封面"
    # 演示数据没有真实封面，可选项就应该是空的，而不是拿素材图凑数
    assert view["cover_options"] == []
    assert "不会改动已算好的热度" in view["note"]

    # 采信样本：让人能抽查"这个梗的分数到底是哪些视频撑起来的"
    samples = view["sample_videos"]
    assert samples["accepted"] >= 1 and samples["items"]
    assert any(item["relevance_score"] > 0 for item in samples["items"]), "分数得是真算出来的，不是一片 0"
    assert all(item["url"] for item in samples["items"])


def test_patch_updates_only_metadata(client):
    meme_id = client.get("/api/memes?limit=1").json()["items"][0]["id"]
    before = client.get("/api/memes?limit=100").json()["items"]
    snap_before = _snapshot(client, meme_id)

    saved = client.patch(
        f"/api/manage/memes/{meme_id}",
        json={
            "description": "人工补充的介绍",
            "aliases": ["赛博木鱼", "电子功德", "赛博木鱼", "  "],
            "keywords": ["解压", "功德"],
        },
    ).json()

    assert saved["changed"] == ["description", "aliases", "keywords"]
    assert saved["meme"]["description"] == "人工补充的介绍"
    assert saved["meme"]["aliases"] == ["赛博木鱼", "电子功德"], "去重去空白，顺序保持"
    assert saved["meme"]["keywords"] == ["解压", "功德"]

    # 热度、阶段、榜单顺序一个字都不该动
    assert _snapshot(client, meme_id) == snap_before
    after = client.get("/api/memes?limit=100").json()["items"]
    assert [(i["id"], i["hotness"], i["stage"]) for i in before] == [
        (i["id"], i["hotness"], i["stage"]) for i in after
    ]


def test_manual_cover_wins_and_is_flagged(client):
    item = client.get("/api/memes?limit=1").json()["items"][0]
    meme_id = item["id"]

    client.patch(f"/api/manage/memes/{meme_id}", json={"cover_url": "/thumbs/muyu.png"})
    card = client.get(f"/api/manage/memes/{meme_id}").json()
    assert card["effective_cover"] == "/thumbs/muyu.png"
    assert client.get("/api/manage/memes").json()["managed_count"] == 1

    shown = client.get("/api/memes?limit=100").json()["items"]
    mine = next(item for item in shown if item["id"] == meme_id)
    assert mine["thumbnail"]["image"] == "/thumbs/muyu.png"
    assert mine["thumbnail"]["manual"] is True

    # 恢复自动：人工地址清空后退回原来的取值链
    client.patch(f"/api/manage/memes/{meme_id}", json={"cover_url": ""})
    back = client.get(f"/api/memes?limit=100").json()["items"]
    restored = next(item for item in back if item["id"] == meme_id)
    assert restored["thumbnail"]["manual"] is False


def test_cover_url_normalised_to_https(client):
    meme_id = client.get("/api/memes?limit=1").json()["items"][0]["id"]
    client.patch(f"/api/manage/memes/{meme_id}", json={"cover_url": "//i0.hdslb.com/bfs/archive/a.jpg"})
    view = client.get(f"/api/manage/memes/{meme_id}").json()
    assert view["cover_url"] == "https://i0.hdslb.com/bfs/archive/a.jpg"
    client.patch(f"/api/manage/memes/{meme_id}", json={"cover_url": ""})


@pytest.mark.parametrize("cover", BAD_COVERS)
def test_rejects_unusable_cover_urls(client, cover):
    meme_id = client.get("/api/memes?limit=1").json()["items"][0]["id"]
    assert client.patch(f"/api/manage/memes/{meme_id}", json={"cover_url": cover}).status_code == 400


def test_rejects_oversized_and_unknown_fields(client):
    meme_id = client.get("/api/memes?limit=1").json()["items"][0]["id"]

    assert client.patch(f"/api/manage/memes/{meme_id}", json={}).status_code == 400
    assert client.patch(f"/api/manage/memes/{meme_id}", json={"hotness": 99}).status_code == 400
    assert client.patch(f"/api/manage/memes/{meme_id}", json={"certified": True}).status_code == 400
    assert (
        client.patch(f"/api/manage/memes/{meme_id}", json={"keywords": [f"k{i}" for i in range(13)]}).status_code
        == 400
    )
    assert client.patch(f"/api/manage/memes/{meme_id}", json={"aliases": ["超" * 21]}).status_code == 400
    assert client.patch(f"/api/manage/memes/{meme_id}", json={"description": "字" * 601}).status_code == 400
    assert client.patch("/api/manage/memes/999999", json={"description": "x"}).status_code == 404


def test_out_of_pool_meme_is_manageable(client):
    """两位 UP 都没介绍过的梗没进榜单，但介绍和封面照样要能补。"""
    db = _session()
    try:
        candidate = db.query(Meme).filter(
            Meme.encyclopedia_confirmed.is_(False), Meme.guide_confirmed.is_(False)
        ).first()
        assert candidate is not None
        meme_id = candidate.id
    finally:
        db.close()

    assert client.get(f"/api/memes/{meme_id}").status_code == 409
    saved = client.patch(f"/api/manage/memes/{meme_id}", json={"description": "候选阶段先写个介绍"})
    assert saved.status_code == 200
    assert saved.json()["meme"]["description"] == "候选阶段先写个介绍"


def test_manage_list_labels_certification_strength(client):
    """管理列表要能一眼看出"缺哪一边"，不然运营只会看到一片"未认证"。"""
    managed = client.get("/api/manage/memes").json()
    by_name = {item["name"]: item for item in managed["items"]}

    assert by_name["新梗观察A"]["cert_label"] == "梗百科认证"
    assert by_name["新梗观察A"]["admitted"] is True
    assert by_name["新梗观察A"]["certified"] is False
    assert by_name["新梗观察B"]["certified_by"] == ["梗指南"]
    assert by_name["网友投稿梗"]["admitted"] is False
    assert by_name["网友投稿梗"]["cert_label"] == "未认证"
    assert managed["in_pool_count"] == managed["total"] - managed["out_of_pool_count"]
    assert managed["cert_window_days"] == 90


# --------------------------------------------------------------------------- #
# 服务层
# --------------------------------------------------------------------------- #
def test_thumbnail_priority_is_manual_then_real_then_demo():
    db = _session()
    try:
        real = db.query(Meme).filter_by(name="阿巴阿巴").one()
        real.cover_url = ""
        assert thumbnail_for(real, "https://i0.hdslb.com/x.jpg")["image"] == "https://i0.hdslb.com/x.jpg"

        real.cover_url = "/thumbs/tom.png"
        picked = thumbnail_for(real, "https://i0.hdslb.com/x.jpg")
        assert picked["image"] == "/thumbs/tom.png" and picked["manual"] is True
        real.cover_url = ""

        demo = db.query(Meme).filter_by(name="狗都不谈恋爱").one()
        assert thumbnail_for(demo, "")["image"] == "/thumbs/shiba.png"
        assert thumbnail_for(demo, "")["manual"] is False
        db.rollback()
    finally:
        db.close()


def test_cover_options_only_list_real_deduped_covers(client):
    db = _session()
    try:
        meme = db.query(Meme).filter_by(name="阿巴阿巴").one()
        db.add(make_video("BV1opt1", "阿巴阿巴 合集", meme_id=meme.id, view=900,
                          cover="//i0.hdslb.com/bfs/archive/one.jpg"))
        db.add(make_video("BV1opt2", "阿巴阿巴 重复封面", meme_id=meme.id, view=10,
                          cover="//i0.hdslb.com/bfs/archive/one.jpg"))
        db.add(make_video("BV1opt3", "阿巴阿巴 低播放", meme_id=meme.id, view=500,
                          cover="//i2.hdslb.com/bfs/archive/two.jpg"))
        db.add(make_video("BV1opt4", "阿巴阿巴 没封面", meme_id=meme.id, view=9999, cover=""))
        db.commit()
        meme_id = meme.id
    finally:
        db.close()

    options = client.get(f"/api/manage/memes/{meme_id}").json()["cover_options"]
    assert [option["cover"] for option in options] == [
        "https://i0.hdslb.com/bfs/archive/one.jpg",
        "https://i2.hdslb.com/bfs/archive/two.jpg",
    ], "按播放量排序、去重、跳过没有封面的视频"

    db = _session()
    try:
        db.query(Video).filter(Video.bvid.in_(["BV1opt1", "BV1opt2", "BV1opt3", "BV1opt4"])).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def test_bad_cover_raises_http_400_from_service():
    from app.services.meme import manage

    with pytest.raises(HTTPException) as err:
        manage._clean_image("javascript:alert(1)")
    assert err.value.status_code == 400


def _snapshot(client, meme_id: int) -> tuple:
    db = _session()
    try:
        hotness = db.get(HotnessSnapshot, meme_id)
        lifecycle = db.get(LifecycleSnapshot, meme_id)
        return (
            hotness.score,
            tuple(sorted((hotness.components or {}).items())),
            lifecycle.stage,
            lifecycle.catch_status,
            round(lifecycle.catch_confidence, 4),
        )
    finally:
        db.close()


def test_create_meme_is_candidate_and_stays_gated(client):
    """手动新增的梗能进库、能被度量，但未通过发现层准入就不该上榜单。"""
    created = client.post(
        "/api/manage/memes",
        json={"name": "临时新增梗", "description": "先记一笔", "aliases": ["临时梗"], "keywords": ["测试"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["created"] is True
    meme = body["meme"]
    assert meme["status"] == "candidate" and meme["certified"] is False
    assert meme["data_source"] == "pending", "新梗还没数据，不该被标成演示或真实数据"
    assert meme["sample_videos"]["accepted"] == 0

    assert client.post("/api/manage/memes", json={"name": "临时新增梗"}).status_code == 409
    assert client.post("/api/manage/memes", json={"name": "超长名字".join("梗" * 25)}).status_code in (400, 422)

    public = {item["name"] for item in client.get("/api/memes?limit=100").json()["items"]}
    assert "临时新增梗" not in public, "未入池的梗不能出现在榜单"
    managed = client.get("/api/manage/memes?status=candidate").json()
    assert "临时新增梗" in {item["name"] for item in managed["items"]}

    from app.models import Meme, SessionLocal

    db = SessionLocal()
    try:
        db.query(Meme).filter(Meme.id == meme["id"]).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_collect_covers_candidates_so_manual_memes_get_measured(monkeypatch):
    """闸门管榜单，不管采集：候选梗也要能拿到真实序列。"""
    from app.collectors.base import CollectedBundle
    from app.services.pipeline import collect_all

    seen: list[tuple[int, str]] = []

    class Recorder:
        source = "bilibili"

        def is_available(self):
            return True, "ok"

        def collect(self, meme, *, window_days=30):
            seen.append((meme.id, meme.status))
            return CollectedBundle(daily_stats=[], videos=[])

    monkeypatch.setattr("app.collectors.make_collector", lambda _source: Recorder())

    collect_all("bilibili", window_days=30, include_candidates=True)
    with_candidates = {status for _, status in seen}
    seen.clear()
    collect_all("bilibili", window_days=30, include_candidates=False)
    only_certified = {status for _, status in seen}

    assert "candidate" in with_candidates
    assert only_certified == {"certified"}
