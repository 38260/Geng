"""接口集成测试：跑真实 ASGI 应用 + 自动灌入的演示数据。"""

from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from app.config import HOME_FILTERS, settings
from app.main import app
from app.models import Meme, SessionLocal, VideoTranscript, reset_db

from .conftest import make_video

# 两位 UP 主都没介绍过 → 未通过发现层准入，不得出现在榜单/详情
OUT_OF_POOL_NAMES = {"网友投稿梗"}
# 只有一位介绍过 → 并集准入通过，照样上榜，但标签必须写清是哪一位
SINGLE_UP_NAMES = {"新梗观察A", "新梗观察B"}


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
    # 热榜还要过"活着"门槛，所以榜上数会比梗库总数小，两个都得报出来
    assert payload["certified_count"] >= 25
    assert payload["library_count"] >= 30
    assert payload["gated_out"] >= 1
    assert "过气" in payload["transparency"]["board_gate"]
    # 候选 = 两位 UP 都没介绍过的（并集准入之外）；只有一位做过的已经算入池
    assert payload["candidate_count"] == 1
    assert payload["transparency"]["cert_window_days"] == 90
    assert "并集" in payload["transparency"]["certification_rule"]
    assert payload["data_updated_at"]
    # 新鲜度必须可机读：统计截至哪天、离今天几天，前端据此写"数据截至"
    assert payload["data_through"] and len(payload["data_through"]) == 10
    assert payload["data_lag_days"] >= 0
    assert "不含今天" in payload["transparency"]["sampling"] or payload["is_demo"]
    assert [f["key"] for f in payload["filters"]] == ["all", "hot", "taking_off", "receding"]
    # 六个真实阶段 + 一个「数据不足」闸门态
    assert len(payload["lifecycle_stages"]) == 7
    assert payload["transparency"]["data_platform"] == "Bilibili"
    assert payload["transparency"]["certification"] == ["梗百科", "梗指南"]


# --------------------------------------------------------------------------- #
# 榜单
# --------------------------------------------------------------------------- #
def test_list_is_heat_sorted_and_only_admitted(client):
    payload = client.get("/api/memes").json()
    scores = [item["hotness"] for item in payload["items"]]
    assert scores == sorted(scores, reverse=True)
    assert len(scores) == payload["total"]
    names = {item["name"] for item in payload["items"]}
    assert not (names & OUT_OF_POOL_NAMES), "两位 UP 都没做过的梗不能上榜"
    assert names & SINGLE_UP_NAMES == SINGLE_UP_NAMES, "并集准入：单 UP 也要能上榜"
    for item in payload["items"]:
        assert 0 <= item["hotness"] <= 100
        assert item["stage"] in {"sprouting", "rising", "explosive", "plateau", "receding", "obsolete"}
        assert item["catch_status"] in {"can_catch", "caution", "too_late"}
        assert item["nickname"]
        assert item["thumbnail"]["emoji"]
        # 认证强度标签必须跟着卡片走，不能让单 UP 冒充双 UP
        assert item["cert_label"] in {"双 UP 认证", "梗百科认证", "梗指南认证"}
        assert item["certified_by"], "入池的梗至少要有一位 UP 证据"
        assert item["double_certified"] is (len(item["certified_by"]) == 2)
        assert item["cert_label"] == (
            "双 UP 认证" if len(item["certified_by"]) == 2 else f"{item['certified_by'][0]}认证"
        )

    by_name = {item["name"]: item for item in payload["items"]}
    assert by_name["新梗观察A"]["cert_label"] == "梗百科认证"
    assert by_name["新梗观察A"]["certified_by"] == ["梗百科"]
    assert by_name["新梗观察B"]["cert_label"] == "梗指南认证"


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

    assert set(payload) >= {"meme", "hotness", "lifecycle", "metrics", "certification", "intro", "videos", "trend", "insight"}
    assert payload["meme"]["hotness"] == payload["hotness"]["score"]

    # 详情页的「这个梗是什么」：必须有来源标注，且不许是空白
    intro = payload["intro"]
    assert intro["source"] in {"manual", "transcript", "evidence", "none"}
    assert intro["source_label"]
    assert intro["text"], "点进详情不能看到一片空白"
    if intro["source"] == "evidence":
        # 证据拼出来的介绍，每个字都要能回指到一条真实解说视频
        assert intro["evidence"]
        assert all(item["video_title"] for item in intro["evidence"])

    # 热度分量 + 权重，且权重合计 1
    weights = payload["hotness"]["weights"]
    assert set(weights) == {"view", "interaction", "content", "creator", "growth"}
    assert sum(weights.values()) == pytest.approx(1.0)
    for value in payload["hotness"]["components"].values():
        assert 0 <= value <= 100

    # 生命周期六态 + 「数据不足」闸门态，且只有一个"当前所处"
    stages = payload["lifecycle"]["stages"]
    assert len(stages) == 7
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


