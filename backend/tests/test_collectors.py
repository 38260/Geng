"""采集层测试：全部离线，不碰真实 B 站接口。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.collectors import BilibiliCollector, MockCollector, make_collector
from app.collectors.bilibili import parse_search_row, sign_params
from app.models import Meme, MemeCertification, MemeDailyStats, Video
from app.services.pipeline import _demo_only_ids, collect_all

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


def test_incremental_run_keeps_history(certified_meme, session, monkeypatch):
    """只补一天的增量跑，不许把历史砍掉。

    自动日更的前提：每天只想补 T-1 那一天，不能顺手把之前 30 天删了。
    原来 purge_previous_series 删的是"keep_days 之外的所有行"，
    window_days=1 就会把整个序列砍成 1 天。
    """
    name = certified_meme.name
    today = date.today()
    for back in range(2, 32):
        session.add(
            MemeDailyStats(
                meme_id=certified_meme.id,
                stat_date=today - timedelta(days=back),
                video_count=3,
                view=30_000,
                data_source="bilibili",
            )
        )
    session.commit()

    _patch_client(monkeypatch, FakeClient(rows=[_row(0, days_ago=1, title=f"{name}名场面")]))
    result = collect_all("bilibili", meme_ids=[certified_meme.id], window_days=1)

    assert result["ok"] is True and result["collected"] == 1
    session.expire_all()
    rows = session.query(MemeDailyStats).filter(
        MemeDailyStats.meme_id == certified_meme.id, MemeDailyStats.data_source == "bilibili"
    ).all()
    assert len(rows) == 31, f"30 天历史 + 新补的 T-1，实际 {len(rows)} 行"
    by_day = {row.stat_date: row for row in rows}
    old = by_day[today - timedelta(days=20)]
    assert (old.video_count, old.view) == (3, 30_000), "窗口外的历史行必须原样保留"
    fresh = by_day[today - timedelta(days=1)]
    assert fresh.video_count == 1 and fresh.view > 0, "本次采到的那天要写进来"


def test_incremental_run_still_prefers_better_old_observation(certified_meme, session, monkeypatch):
    """补采同一天时，旧观测样本更多就沿用旧的——这条规则对增量同样成立。"""
    name = certified_meme.name
    yesterday = date.today() - timedelta(days=1)
    session.add(
        MemeDailyStats(
            meme_id=certified_meme.id,
            stat_date=yesterday,
            video_count=9,
            view=900_000,
            data_source="bilibili",
        )
    )
    session.commit()

    _patch_client(monkeypatch, FakeClient(rows=[_row(0, days_ago=1, title=f"{name}名场面")]))
    result = collect_all("bilibili", meme_ids=[certified_meme.id], window_days=1)

    assert result["kept_better_days"] == 1
    session.expire_all()
    row = session.query(MemeDailyStats).filter(
        MemeDailyStats.meme_id == certified_meme.id, MemeDailyStats.stat_date == yesterday
    ).one()
    assert (row.video_count, row.view) == (9, 900_000), "更好的那次观测不能被覆盖"


def test_demo_only_ids_only_flags_pure_demo_memes(session, meme_factory):
    """纯演示 = mock 来源且没有任何 B 站真实证据；挂过真实证据的就不算。"""
    _counter["n"] += 1
    # 库里造出来的演示梗是"已认证 + mock 来源"，不是候选
    pure = meme_factory(name=f"纯演示梗{_counter['n']}", data_source="mock", status="certified")
    _counter["n"] += 1
    candidate = meme_factory(
        name=f"手动投稿候选梗{_counter['n']}", data_source="mock", status="candidate"
    )
    _counter["n"] += 1
    with_evidence = meme_factory(
        name=f"有证据的梗{_counter['n']}", data_source="mock", status="certified"
    )
    session.add(
        MemeCertification(
            meme_id=with_evidence.id, role="encyclopedia", up_name="梗百科", up_mid=1,
            bvid="BV1real", confirmed=True, data_source="bilibili",
        )
    )
    _counter["n"] += 1
    real = meme_factory(name=f"真实梗{_counter['n']}", data_source="bilibili")
    session.commit()

    demo = _demo_only_ids(session)
    assert pure.id in demo
    assert candidate.id not in demo, "有人点名要量的候选梗不能当成演示数据跳过"
    assert with_evidence.id not in demo, "有一条真实证据就不该被当成演示数据跳过"
    assert real.id not in demo


def test_scope_real_collects_fewer_than_all(session, monkeypatch):
    """真实模式下 scope=real 要真的少打接口，否则定时刷新会白烧请求。"""
    _patch_client(monkeypatch, FakeClient(rows=[]))
    real = collect_all("bilibili", window_days=1, scope="real")
    everything = collect_all("bilibili", window_days=1, scope="all")

    assert real["targets"] < everything["targets"]
    assert real["skipped_demo"] == everything["targets"] - real["targets"]
    assert "纯演示" in str(real["scope_note"])
    assert "不套 scope" not in str(real["scope_note"])


def test_explicit_ids_bypass_scope(session, monkeypatch, certified_meme):
    """点名要刷的梗不许被 scope 挡掉——certified_meme 本身就是 mock 来源。"""
    _patch_client(monkeypatch, FakeClient(rows=[_row(0, days_ago=1, title=f"{certified_meme.name}名场面")]))
    result = collect_all("bilibili", meme_ids=[certified_meme.id], window_days=1, scope="real")

    assert result["targets"] == 1
    assert "不套 scope" in str(result["scope_note"])
    assert result["collected"] == 1


class FlakyClient(FakeClient):
    """按"第几次请求这一天"决定给不给货，用来复现 B 站搜索的空壳抖动。

    实测：同一个词同一天连打两次，能一次返回 20 条、一次返回 0 条，
    而两种情况在返回体里长得一模一样（HTTP 200 + 空 result）。
    """

    def __init__(self, *, rows=None, give_on: int = 2):
        super().__init__(rows=rows)
        self.give_on = give_on
        self.attempts: dict[str, int] = {}

    def search_range(self, keyword, *, begin, end, order="click", page=1, page_size=20):
        key = f"{keyword}@{begin.date()}"
        self.attempts[key] = self.attempts.get(key, 0) + 1
        rows = [
            row for row in self.rows
            if begin.timestamp() <= row["pubdate"] < end.timestamp()
        ]
        if self.attempts[key] < self.give_on or not rows:
            return [], 0                 # 空壳：接口没给这一天的数据
        return rows[:page_size], len(rows)


def test_flaky_day_is_retried_and_recovered(certified_meme, monkeypatch):
    """第二次才给货的日子，必须被记成"观测到了"，而不是留一个 0。"""
    from app.config import settings

    monkeypatch.setattr(settings, "collect_day_retries", 2, raising=False)
    name = certified_meme.name
    client = FlakyClient(rows=[_row(0, days_ago=2, title=f"{name}名场面")], give_on=2)
    collector = BilibiliCollector(client=client, request_gap=0, enrich_limit=2)
    bundle = collector.collect(certified_meme, window_days=5)

    day2 = [s for s in bundle.daily_stats if s.video_count > 0]
    assert len(day2) == 1, "重试拿到内容的那天应该有数"
    assert day2[0].observed is True
    assert client.attempts[f"{name}@{day2[0].stat_date}"] == 2, "应该是第二次请求才拿到"


def test_all_empty_days_marked_unobserved_not_zero(certified_meme, monkeypatch):
    """几次都空的日子要标 observed=False：它是洞，不是"当天没人做这个梗"。"""
    from app.config import settings

    monkeypatch.setattr(settings, "collect_day_retries", 2, raising=False)
    collector = BilibiliCollector(client=FakeClient(rows=[]), request_gap=0, enrich_limit=2)
    bundle = collector.collect(certified_meme, window_days=5)

    assert len(bundle.daily_stats) == 5, "窗口骨架仍然要跑满"
    assert all(row.observed is False for row in bundle.daily_stats), "全是空壳，一天都没观测到"
    assert all(row.video_count == 0 for row in bundle.daily_stats)


def test_filtered_out_content_still_counts_as_observed(certified_meme, monkeypatch):
    """接口给了行、但全被相关性过滤掉 —— 这是"观测到了，当天确实没人做"，不是洞。"""
    from app.config import settings

    monkeypatch.setattr(settings, "collect_day_retries", 2, raising=False)
    rows = [_row(0, days_ago=2, title="完全无关的其它内容标题")]
    collector = BilibiliCollector(client=FakeClient(rows=rows), request_gap=0, enrich_limit=2)
    bundle = collector.collect(certified_meme, window_days=5)

    hit = next(s for s in bundle.daily_stats if s.search_total)
    assert hit.observed is True
    assert hit.video_count == 0, "无关内容不能进统计，但这一天确实被观测过"


def test_unobserved_row_never_overwrites_real_observation(session, certified_meme):
    """同日合并：一次空返回不许把上次真正观测到的那天盖掉。"""
    from app.services.pipeline import split_daily_stats

    day = date.today() - timedelta(days=3)
    stored = MemeDailyStats(
        meme_id=certified_meme.id, stat_date=day, video_count=14, creator_count=12,
        view=1_400_000, reply=100, danmaku=50, search_total=900,
        data_source="bilibili", observed=True,
    )
    session.add(stored)
    session.flush()

    hole = MemeDailyStats(
        meme_id=certified_meme.id, stat_date=day, video_count=0, creator_count=0,
        view=0, data_source="bilibili", observed=False,
    )
    incoming, reuse = split_daily_stats(session, certified_meme, [hole], "bilibili")

    assert reuse == 1 and incoming == [], "空壳不许覆盖真观测"
    # 反过来：真观测要能盖掉之前的空壳
    stored.observed, stored.video_count, stored.view = False, 0, 0
    session.flush()
    good = MemeDailyStats(
        meme_id=certified_meme.id, stat_date=day, video_count=9, creator_count=8,
        view=300_000, data_source="bilibili", observed=True,
    )
    incoming, reuse = split_daily_stats(session, certified_meme, [good], "bilibili")
    assert reuse == 0 and incoming == [good], "补到的真观测必须写进去"
