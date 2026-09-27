"""梗库去重：只报告、只删点名的、有真实证据的不许删。

这个脚本会 CASCADE 掉视频与序列，所以它的安全边界本身也得有测试。
"""

from __future__ import annotations

import pytest

from app.models import Meme, MemeDailyStats, Video
from app.scripts.dedupe_memes import duplicate_pairs, drop_memes, keeper_of, placeholder_rows
from app.services.meme.certification import record_certification

from .conftest import make_stats, make_video


def _byname(pairs):
    return {(a.name, b.name) for a, b in pairs} | {(b.name, a.name) for a, b in pairs}


def test_containment_pairs_are_found_and_lookalikes_are_not(session, meme_factory):
    meme_factory("胆子肥嘟嘟")
    meme_factory("胆子肥嘟嘟的")
    meme_factory("宗主第二招")
    meme_factory("宗主第一招")     # 像但不是互相包含：确实是两个梗，不许自动合
    meme_factory("网友随手造的梗")

    pairs = duplicate_pairs(list(session.query(Meme).order_by(Meme.id)))

    assert ("胆子肥嘟嘟", "胆子肥嘟嘟的") in _byname(pairs)
    assert ("宗主第一招", "宗主第二招") not in _byname(pairs)
    assert ("胆子肥嘟嘟", "网友随手造的梗") not in _byname(pairs)


def test_keeper_is_the_one_with_real_evidence(session, meme_factory):
    evidenced = meme_factory("牛来")
    record_certification(session, evidenced, "encyclopedia", bvid="BV1real", data_source="bilibili")
    hand_made = meme_factory("牛来也")

    keep, gone = keeper_of((hand_made, evidenced))

    assert keep.id == evidenced.id and gone.id == hand_made.id


def test_placeholder_shells_are_listed_only_when_they_have_no_data(session, meme_factory):
    """占位名（xx）搜不出内容；只有"一天数据都没采到"的才当空壳清理。"""
    shell = meme_factory("xx在哪？最优骑士小碎步")
    filled = meme_factory("你会xxx吗")
    for row in make_stats(filled.id, [10_000] * 3):
        session.add(row)
    session.flush()

    names = {meme.name for meme in placeholder_rows(session)}

    assert shell.name in names
    assert filled.name not in names, "采到过数据的条目不许当空壳删掉"


def test_drop_refuses_meme_with_evidence(session, meme_factory):
    real = meme_factory("琵琶曲")
    record_certification(session, real, "guide", bvid="BV1real2", data_source="bilibili")

    with pytest.raises(SystemExit):
        drop_memes(session, [real.id])


def test_drop_removes_rows_and_cascades(session, meme_factory):
    dupe = meme_factory("胆子真的肥嘟嘟的")
    for row in make_stats(dupe.id, [10_000] * 3, end=None):
        session.add(row)
    session.add(make_video("BV1dupe", "胆子真的肥嘟嘟的 测试", meme_id=dupe.id))
    session.flush()

    removed = drop_memes(session, [dupe.id])

    assert removed == ["胆子真的肥嘟嘟的"]
    assert session.query(Meme).filter_by(id=dupe.id).count() == 0
    assert session.query(MemeDailyStats).filter_by(meme_id=dupe.id).count() == 0
    assert session.query(Video).filter_by(bvid="BV1dupe").count() == 0