def test_videos_pagination_reports_real_total(client, top_meme_id):
    """翻页接口不许把 limit 当 total 返回。

    线上真实数据里有个梗采信了 125 条视频，接口却回 total=3（等于 limit），
    前端据此判断"没有下一页"，用户永远只能看到前 3 条。
    """
    first = client.get(f"/api/memes/{top_meme_id}/videos?limit=2&offset=0&sort=view").json()
    assert first["offset"] == 0
    assert len(first["items"]) <= 2
    assert first["total"] >= len(first["items"])
    assert first["note"], "要说明这些视频是过完相关性筛的"

    # 一页页翻到底，拿到的条数必须等于 total，且不许重复
    seen, offset, guard = [], 0, 0
    while guard < 40:
        page = client.get(f"/api/memes/{top_meme_id}/videos?limit=2&offset={offset}&sort=view").json()
        assert page["total"] == first["total"], "翻页过程中 total 不许变"
        seen += [item["bvid"] for item in page["items"]]
        if not page["items"]:
            break
        offset += len(page["items"])
        guard += 1
    assert len(seen) == first["total"], f"翻完应有 {first['total']} 条，实际 {len(seen)}"
    assert len(set(seen)) == len(seen), "同一页之间不许重复"

    # 播放量降序，且参数越界要拦住
    views = [item["view"] for item in first["items"]]
    assert views == sorted(views, reverse=True)
    assert client.get(f"/api/memes/{top_meme_id}/videos?limit=99").status_code == 422
    assert client.get(f"/api/memes/{top_meme_id}/videos?offset=-1").status_code == 422


def test_videos_sort_follows_bilibili_rank(session, meme_factory):
    """相关视频两档排法：B 站综合排序名次 vs 播放量。

    「默认排序」是用户在 B 站搜这个词实际看到的顺序，掺了相关性与时效，
    头部常是几百万播放的老稿——跟"按播放量"是两套列表，不能混为一谈。
    """
    from app.services.meme import query as q

    meme = meme_factory(name="排序测试梗")
    session.add_all(
        [
            # 综合排序第 12 条，播放量最高（老稿）
            make_video("BVrank12", "排序测试梗 老稿", meme_id=meme.id, view=9_000_000,
                       search_rank=12, data_source="bilibili", relevance_score=0.9),
            # 综合排序第 1 条，播放量很低（站内把它排前面是因为相关性/时效）
            make_video("BVrank1", "排序测试梗 站内第一", meme_id=meme.id, view=30_000,
                       search_rank=1, data_source="bilibili", relevance_score=0.9),
            # 综合排序第 5 条
            make_video("BVrank5", "排序测试梗 站内第五", meme_id=meme.id, view=3_000_000,
                       search_rank=5, data_source="bilibili", relevance_score=0.9),
            # 没有名次：只从逐日头部样本采到，排在有名次的后面
            make_video("BVnorank", "排序测试梗 没名次", meme_id=meme.id, view=99_000_000,
                       data_source="bilibili", relevance_score=0.9),
        ]
    )
    session.flush()  # 不 commit：这个库是整模块共用的，留下脏梗会污染别的用例

    by_rank = q.video_page(session, meme, sort="rank")
    assert [item["bvid"] for item in by_rank["items"]] == [
        "BVrank1", "BVrank5", "BVrank12", "BVnorank",
    ], "默认排序必须按站内名次，没名次的垫底"
    assert by_rank["sort_applied"] == "rank" and by_rank["sort_label"] == "B站默认排序"

    by_view = q.video_page(session, meme, sort="view")
    assert [item["bvid"] for item in by_view["items"]] == [
        "BVnorank", "BVrank12", "BVrank5", "BVrank1",
    ], "播放量档就是纯按播放量降序"
    assert by_view["sort_label"] == "播放量"


