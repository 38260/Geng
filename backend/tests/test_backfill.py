"""回填脚本只比较"同一天谁采得更多"，不许相加、不许改梗、不许动别的数据源。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Meme, MemeDailyStats
from app.scripts.backfill_days import apply_plan, build_plan, snapshot_stats
from app.services.pipeline import split_daily_stats

FIELDS = ("video_count", "creator_count", "view", "like", "coin", "favorite", "reply", "danmaku")


def _stats(meme_id: int, days: dict[date, tuple[int, int]], source: str = "bilibili"):
    out = []
    for stat_date, (video_count, view) in days.items():
        out.append(
            MemeDailyStats(
                meme_id=meme_id, stat_date=stat_date, data_source=source,
                video_count=video_count, creator_count=1, view=view,
                like=view // 10, coin=view // 40, favorite=view // 20,
                reply=view // 50, danmaku=view // 30,
            )
        )
    return out


@pytest.fixture()
def snapshot_db(tmp_path):
    """另开一个 SQLite 文件当"历史快照"，只用来读。"""
    path = tmp_path / "snap.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    yield path, maker
    engine.dispose()


def _fill(maker, name: str, days: dict[date, tuple[int, int]], source: str = "bilibili") -> None:
    db = maker()
    try:
        meme = Meme(name=name, slug=f"snap-{name}")
        db.add(meme)
        db.flush()
        for row in _stats(meme.id, days, source):
            db.add(row)
        db.commit()
    finally:
        db.close()


def test_only_days_the_snapshot_observed_better_are_planned(session, meme_factory, snapshot_db):
    path, maker = snapshot_db
    day_a = date.today() - timedelta(days=3)
    day_b = date.today() - timedelta(days=2)

    meme = meme_factory("琵琶曲回填样本")
    for row in _stats(meme.id, {day_a: (1, 10_000), day_b: (20, 900_000)}):
        session.add(row)
    session.flush()

    _fill(maker, "琵琶曲回填样本", {day_a: (18, 3_900_000), day_b: (4, 50_000)})
    plan = build_plan(session, snapshot_stats(path, "bilibili"), "bilibili")

    assert [(item["name"], item["day"], item["action"]) for item in plan] == [("琵琶曲回填样本", day_a, "update")]
    assert plan[0]["before"] == (1, 10_000) and plan[0]["after"] == (18, 3_900_000)


def test_apply_replaces_the_day_instead_of_adding_to_it(session, meme_factory, snapshot_db):
    path, maker = snapshot_db
    day_a = date.today() - timedelta(days=5)
    meme = meme_factory("肥嘟嘟回填样本")
    for row in _stats(meme.id, {day_a: (2, 20_000)}):
        session.add(row)
    session.flush()

    _fill(maker, "肥嘟嘟回填样本", {day_a: (20, 4_000_000)})
    plan = build_plan(session, snapshot_stats(path, "bilibili"), "bilibili")
    written = apply_plan(session, plan, "bilibili")

    rows = list(session.query(MemeDailyStats).filter_by(meme_id=meme.id))
    assert written == 1 and len(rows) == 1
    assert rows[0].view == 4_000_000 and rows[0].video_count == 20, "同日覆盖，不是相加"


def test_missing_meme_in_live_library_is_not_created(session, meme_factory, snapshot_db):
    path, maker = snapshot_db
    _fill(maker, "库里没有的梗", {date.today() - timedelta(days=1): (10, 100_000)})

    plan = build_plan(session, snapshot_stats(path, "bilibili"), "bilibili")

    assert [item for item in plan if item["name"] == "库里没有的梗"] == []
    assert session.query(Meme).filter_by(name="库里没有的梗").count() == 0


def test_pipeline_keeps_the_better_day_too(session, meme_factory):
    """管线里的规则与回填脚本同源：新采的那天更薄就留着旧的，其余照常更新。"""
    day_old = date.today() - timedelta(days=4)
    day_new = date.today() - timedelta(days=1)
    meme = meme_factory("野生狗奶", encyclopedia_confirmed=True, guide_confirmed=True, certified=True)
    for row in _stats(meme.id, {day_old: (20, 1_200_000)}):
        session.add(row)
    session.flush()

    incoming = _stats(meme.id, {day_old: (1, 9_000), day_new: (7, 90_000)})
    kept, reuse = split_daily_stats(session, meme, incoming, "bilibili")

    assert reuse == 1
    assert [row.stat_date for row in kept] == [day_new], "更薄的那天不该写回去"
