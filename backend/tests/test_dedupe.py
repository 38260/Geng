"""梗库去重：只报告、只删点名的、有真实证据的不许删。

这个脚本会 CASCADE 掉视频与序列，所以它的安全边界本身也得有测试。
测试里的梗名都带模块前缀：整个测试跑在同一个内存库上，重名会撞 UNIQUE。
"""

from __future__ import annotations

import pytest

from app.models import Meme, MemeDailyStats, Video
from app.scripts.dedupe_memes import (
    duplicate_pairs,
    drop_memes,
    keeper_of,
    placeholder_rows,
    similar_pairs,
)
from app.services.meme.certification import record_certification

from .conftest import make_stats, make_video


def _names(pairs):
    return {(a.name, b.name) for a, b in pairs} | {(b.name, a.name) for a, b in pairs}


def _all(session) -> list[Meme]:
    return list(session.query(Meme).order_by(Meme.id))


def test_containment_pairs_are_found_and_lookalikes_are_not(session, meme_factory):
    meme_factory("去重甲梗")
    meme_factory("去重甲梗延伸")
    meme_factory("去重宗主第一招")
    meme_factory("去重宗主第二招")     # 像但不是互相包含：确实是两个梗，不许自动合
    meme_factory("去重无关梗")

    pairs = duplicate_pairs(_all(session))

    assert ("去重甲梗", "去重甲梗延伸") in _names(pairs)
    assert ("去重宗主第一招", "去重宗主第二招") not in _names(pairs)


def test_near_duplicates_are_reported_but_never_auto_merged(session, meme_factory):
    """只差一个字的条目要报出来给人看，但脚本里没有任何自动合并路径。"""
    meme_factory("近似胆子真的肥嘟嘟")
    meme_factory("近似胆子真是肥嘟嘟")

    pairs = similar_pairs(_all(session))

    assert ("近似胆子真的肥嘟嘟", "近似胆子真是肥嘟嘟") in _names(pairs)


def test_keeper_is_the_one_with_real_evidence(session, meme_factory):
    evidenced = meme_factory("去重牛来")
    record_certification(session, evidenced, "encyclopedia", bvid="BV1dedupe1", data_source="bilibili")
    hand_made = meme_factory("去重牛来也")

    keep, gone = keeper_of((hand_made, evidenced))

    assert keep.id == evidenced.id and gone.id == hand_made.id


def test_placeholder_shells_are_listed_only_when_they_have_no_data(session, meme_factory):
    """占位名（xx）搜不出内容；只有"一天数据都没采到"的才当空壳清理。"""
    shell = meme_factory("去重xx在哪")
    filled = meme_factory("去重你会xx吗")
    for row in make_stats(filled.id, [10_000] * 3):
        session.add(row)
    session.flush()

    names = {meme.name for meme in placeholder_rows(session)}

    assert shell.name in names
    assert filled.name not in names, "采到过数据的条目不许当空壳删掉"


def test_drop_refuses_meme_with_evidence(session, meme_factory):
    real = meme_factory("去重琵琶曲")
    record_certification(session, real, "guide", bvid="BV1dedupe2", data_source="bilibili")

    with pytest.raises(SystemExit):
        drop_memes(session, [real.id])


def test_drop_removes_rows_and_cascades(session, meme_factory):
    dupe = meme_factory("去重胆子真的肥嘟嘟的")
    for row in make_stats(dupe.id, [10_000] * 3):
        session.add(row)
    session.add(make_video("BV1dedupe3", "去重胆子真的肥嘟嘟的 测试", meme_id=dupe.id))
    session.flush()

    removed = drop_memes(session, [dupe.id])

    assert removed == ["去重胆子真的肥嘟嘟的"]
    assert session.query(Meme).filter_by(id=dupe.id).count() == 0
    assert session.query(MemeDailyStats).filter_by(meme_id=dupe.id).count() == 0
    assert session.query(Video).filter_by(bvid="BV1dedupe3").count() == 0
