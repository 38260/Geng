"""采集层测试：全部离线，不碰真实 B 站接口。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.collectors import BilibiliCollector, MockCollector, make_collector
from app.collectors.bilibili import parse_search_row, sign_params
from app.models import Meme, MemeDailyStats, Video
from app.services.pipeline import collect_all

# 真实的 img_key/sub_key 是 64 位文件名，签名表要索引到第 63 位
IMG_KEY = "7cd0849413384173a0436703415832c9"
SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"

_counter = {"n": 0}


def test_factory_picks_collector():
    assert isinstance(make_collector("mock"), MockCollector)
    assert isinstance(make_collector("bilibili"), BilibiliCollector)
    assert isinstance(make_collector("BILIBILI"), BilibiliCollector)


def test_mock_collector_output_is_labelled_mock(meme_factory, session):
    # 演示梗库里已有同名梗时复用，避免用例之间互相撞唯一键
    meme = session.query(Meme).filter(Meme.name == "电子木鱼").one_or_none()
    if meme is None:
        meme = meme_factory(name="电子木鱼", aliases=["赛博木鱼"], keywords=["木鱼", "功德"])
    bundle = MockCollector().collect(meme, window_days=30)
    assert bundle.daily_stats and bundle.videos
    assert all(row.data_source == "mock" for row in bundle.daily_stats)
    assert all(video.data_source == "mock" for video in bundle.videos)
    assert {cert.role for cert in bundle.certifications} == {"encyclopedia", "guide"}


def test_wbi_signature_is_stable_and_ordered(monkeypatch):
    monkeypatch.setattr("app.collectors.bilibili.time.time", lambda: 1_700_000_000)
    signed = sign_params({"search_type": "video", "keyword": "电子木鱼", "page": 1}, IMG_KEY, SUB_KEY)

    assert signed["wts"] == "1700000000"
    assert len(signed["w_rid"]) == 32
    assert list(signed)[:3] == ["keyword", "page", "search_type"]
    reordered = sign_params({"page": 1, "keyword": "电子木鱼", "search_type": "video"}, IMG_KEY, SUB_KEY)
    assert signed["w_rid"] == reordered["w_rid"]
    assert sign_params({"keyword": "a'b(c)*"}, IMG_KEY, SUB_KEY)["keyword"] == "abc"


def test_parse_search_row_strips_highlight_tags():
    row = {
        "bvid": "BV1xx",
        "title": '<em class="keyword">电子木鱼</em>是什么梗',
        "description": "赛博功德",
        "author": "<em>某UP</em>",
        "play": 1234,
        "danmaku": 5,
        "review": 7,
        "pubdate": datetime(2026, 9, 20).timestamp(),
        "duration": "3:12",
    }
    parsed = parse_search_row(row)
    assert parsed["title"] == "电子木鱼是什么梗"
    assert parsed["author"] == "某UP"
    assert parsed["view"] == 1234
    assert parsed["reply"] == 7
    assert parsed["duration_seconds"] == 192
    assert parsed["publish_time"].date() == datetime(2026, 9, 20).date()


class FakeClient:
    """替代 BiliClient：让我们能在不联网的情况下验证采集逻辑。"""

    def __init__(self, *, blocked=False, rows=None):
        self.blocked = blocked
        self.rows = rows or []
        self.requested: list[str] = []

    def probe(self):
        if self.blocked:
            return False, "B 站风控拦截（HTTP 412）"
        return True, "WBI 签名可用"

    def search_videos(self, keyword, *, pages=1, order="pubdate"):
        self.requested.append(keyword)
        if self.blocked:
            from app.collectors.bilibili import BilibiliBlocked

            raise BilibiliBlocked("HTTP 412")
        return self.rows

    def search_range(self, keyword, *, begin, end, order="click", page=1, page_size=20):
        """模拟 B 站的发布时间区间过滤。"""
        self.requested.append(f"{keyword}@{begin.date()}")
        if self.blocked:
            from app.collectors.bilibili import BilibiliBlocked

            raise BilibiliBlocked("HTTP 412")
        rows = [
            row for row in self.rows
            if begin.timestamp() <= row["pubdate"] < end.timestamp()
        ]
        return rows[:page_size], len(rows)

    def _get_payload(self, url, params):
        return {
            "data": {
                "stat": {
                    "view": 5000, "like": 200, "coin": 60,
                    "favorite": 80, "reply": 30, "danmaku": 45,
                },
                "duration": 100,
                "desc": "详情描述",
                "mid": 900,
                "tags": [],
            }
        }


def _row(index: int, *, days_ago: int, title: str):
    return {
        "bvid": f"BV1fake{index}_{_counter['n']}",
        "aid": 1000 + index,
        "title": title,
        "description": "",
        "author": f"UP{index}",
        "mid": 900 + index,
        "pic": "",
        "play": 1000 * (index + 1),
        "danmaku": 10,
        "review": 3,
        "pubdate": (datetime.now() - timedelta(days=days_ago)).timestamp(),
        "duration": "1:30",
    }


@pytest.fixture()
def certified_meme(session, meme_factory):
    from app.services.meme.certification import record_certification

    _counter["n"] += 1
    name = f"采集测试梗{_counter['n']}"
    # 别名保持 ≥4 字：短别名按相关性规则只能算弱证据，这里要测的是"退回别名再查一轮"的机制
    meme = meme_factory(name=name, aliases=[f"测试别名梗{_counter['n']}"], keywords=["拟声", "装傻"])
    record_certification(session, meme, "encyclopedia", bvid="BV1enc")
    record_certification(session, meme, "guide", bvid="BV1gui")
    session.commit()
    return meme


def _patch_client(monkeypatch, client):
    from app.collectors import bilibili_collector

    monkeypatch.setattr(bilibili_collector, "get_client", lambda: client)


def test_bilibili_collector_builds_consistent_daily_stats(certified_meme):
    name = certified_meme.name
    rows = [
        _row(0, days_ago=2, title=f"{name}名场面"),
        _row(1, days_ago=2, title=f"{name}reaction"),
        _row(2, days_ago=9, title=f"第一次看{name}"),
        _row(3, days_ago=120, title=f"窗口外的老视频 {name}"),
    ]
    collector = BilibiliCollector(client=FakeClient(rows=rows), request_gap=0, enrich_limit=10)
    bundle = collector.collect(certified_meme, window_days=30)

    assert len(bundle.videos) == 3, "窗口外的视频不应进入统计"
    assert all(video.data_source == "bilibili" for video in bundle.videos)
    assert bundle.videos[0].like == 200 and bundle.videos[0].coin == 60, "详情接口应补齐点赞/投币"

    # 逐日采集会产出完整窗口（含没有内容的日子），这样增长率才有可比的分母
    assert len(bundle.daily_stats) == 30
    by_day = {stat.stat_date: stat for stat in bundle.daily_stats}
    assert sum(1 for stat in bundle.daily_stats if stat.video_count == 0) == 28
    recent = max(day for day, stat in by_day.items() if stat.video_count)
    assert by_day[recent].video_count == 2
    # 日统计用的是搜索接口给的播放量（1000+2000）；详情接口补齐的点赞/投币
    # 只写进视频列表，不回灌日统计，避免两个口径混用
    assert by_day[recent].view == 3_000
    assert by_day[recent].creator_count == 2      # 两个不同 UP 主
    assert by_day[recent].search_total == 2       # B站给出的当日结果总数


def test_collect_all_drops_irrelevant_search_results(certified_meme, session, monkeypatch):
    """搜索结果里混着的无关视频，必须在聚合前被相关性过滤剔掉。"""
    name = certified_meme.name
    rows = [
        _row(0, days_ago=1, title=f"{name}是什么梗"),
        _row(1, days_ago=1, title="周末去了趟郊外 vlog"),
        _row(2, days_ago=1, title="本周热门视频合集"),
    ]
    _patch_client(monkeypatch, FakeClient(rows=rows))

    result = collect_all("bilibili", meme_ids=[certified_meme.id], window_days=30)

    assert result["ok"] is True and result["collected"] == 1
    assert result["dropped"] == 2
    session.expire_all()
    kept = session.query(Video).filter(Video.meme_id == certified_meme.id).all()
    assert [video.title for video in kept] == [f"{name}是什么梗"]
    assert all(video.relevance_score >= 0.5 for video in kept)


def test_collect_all_refuses_when_blocked_and_keeps_data(certified_meme, session, monkeypatch):
    before = session.query(Video).filter(Video.meme_id == certified_meme.id).count()
    _patch_client(monkeypatch, FakeClient(blocked=True))

    result = collect_all("bilibili", meme_ids=[certified_meme.id], window_days=30)

    assert result["ok"] is False
    assert "412" in str(result["reason"])
    assert result["collected"] == 0
    session.expire_all()
    assert session.query(Video).filter(Video.meme_id == certified_meme.id).count() == before


def test_collect_all_replaces_previous_source_for_a_meme(certified_meme, session, monkeypatch):
    """一个梗只能有一个数据来源，否则时间序列会把演示数据和真实数据加起来。"""
    session.add(
        MemeDailyStats(
            meme_id=certified_meme.id,
            stat_date=date.today(),
            video_count=99,
            view=999_999,
            data_source="mock",
        )
    )
    session.commit()

    name = certified_meme.name
    _patch_client(monkeypatch, FakeClient(rows=[_row(0, days_ago=1, title=f"{name}名场面")]))

    result = collect_all("bilibili", meme_ids=[certified_meme.id], window_days=30)

    assert result["ok"] is True and result["collected"] == 1
    session.expire_all()
    stats = session.query(MemeDailyStats).filter(MemeDailyStats.meme_id == certified_meme.id).all()
    assert stats and all(row.data_source == "bilibili" for row in stats)
    assert sum(row.video_count for row in stats) < 99, "旧的演示数据不应残留"
    assert session.get(Meme, certified_meme.id).data_source == "bilibili"


class TermAwareClient(FakeClient):
    """不同搜索词返回不同结果，用来验证"梗名太口语时会退回别名再查"。"""

    def __init__(self, mapping: dict[str, list]):
        super().__init__(rows=[])
        self.mapping = mapping

    def search_range(self, keyword, *, begin, end, order="click", page=1, page_size=20):
        self.requested.append(f"{keyword}@{begin.date()}")
        rows = [
            row for row in self.mapping.get(keyword, [])
            if begin.timestamp() <= row["pubdate"] < end.timestamp()
        ]
        return rows[:page_size], len(rows)


def test_daily_collection_falls_back_to_alias_when_name_is_too_vague(certified_meme):
    """梗名是常用口语时 B 站只会回一堆无关内容，这时必须用别名再查一轮。"""
    alias = certified_meme.aliases[0]
    client = TermAwareClient({
        certified_meme.name: [_row(0, days_ago=1, title="周末去了趟郊外 vlog")],
        alias: [
            _row(1, days_ago=1, title=f"{alias}是什么梗"),
            _row(2, days_ago=4, title=f"第一次看{alias}"),
        ],
    })
    collector = BilibiliCollector(client=client, request_gap=0, enrich_limit=0)

    stats, seen, dropped = collector.collect_daily(certified_meme, window_days=30)

    assert sum(1 for row in stats if row.video_count) == 2, "别名那一版才算采到内容"
    assert len(seen) == 2
    assert any(entry.startswith(f"{alias}@") for entry in client.requested), "应该用别名补查过"
    titles = " ".join(item["title"] for item in seen.values())
    assert alias in titles and "vlog" not in titles, "梗名那轮采到的无关内容不该进结果"


def test_alias_pass_is_skipped_when_name_already_shapes_series(certified_meme):
    """梗名本身就能画出形状时，不该再多打 30 次接口。"""
    name = certified_meme.name
    client = TermAwareClient({
        name: [_row(index, days_ago=index + 1, title=f"{name}名场面{index}") for index in range(9)],
    })
    collector = BilibiliCollector(client=client, request_gap=0, enrich_limit=0)

    stats, _, _ = collector.collect_daily(certified_meme, window_days=30)

    assert sum(1 for row in stats if row.video_count) == 9
    assert all(entry.startswith(f"{name}@") for entry in client.requested), "不该再查别名"


def test_purge_when_empty_keeps_previous_real_snapshot(certified_meme, session, monkeypatch):
    """一次空窗不能把上次采到的真实快照删掉——B站搜索结果本身就会抖。"""
    from app.collectors.base import CollectedBundle

    session.add(
        MemeDailyStats(
            meme_id=certified_meme.id, stat_date=date.today() - timedelta(days=1),
            video_count=3, view=30_000, reply=300, danmaku=900, data_source="bilibili",
        )
    )
    session.add(
        MemeDailyStats(
            meme_id=certified_meme.id, stat_date=date.today() - timedelta(days=2),
            video_count=9, view=900_000, data_source="mock",
        )
    )
    session.commit()

    class EmptyCollector:
        source = "bilibili"

        def is_available(self):
            return True, "ok"

        def collect(self, meme, *, window_days=30):
            return CollectedBundle(daily_stats=[], videos=[], dropped_irrelevant=2)

    monkeypatch.setattr("app.collectors.make_collector", lambda _source: EmptyCollector())

    result = collect_all(
        "bilibili", meme_ids=[certified_meme.id], window_days=30, purge_when_empty=True
    )

    session.expire_all()
    rows = session.query(MemeDailyStats).filter(MemeDailyStats.meme_id == certified_meme.id).all()
    assert result["empty"] == 1 and result["kept_snapshots"] == 1
    assert [row.data_source for row in rows] == ["bilibili"], "真实快照留下，演示行清掉"
    assert rows[0].video_count == 3
