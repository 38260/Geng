"""发现层：并集入池、写法合并、单边被风控也能出池。

这些规则全靠 B 站空间投稿接口（限流很凶），所以这里用假客户端把规则本身钉住，
不依赖网络。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from app.collectors.bilibili import BilibiliBlocked
from app.services.meme import discovery
from app.services.meme.certification import ENCYCLOPEDIA, GUIDE
from app.services.meme.discovery import PoolEntry, UpVideo, discover, extract_meme_name, index_by_meme, merge_pool


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """重试退避与翻页间隔在测试里没必要真等。"""
    monkeypatch.setattr(discovery.time, "sleep", lambda *_: None)
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def _ts(days: int) -> int:
    return int((datetime.now() - timedelta(days=days)).timestamp())


def _up(bvid: str, title: str, *, author, days: int, play: int = 100_000) -> UpVideo:
    return UpVideo(
        bvid=bvid, title=title, pubdate=datetime.fromtimestamp(_ts(days)),
        mid=author.mid, author=author.name, play=play,
    )


class FakeClient:
    """按 mid 返回投稿；blocked 里的 mid 每次调用都抛风控。"""

    def __init__(self, pages: dict[int, list[dict]], blocked: set[int] | None = None):
        self.pages = pages
        self.blocked = blocked or set()

    def space_videos(self, mid: int, *, page_size: int = 50, page: int = 1) -> list[dict]:
        if mid in self.blocked:
            raise BilibiliBlocked("测试用风控")
        return list(self.pages.get(mid) or [])


def _row(bvid: str, title: str, *, days: int, play: int = 100_000) -> dict:
    return {"bvid": bvid, "title": title, "created": _ts(days), "play": play}


# --------------------------------------------------------------------------- #
# 标题 → 梗名
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("【梗百科】闪身步是啥梗？", "闪身步"),
        ("老叟戏顽童是什么梗【梗指南】", "老叟戏顽童"),
        ("「牛来也」是什么梗【梗指南】", "牛来也"),
        ("宗主第二招：一句话解释是什么梗【梗指南】", "宗主第二招"),
        ("尴尬狗是什么来头", "尴尬狗"),
    ],
)
def test_extract_meme_name(title, expected):
    assert extract_meme_name(title) == expected


def test_extract_meme_name_gives_up_instead_of_guessing():
    """抽不出梗名就返回 None，绝不把整条标题当成梗名塞进库里。"""
    assert extract_meme_name("【梗百科】今天聊聊最近的热梗们") is None
    assert extract_meme_name("为什么最近大家都在玩梗") is None


# --------------------------------------------------------------------------- #
# 索引与并集
# --------------------------------------------------------------------------- #
def test_index_by_meme_keeps_the_latest_episode():
    index = index_by_meme([
        _up("BV1old", "闪身步是什么梗【梗指南】", author=GUIDE, days=80),
        _up("BV1new", "闪身步是什么梗【梗指南】", author=GUIDE, days=3),
    ])
    assert index["闪身步"].bvid == "BV1new", "90 天滚动窗口要拿最新一期当证据"


def test_merge_pool_is_union_and_puts_encyclopedia_first():
    enc = {
        "阿甲": _up("BV1e1", "阿甲是啥梗", author=ENCYCLOPEDIA, days=1),
        "阿丙": _up("BV1e2", "阿丙是啥梗", author=ENCYCLOPEDIA, days=5),
    }
    gui = {
        "阿乙": _up("BV1g1", "阿乙是什么梗", author=GUIDE, days=2),
        "阿丙": _up("BV1g2", "阿丙是什么梗", author=GUIDE, days=7),
    }

    pool, merged = merge_pool(enc, gui)

    assert [entry.key for entry in pool] == ["阿甲", "阿丙", "阿乙"], "主来源在前，再补另一位的"
    assert merged == []
    assert {entry.key: entry.cert_label for entry in pool} == {
        "阿甲": "梗百科认证", "阿丙": "双 UP 认证", "阿乙": "梗指南认证",
    }
    assert next(entry for entry in pool if entry.key == "阿乙").encyclopedia is None


def test_merge_pool_absorbs_writing_variants():
    """同一梗两种标题写法（"胆子肥嘟嘟" / "胆子肥嘟嘟的"）合成一条，不是两条。"""
    enc = {"胆子肥嘟嘟": _up("BV1e", "胆子肥嘟嘟是啥梗", author=ENCYCLOPEDIA, days=4)}
    gui = {"胆子肥嘟嘟的": _up("BV1g", "胆子肥嘟嘟的是什么梗", author=GUIDE, days=2)}

    pool, merged = merge_pool(enc, gui)

    assert len(pool) == 1 and merged == [("胆子肥嘟嘟", "胆子肥嘟嘟的")]
    assert pool[0].cert_label == "双 UP 认证"
    assert pool[0].guide.bvid == "BV1g", "合并后两边的证据都要留着"


def test_lookalike_names_are_not_merged():
    """只有互相包含才合并：像但不同的写法（牛来 / 闪身步）宁可留两条让人来看。"""
    enc = {"牛来": _up("BV1e", "牛来是啥梗", author=ENCYCLOPEDIA, days=4)}
    gui = {"闪身步": _up("BV1g", "闪身步是什么梗", author=GUIDE, days=2)}

    pool, merged = merge_pool(enc, gui)

    assert merged == [] and [entry.key for entry in pool] == ["牛来", "闪身步"]


def test_pool_entry_certified_by_order_is_stable():
    entry = PoolEntry("某梗", None, _up("BV1g", "某梗是什么梗", author=GUIDE, days=1))
    assert entry.certified_by == ["梗指南"]
    assert entry.name == "某梗是什么梗"
    assert entry.both is False


# --------------------------------------------------------------------------- #
# discover()：真实翻页 + 风控下的并集
# --------------------------------------------------------------------------- #
def test_discover_unions_both_authors():
    client = FakeClient({
        ENCYCLOPEDIA.mid: [
            _row("BV1e1", "【梗百科】闪身步是啥梗？", days=6),
            _row("BV1e2", "【梗百科】尴尬狗是什么来头", days=20),
        ],
        GUIDE.mid: [
            _row("BV1g1", "闪身步是什么梗【梗指南】", days=12),
            _row("BV1g2", "宗主第二招是什么梗【梗指南】", days=9),
        ],
    })

    report = discover(client, max_pages=1, gap=0, cert_days=90)

    assert [entry.key for entry in report.pool] == ["闪身步", "尴尬狗", "宗主第二招"]
    assert len(report.certified) == 1, "交集不再是闸门，但双 UP 标签仍然只看交集"
    assert report.double[0].key == "闪身步"
    assert sorted(report.single_sided) == sorted(["尴尬狗", "宗主第二招"])


def test_discover_ignores_videos_outside_the_rolling_window():
    client = FakeClient({
        ENCYCLOPEDIA.mid: [
            _row("BV1e1", "【梗百科】新近的梗是啥梗？", days=10),
            _row("BV1e2", "【梗百科】太老的梗是啥梗？", days=150),
        ],
        GUIDE.mid: [],
    })

    report = discover(client, max_pages=1, gap=0, cert_days=90)

    assert [entry.key for entry in report.pool] == ["新近的梗"]


def test_discover_still_builds_pool_when_one_up_is_blocked():
    """准入是并集，所以一位 UP 被风控不等于这轮没有梗。"""
    client = FakeClient(
        {ENCYCLOPEDIA.mid: [_row("BV1e1", "【梗百科】闪身步是啥梗？", days=6)]},
        blocked={GUIDE.mid},
    )

    report = discover(client, max_pages=1, gap=0, cert_days=90)

    assert [entry.key for entry in report.pool] == ["闪身步"]
    assert report.pool[0].cert_label == "梗百科认证"
    assert GUIDE.name in report.errors[0]


def test_discover_without_any_index_is_honestly_empty():
    client = FakeClient({}, blocked={ENCYCLOPEDIA.mid, GUIDE.mid})

    report = discover(client, max_pages=1, gap=0, cert_days=90)

    assert report.pool == [] and len(report.errors) == 2