def test_videos_rank_sort_degrades_honestly(session, meme_factory):
    """一条名次都没有时不许"假装排过"：退回播放量，并在 note 里说清楚。"""
    from app.services.meme import query as q

    meme = meme_factory(name="没名次测试梗")
    session.add_all(
        [
            make_video("BVb", "没名次测试梗 B", meme_id=meme.id, view=500,
                       data_source="bilibili", relevance_score=0.9),
            make_video("BVa", "没名次测试梗 A", meme_id=meme.id, view=5000,
                       data_source="bilibili", relevance_score=0.9),
        ]
    )
    session.flush()  # 同上：不往共用库里留脏数据

    page = q.video_page(session, meme, sort="rank")
    assert page["sort"] == "rank" and page["sort_applied"] == "view"
    assert [item["bvid"] for item in page["items"]] == ["BVa", "BVb"]
    assert "还没抓到" in page["note"], page["note"]


def test_videos_sort_param_validated(client, top_meme_id):
    """非法排法要挡在入口，不能默默当成 rank 处理。"""
    assert client.get(f"/api/memes/{top_meme_id}/videos?sort=bogus").status_code == 422
    ok = client.get(f"/api/memes/{top_meme_id}/videos?sort=view").json()
    assert ok["sort"] == "view" and ok["sort_applied"] == "view"
    # 演示数据没有真实名次：请求 rank 也必须如实退回播放量，不能假装排过
    rank = client.get(f"/api/memes/{top_meme_id}/videos?sort=rank").json()
    assert rank["sort_applied"] == "view", rank
    assert rank["sort_label"] == "播放量"


def test_list_supports_ids_filter(client):
    """收藏只存在本机，收藏页要靠 ids 参数拿实时数据（不能存梗的副本）。"""
    library = client.get("/api/memes?scope=all&limit=100").json()["items"]
    assert len(library) >= 3
    picked = [library[0]["id"], library[2]["id"]]
    got = client.get(f"/api/memes?scope=all&ids={picked[0]},{picked[1]}").json()
    assert got["total"] == 2, "只应返回点名的那两个"
    assert {row["id"] for row in got["items"]} == set(picked)
    assert [row["hotness"] for row in got["items"]] == sorted(
        [row["hotness"] for row in got["items"]], reverse=True
    ), "按 id 取也要照排序规则返回"

    # 垃圾输入不该让接口报错，也不该把全部梗放出来
    junk = client.get(f"/api/memes?scope=all&ids=abc,,{picked[0]},-5,0").json()
    assert [row["id"] for row in junk["items"]] == [picked[0]]
    assert client.get("/api/memes?scope=all&ids=").json()["total"] == len(library), "空 ids 等于不过滤"


def test_no_meme_detail_is_blank(client):
    """整库扫一遍：点进任何一条详情都不该看到空白介绍。"""
    items = client.get("/api/memes?scope=all&limit=100").json()["items"]
    assert items
    blanks = []
    for item in items:
        intro = client.get(f"/api/memes/{item['id']}").json()["intro"]
        if not intro["text"].strip():
            blanks.append((item["name"], intro["source"]))
    assert not blanks, f"这些梗的详情页没有介绍：{blanks}"



