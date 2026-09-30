"""采集层测试：全部离线，不碰真实 B 站接口。"""

from __future__ import annotations

from datetime import date, datetime, time as _time, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.collectors import BilibiliCollector, MockCollector, make_collector
from app.collectors.bilibili import (
    BilibiliBlocked,
    BilibiliThrottled,
    BiliClient,
    parse_search_row,
    sign_params,
)
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
    """替代 BiliClient：让我们能在不联网的情况下验证采集逻辑。

    ``rows`` 喂给逐日区间查询（search_range），``ranked`` 喂给"综合排序"那一页
    （search_videos）——两者分开是因为真实接口的结果集根本不同：
    逐日头部样本只有近 30 天的内容，综合排序会把几年前的老稿顶到第一页。
    """

    def __init__(self, *, blocked=False, rows=None, ranked=None):
        self.blocked = blocked
        self.rows = rows or []
        self.ranked = ranked if ranked is not None else []
        self.requested: list[str] = []

    def probe(self):
        if self.blocked:
            return False, "B 站风控拦截（HTTP 412）"
        return True, "WBI 签名可用"

    def search_videos(self, keyword, *, pages=1, order="pubdate"):
        self.requested.append(f"{keyword}#{order}")
        if self.blocked:
            from app.collectors.bilibili import BilibiliBlocked

            raise BilibiliBlocked("HTTP 412")
        return self.ranked

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
    """按"第几次请求这一天"决定给不给货，用来复现 B 站搜索的限流抖动。

    实测：B 站对同一天同一个词会返回带 ``v_voucher`` 的风控应答
    （HTTP 200、没有 numResults 字段、result 为空），而**真空返回**是
    ``result=[] 且 numResults=0``。两者必须分开：前者是"这次没给我"，
    后者才是"当天真没内容"。这个假客户端复现的是前者。
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
        if self.attempts[key] < self.give_on:
            raise BilibiliThrottled("被限流吞掉（返回体只有 v_voucher）")
        if not rows:
            return [], 0                 # 真空返回：这些天确实没内容
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


def test_throttled_day_is_unobserved_and_flagged(certified_meme, monkeypatch):
    """整天都被限流：必须标 observed=False，并且明确回报"这是被限流"。

    这一条是整套区分的关键——被限流和"当天没人做这个梗"在旧实现里
    都是 ``rows == []``，于是库里积了 1070 行假的 observed=0。
    """
    from app.config import settings

    monkeypatch.setattr(settings, "collect_day_retries", 2, raising=False)
    client = FlakyClient(rows=[_row(0, days_ago=1, title="测试标题")], give_on=99)
    collector = BilibiliCollector(client=client, request_gap=0, enrich_limit=2)

    rows, total, observed, throttled = collector._search_day(
        certified_meme.name,
        begin=datetime.combine(date.today() - timedelta(days=1), _time.min),
        end=datetime.combine(date.today(), _time.min))
    assert (rows, observed) == ([], False), "被限流不能算观测到"
    assert throttled is True, "必须回报这是限流，而不是普通的空结果"

    # 真空返回（numResults=0 那种）不该被标成限流
    quiet = FakeClient(rows=[])
    collector2 = BilibiliCollector(client=quiet, request_gap=0, enrich_limit=2)
    rows2, _, observed2, throttled2 = collector2._search_day(
        certified_meme.name,
        begin=datetime.combine(date.today() - timedelta(days=1), _time.min),
        end=datetime.combine(date.today(), _time.min))
    assert (rows2, observed2, throttled2) == ([], False, False), (
        "真没内容不该被当成限流，否则会白白重试并误报风控")


def test_throttle_streak_stops_the_window_early(certified_meme, monkeypatch):
    """一次冷却之后仍连续被吞，才提前收工（限流是会话级的，越打恢复越慢）。"""
    from app.config import settings

    monkeypatch.setattr(settings, "collect_day_retries", 1, raising=False)
    monkeypatch.setattr(settings, "collect_throttle_stop_after", 3, raising=False)
    # 冷却必须归零，否则这个用例真的会睡 180 秒
    monkeypatch.setattr(settings, "collect_throttle_cooldown", 0.0, raising=False)
    client = FlakyClient(rows=[_row(0, days_ago=1, title="测试标题")], give_on=99)
    collector = BilibiliCollector(client=client, request_gap=0, enrich_limit=2)
    stats_list = collector.collect_daily(certified_meme, window_days=30)[0]

    calls = sum(client.attempts.values())
    # 阈值 3 天就该停，不该打满 30 天。注意会跑两轮（梗名 + 别名兜底），
    # 所以用宽松上界，重点断言"停得下来"而不是精确次数。
    assert calls <= 16, f"连续限流后没有提前停止，共打了 {calls} 次请求"
    # 提前停止意味着后面的天没有生成行；已生成的那些必须如实标成未观测
    assert len(stats_list) < 30, "提前停止后不该仍有 30 天记录"
    assert all(s.observed is False for s in stats_list), "被限流的天不能标成观测到"


def test_throttle_cooldown_is_a_session_pause_not_a_retry_gap(monkeypatch):
    """被限流时的等待必须是"整条会话冷却"，而不是"这一天的重试间隔"。

    限流是会话级状态：换词、换日期、立刻重试都没用，只有整条会话静默才恢复。
    所以退避时长要以 `collect_throttle_cooldown` 为准，而不是
    `collect_retry_gap × 次数`——后者只有几秒，实测根本等不回来。
    """
    from app.config import settings

    monkeypatch.setattr(settings, "collect_retry_gap", 1.2, raising=False)
    monkeypatch.setattr(settings, "collect_throttle_cooldown", 180.0, raising=False)

    throttled = BilibiliCollector._backoff_seconds(0, throttled=True)
    ordinary = BilibiliCollector._backoff_seconds(0, throttled=False)

    assert throttled >= 180.0, f"被限流只等了 {throttled:.1f} 秒，等不回来"
    assert throttled > ordinary * 10, (
        f"限流退避 {throttled:.1f}s 与普通退避 {ordinary:.1f}s 没拉开差距")
    # 普通空结果的退避要克制，别把正常抖动也拖成分钟级
    assert ordinary < 5.0


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


class RankClient(FakeClient):
    """只回应"综合排序"那一页：行按站内顺序给，无关内容混在里面。"""

    def __init__(self, rows):
        super().__init__(rows=rows)
        self.ordered: list[str] = []

    def search_videos(self, keyword, *, pages=1, order="pubdate"):
        self.ordered.append(order)
        return self.rows


def test_totalrank_keeps_original_positions_and_drops_irrelevant(certified_meme):
    """综合排序的名次取过滤前的位置：宁可跳号，也不把"站内第 7 条"谎称第 4 条。"""
    name = certified_meme.name
    rows = [
        _row(0, days_ago=3, title=f"{name} 站内第1"),
        _row(1, days_ago=3, title="完全无关的其它内容标题一"),
        _row(2, days_ago=3, title=f"{name} 站内第3"),
        _row(3, days_ago=3, title="完全无关的其它内容标题二"),
        _row(4, days_ago=3, title=f"{name} 站内第5"),
    ]
    collector = BilibiliCollector(client=RankClient(rows), request_gap=0, enrich_limit=2)
    ranked = collector._totalrank(certified_meme)

    assert [item["search_rank"] for item in ranked] == [1, 3, 5], "名次要保留过滤前的原始位置"
    assert all(item["relevance_score"] >= 0.5 for item in ranked), "无关内容不能进列表"


def test_totalrank_asks_for_default_order(certified_meme):
    """默认排序必须问的是 B 站"综合"那一档（不传 order），不是 click/pubdate。"""
    client = RankClient([_row(0, days_ago=2, title=f"{certified_meme.name}名场面")])
    BilibiliCollector(client=client, request_gap=0, enrich_limit=2)._totalrank(certified_meme)
    assert client.ordered and set(client.ordered) == {""}


# --------------------------------------------------------------------------- #
# 字幕抓取：view → player 字幕轨 → 字幕文件三段链路，每一种「拿不到」都要说人话


def _subtitle_client(monkeypatch, *, cookie="SESSDATA=x", view=None, tracks=None, body=None, fail=None):
    """把 BiliClient 的三个网络出口换成假响应，并记录调用顺序。

    ``fail`` 用来模拟 view/player 直接风控；``body`` 是字幕文件里的逐句。
    """
    client = BiliClient(cookie=cookie)
    calls: list[str] = []
    client.downloaded_urls = []

    def _get_payload(url, params=None):
        calls.append("view")
        if fail == "view":
            raise BilibiliBlocked("B 站返回 HTTP 412")
        return {"code": 0, "data": view if view is not None else {"cid": 9001, "title": "《琵琶曲》这梗哪来的"}}

    def signed_get(url, params):
        calls.append("player")
        if fail == "player":
            raise BilibiliBlocked("B 站安全校验未通过（code=-352）")
        return {"subtitle": {"subtitles": tracks if tracks is not None else []}}

    def download(url, **kwargs):
        calls.append("file")
        client.downloaded_urls.append(url)
        if fail == "file":
            raise httpx.ReadTimeout("字幕文件超时")
        return SimpleNamespace(
            json=lambda: {"body": body if body is not None else []},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(client, "_get_payload", _get_payload)
    monkeypatch.setattr(client, "signed_get", signed_get)
    monkeypatch.setattr("app.collectors.bilibili.httpx.get", download)
    return client, calls


def test_subtitle_prefers_human_cc_over_ai(monkeypatch):
    """人工 CC 优先，同档里中文优先：AI 识别的错字会把「琵琶曲」听成「枇杷去」。"""
    tracks = [
        {"ai_type": 1, "lan": "zh-CN", "subtitle_url": "//bunches/ai.json"},
        {"ai_type": 0, "lan": "zh-CN", "subtitle_url": "//bunches/cc.json"},
        {"ai_type": 0, "lan": "en-US", "subtitle_url": "//bunches/en.json"},
    ]
    client, calls = _subtitle_client(
        monkeypatch,
        tracks=tracks,
        body=[{"content": "这个梗出自一场直播"}, {"content": ""}, {"content": "UP 主把它做成了 BGM"}],
    )
    result = client.subtitle_of("BV1cc")

    assert calls == ["view", "player", "file"]
    assert result.ok and result.kind == "cc" and result.lang == "zh-CN"
    assert result.text == "这个梗出自一场直播\nUP 主把它做成了 BGM", "空行要丢掉，其余原样保留"
    assert result.tracks == 3 and result.cid == 9001
    assert result.title == "《琵琶曲》这梗哪来的"
    assert client.downloaded_urls == ["https://bunches/cc.json"], "//开头的字幕地址要补成 https"


def test_subtitle_falls_back_to_ai_and_labels_it(monkeypatch):
    client, _ = _subtitle_client(
        monkeypatch,
        tracks=[{"ai_type": 1, "lan": "zh-CN", "subtitle_url": "/bunches/ai.json"}],
        body=[{"content": "自动识别的一句话"}],
    )
    result = client.subtitle_of("BV1ai")
    assert result.ok and result.kind == "ai"


def test_subtitle_anonymous_empty_tracks_points_at_cookie(monkeypatch):
    """匿名请求 code=0 但空轨，这时说「没字幕」是撒谎，必须点名要 cookie。"""
    client, calls = _subtitle_client(monkeypatch, cookie="", tracks=[])
    result = client.subtitle_of("BV1an")
    assert not result.ok
    assert "BILI_COOKIE" in result.reason
    assert result.logged_in is False
    assert calls == ["view", "player"], "没有轨就不该再去下载字幕文件"


def test_subtitle_login_but_no_track_is_reported_as_no_track(monkeypatch):
    client, _ = _subtitle_client(monkeypatch, cookie="SESSDATA=x", tracks=[])
    result = client.subtitle_of("BV1none")
    assert not result.ok and "没有字幕轨" in result.reason


def test_subtitle_empty_file_and_missing_cid_have_distinct_reasons(monkeypatch):
    client, calls = _subtitle_client(
        monkeypatch,
        tracks=[{"ai_type": 0, "lan": "zh-CN", "subtitle_url": "/bunches/cc.json"}],
        body=[],
    )
    result = client.subtitle_of("BV1empty")
    assert "空的" in result.reason and calls == ["view", "player", "file"]

    dead, dead_calls = _subtitle_client(monkeypatch, view={"cid": 0, "title": ""})
    gone = dead.subtitle_of("BV1gone")
    assert "cid" in gone.reason and dead_calls == ["view"], "视频查不到就不该继续打播放器接口"


def test_subtitle_download_failure_names_the_step(monkeypatch):
    client, _ = _subtitle_client(
        monkeypatch,
        tracks=[{"ai_type": 0, "lan": "zh-CN", "subtitle_url": "/bunches/cc.json"}],
        fail="file",
    )
    result = client.subtitle_of("BV1dl")
    assert "字幕文件下载失败" in result.reason and not result.ok


def test_subtitle_player_blocked_reason_is_kept(monkeypatch):
    """view 通了、player 被风控——reason 要写出是哪一步断的。"""
    client, _ = _subtitle_client(monkeypatch, fail="player")
    result = client.subtitle_of("BV1r")
    assert "播放器信息失败" in result.reason


# --------------------------------------------------------------------------- #
# 名次补录脚本：不能因为脏数据整条梗崩掉


class _RankOnlyCollector:
    """只回应"综合排序"这一件事的假采集器，用来单测补录脚本。"""

    source = "bilibili"

    def __init__(self, items):
        self.items = items

    def _totalrank(self, meme):
        return self.items


def _ranked(bvid: str, rank: int) -> dict:
    return {
        "bvid": bvid,
        "aid": None,
        "title": f"{bvid} 的综合排序第 {rank} 条",
        "description": "",
        "author": "某UP",
        "author_mid": None,
        "cover": "",
        "duration_seconds": 60,
        "view": 1000 + rank,
        "reply": 1,
        "danmaku": 1,
        "relevance_score": 0.9,
        "matched_terms": [],
        "publish_time": datetime(2026, 9, 20),
        "search_rank": rank,
    }


def test_refresh_rank_tolerates_duplicate_rows_and_demo_sourced_rows(session, certified_meme):
    """两个真实坑：B 站同一页里重复给同一个 bvid；这条视频先以演示来源入过库。

    两者都会撞 videos(meme_id, bvid) 唯一键——唯一键不含 data_source，
    按来源过滤着查就漏判成"库里没有"，然后整条梗补录失败。
    """
    from app.scripts.refresh_video_rank import refresh_one

    session.add(
        Video(
            meme_id=certified_meme.id,
            bvid="BV1demo",
            title="先以演示来源入库的同一条",
            view=10,
            publish_time=datetime(2026, 9, 18),
            data_source="mock",
        )
    )
    session.flush()
    collector = _RankOnlyCollector([_ranked("BV1demo", 1), _ranked("BV1dup", 2), _ranked("BV1dup", 3)])

    touched, added = refresh_one(session, collector, certified_meme, dry_run=False)

    assert touched == 1, "演示来源那条只补名次，不重复插入"
    assert added == 1, "重复出现的 bvid 只入库一次"
    rows = {
        row.bvid: row
        for row in session.scalars(select(Video).where(Video.meme_id == certified_meme.id))
    }
    assert set(rows) == {"BV1demo", "BV1dup"}
    assert rows["BV1demo"].search_rank == 1 and rows["BV1demo"].data_source == "mock"
    assert rows["BV1dup"].search_rank == 2, "同名次取第一次出现的位置"


# --------------------------------------------------------------------------- #
# 采集节流与硬风控熔断
# （settings.collect_request_gap / collect_block_abort_after）
# --------------------------------------------------------------------------- #


class _HardBlockedClient(FakeClient):
    """probe 说"能用"，一发搜索就抛硬风控（412 / -352）。

    对应实测里"跑着跑着风控升级"：开头通，后面整条会话被拦。
    用 ``blocked=True`` 的 FakeClient 测不了这个——它连 is_available 都过不了，
    collect_all 会在发第一个请求之前就返回。
    """

    def probe(self):
        return True, "WBI 签名可用"

    def search_videos(self, keyword, **kwargs):
        self.requested.append(str(keyword))
        raise BilibiliBlocked("HTTP 412")

    def search_range(self, keyword, **kwargs):
        self.requested.append(str(keyword))
        raise BilibiliBlocked("HTTP 412")


def test_collector_request_gap_comes_from_settings(monkeypatch):
    """间隔默认取配置，别在采集器里写死。"""
    from app.config import settings

    monkeypatch.setattr(settings, "collect_request_gap", 4.5)
    assert BilibiliCollector(client=FakeClient(rows=[])).request_gap == 4.5
    # 显式传参仍然覆盖配置（测试用 0 跑快）
    assert BilibiliCollector(client=FakeClient(rows=[]), request_gap=0).request_gap == 0


def test_collect_all_aborts_after_consecutive_hard_blocks(session, meme_factory, monkeypatch):
    """连续 N 个梗被硬风控拦下 → 中止整批，别再往下喂风控。"""
    from app.config import settings

    memes = [meme_factory() for _ in range(4)]
    client = _HardBlockedClient()
    _patch_client(monkeypatch, client)
    monkeypatch.setattr(settings, "collect_block_abort_after", 3)

    result = collect_all("bilibili", meme_ids=[m.id for m in memes], window_days=1)

    assert result["aborted"] is True
    assert result["failed"] == 3, "熔断只算前 3 个梗，第 4 个不该被计入失败"
    assert not any(e.startswith(memes[3].name) for e in client.requested), \
        "第 4 个梗必须一个请求都没发——中止的意义就在这"
    assert "中止" in str(result["abort_reason"])


def test_collect_all_block_fuse_can_be_switched_off(session, meme_factory, monkeypatch):
    """设 0 = 关闭保险，退回"这个梗失败就跳过、继续下一个"的旧行为。"""
    from app.config import settings

    memes = [meme_factory() for _ in range(3)]
    client = _HardBlockedClient()
    _patch_client(monkeypatch, client)
    monkeypatch.setattr(settings, "collect_block_abort_after", 0)

    result = collect_all("bilibili", meme_ids=[m.id for m in memes], window_days=1)

    assert not result.get("aborted"), "关掉保险就不该中止整批"
    assert result["failed"] == 3
    assert any(e.startswith(memes[2].name) for e in client.requested), \
        "最后一个梗仍然被尝试过"


def test_search_range_treats_unreadable_body_as_throttled(monkeypatch):
    """返回体既没有 result、也没有 numResults：读不懂就按被限流处理。

    只有 ``numResults`` 在场的空 result 才是 B 站明确说的"当天没有内容"。
    把读不懂的答复当成零活动，就又会攒出假零——琵琶曲那次误判就是这么来的。
    """
    client = BiliClient(cookie="", timeout=5)
    begin = datetime.now() - timedelta(days=2)
    end = begin + timedelta(days=1)

    monkeypatch.setattr(client, "signed_get", lambda url, params: {"esCode": 10000})
    with pytest.raises(BilibiliThrottled) as exc:
        client.search_range("测试词", begin=begin, end=end)
    assert "numResults" in str(exc.value)

    # 带 numResults=0 的真空返回照旧是可信的"当天没有"
    monkeypatch.setattr(client, "signed_get",
                        lambda url, params: {"result": [], "numResults": 0, "numPages": 0})
    assert client.search_range("测试词", begin=begin, end=end) == ([], 0)


def test_collect_all_offset_is_applied_before_limit(session, meme_factory, monkeypatch):
    """分批跑：offset 要在 limit 之前生效，否则第二棒会把第一棒那批重采一遍。

    这是"分天铺全库"的前提——没有 offset，``--limit 10`` 之后再跑
    ``--limit 10`` 拿到的还是同样前 10 个梗。
    """
    from app.config import settings

    monkeypatch.setattr(settings, "collect_day_retries", 0, raising=False)
    monkeypatch.setattr(settings, "collect_request_gap", 0.0, raising=False)
    monkeypatch.setattr(settings, "collect_throttle_cooldown", 0.0, raising=False)
    memes = [meme_factory(name=f"分批梗{tag}") for tag in "ABCD"]
    ids = [m.id for m in memes]

    c1 = FakeClient(rows=[])
    _patch_client(monkeypatch, c1)
    first = collect_all("bilibili", meme_ids=ids, window_days=1, limit=2)

    c2 = FakeClient(rows=[])
    _patch_client(monkeypatch, c2)
    second = collect_all("bilibili", meme_ids=ids, window_days=1, offset=2, limit=2)

    assert first["targets"] == 2 and second["targets"] == 2
    for prefix, should_hit in (("分批梗A", True), ("分批梗B", True),
                               ("分批梗C", False), ("分批梗D", False)):
        assert any(k.startswith(prefix) for k in c1.requested) is should_hit, (
            f"第一棒{prefix}{'该打' if should_hit else '不该打'}")
    for prefix, should_hit in (("分批梗A", False), ("分批梗B", False),
                               ("分批梗C", True), ("分批梗D", True)):
        assert any(k.startswith(prefix) for k in c2.requested) is should_hit, (
            f"第二棒{prefix}{'该打' if should_hit else '不该打'}")
    assert "跳过前 2 个" in str(second["scope_note"])