def test_detail_prefers_subtitle_over_title_evidence(client):
    """字幕进了库，介绍就该改成摘自字幕原文，并把原文留着可对照。

    这条走的是"内容层"：以前只有标题和简介能拼，现在能引用视频里真正说的话，
    但正文必须逐字等于摘录，不许系统另外编一句过渡话。
    """
    text = (
        "哈喽大家好，欢迎来到本期视频，今天聊一个新东西。"
        "这个梗出自 2019 年的一场直播，主播在逆风局里反复念同一句话。"
        "后来评论区把它做成了万能回应。"
        "记得三连加个关注，我们下期再见。"
    )
    ids = [item["id"] for item in client.get("/api/memes?scope=all&limit=100").json()["items"]]
    meme_id = next(meme_id for meme_id in ids if client.get(f"/api/memes/{meme_id}").status_code == 200)

    session = SessionLocal()
    original = ""
    try:
        meme = session.get(Meme, meme_id)
        original = meme.description or ""
        meme.description = ""
        session.add(
            VideoTranscript(
                bvid="BV1subtitle01",
                meme_id=meme_id,
                kind="cc",
                lang="zh-CN",
                text=text,
                chars=len(text),
                video_title="这条梗到底哪来的",
                logged_in=True,
            )
        )
        session.commit()

        intro = client.get(f"/api/memes/{meme_id}").json()["intro"]
        assert intro["source"] == "transcript" and intro["source_label"] == "字幕原文摘录"
        block = intro["transcript"]
        assert block["bvid"] == "BV1subtitle01"
        assert block["kind_label"] == "人工字幕" and block["certified"] is False
        assert "这个梗出自 2019 年的一场直播" in block["excerpt"]
        assert "欢迎来到本期视频" not in block["excerpt"] and "三连" not in block["excerpt"]
        assert intro["text"] == block["excerpt"], "正文只能是摘录本身，不能是系统另写的一句"
        assert block["full"] == text and block["full_truncated"] is False
        assert block["url"] == "https://www.bilibili.com/video/BV1subtitle01"
    finally:
        meme = session.get(Meme, meme_id)
        meme.description = original
        row = session.get(VideoTranscript, "BV1subtitle01")
        if row is not None:
            session.delete(row)
        session.commit()
        session.close()

    back = client.get(f"/api/memes/{meme_id}").json()["intro"]
    assert back["transcript"] is None, "清理要彻底，别让后面的用例读到这条字幕"


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


def test_out_of_pool_meme_is_blocked(client):
    from app.models import SessionLocal

    session = SessionLocal()
    meme = session.query(Meme).filter(
        Meme.encyclopedia_confirmed.is_(False), Meme.guide_confirmed.is_(False)
    ).first()
    meme_id, meme_name = meme.id, meme.name
    session.close()

    response = client.get(f"/api/memes/{meme_id}")
    assert response.status_code == 409
    assert "介绍过" in response.json()["detail"]
    assert meme_name not in [i["name"] for i in client.get("/api/memes?limit=100").json()["items"]]
    assert client.get("/api/memes/424242").status_code == 404


def test_single_up_meme_is_viewable(client):
    """准入放宽到并集之后，单 UP 的梗不能还被详情接口拦在门外。"""
    from app.models import SessionLocal

    session = SessionLocal()
    meme = session.query(Meme).filter(
        Meme.encyclopedia_confirmed.is_(True), Meme.guide_confirmed.is_(False)
    ).first()
    meme_id = meme.id
    session.close()

    payload = client.get(f"/api/memes/{meme_id}").json()
    assert payload["meme"]["cert_label"] == "梗百科认证"
    assert payload["meme"]["double_certified"] is False
    cert = payload["certification"]
    assert cert["admitted"] is True and cert["certified"] is False
    assert cert["certified_by"] == ["梗百科"]
    assert cert["cert_window_days"] == settings.cert_window_days


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
    # 并集准入之后只剩"两位 UP 都没做过"的那一个被跳过
    assert result["ok"] is True and result["computed"] >= 30 and result["skipped"] == 1
    after = client.get("/api/memes?limit=5").json()["items"]
    assert [(i["id"], i["hotness"]) for i in before] == [(i["id"], i["hotness"]) for i in after]


def test_no_response_leaks_a_secret(client):
    """全站扫描：任何接口响应里都不该出现 Key 字样或密钥值。"""
    paths = ["/api/health", "/api/meta", "/api/memes?limit=5", "/api/settings/llm"]
    for path in paths:
        text = client.get(path).text
        assert "sk-" not in text, path
        assert not math.isnan(0.0)


def test_real_mode_does_not_rank_demo_memes(client, monkeypatch):
    """配置成真实数据源时，手写演示梗不能和真梗同榜——假数字会压住真热度。

    这里一律用 scope=all：本测要验的是"真实数据闸门"，不能被上榜门槛干扰。
    """
    assert client.get("/api/memes?limit=100&scope=all").json()["total"] >= 30

    monkeypatch.setattr(settings, "data_source", "bilibili")
    assert client.get("/api/memes?limit=100&scope=all").json()["total"] == 0, "演示梗该被请出榜单"

    monkeypatch.setattr(settings, "leaderboard_require_verified", False)
    assert client.get("/api/memes?limit=100&scope=all").json()["total"] >= 30, "关掉开关就回到旧行为"
