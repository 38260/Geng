"""清 mock 数据：删假证据、按真证据重推认证，且**不误伤真数据**。

这个脚本是破坏性的，所以守两条：

1. 默认（不带 ``--apply``）**一行都不删**；
2. 删的只是 ``data_source='mock'`` 的子表行——真实视频与逐日序列一条不动，
   只有假证据的梗退回 ``candidate``，它的真实数据仍留在库里。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import Meme, MemeCertification, MemeDailyStats, Video
from app.scripts.purge_mock_data import (
    _affected_ids,
    _mock_counts,
    _sqlite_path,
    main,
    purge,
)
from app.services.meme.certification import cert_label

from .conftest import make_video


def _meme(session, name: str, **kwargs) -> Meme:
    meme = Meme(name=name, slug=f"purge-{name}", aliases=[], keywords=[name], **kwargs)
    session.add(meme)
    session.flush()
    return meme


def _cert(session, meme: Meme, role: str, *, source: str, days_ago: int = 30) -> None:
    session.add(
        MemeCertification(
            meme_id=meme.id,
            role=role,
            up_name="梗百科" if role == "encyclopedia" else "梗指南",
            up_mid=1544008396 if role == "encyclopedia" else 94510621,
            bvid=f"BV{meme.id:04d}{role[:3]}",
            video_title=f"{meme.name}是什么梗",
            published_at=datetime.now() - timedelta(days=days_ago),
            confirmed=True,
            data_source=source,
        )
    )
    session.flush()


def _real_video(session, meme: Meme) -> None:
    # 用 conftest 的工厂：videos.publish_time 是 NOT NULL，手拼会踩约束
    session.add(
        make_video(
            f"BV{meme.id:04d}real",
            f"{meme.name} 相关",
            author="某UP",
            view=12345,
            meme_id=meme.id,
            data_source="bilibili",
        )
    )
    session.flush()


def _mock_only(session) -> Meme:
    """只有假证据、但视频是真采集来的梗（当前库里那 28 只就是这种形态）。"""
    meme = _meme(session, "只有假证据梗", status="certified", certified=True, data_source="bilibili")
    _cert(session, meme, "encyclopedia", source="mock")
    _cert(session, meme, "guide", source="mock")
    _real_video(session, meme)
    session.flush()
    return meme


def _stub(session, monkeypatch):
    """把脚本的会话与危险动作换掉，只观察控制流。

    注意：`main()` 的 finally 会 `session.close()`，而 close 会回滚未提交的事务——
    所以**每个用例只能调一次 main()**，调两次第二次就看不到 fixture 数据了。
    """
    import app.scripts.purge_mock_data as mod

    called: list[list[int]] = []
    monkeypatch.setattr(mod, "SessionLocal", lambda: session)
    monkeypatch.setattr(mod, "_simulate_after", lambda s, ids: 0)
    monkeypatch.setattr(mod, "purge", lambda s, ids: called.append(ids) or 0)
    return mod, called


def test_dry_run_never_calls_purge(session, monkeypatch):
    """不带 ``--apply`` → 一行都不删：``purge`` 根本不许被调用。"""
    mod, called = _stub(session, monkeypatch)
    _mock_only(session)

    assert mod.main([]) == 0
    assert called == [], "预演里不允许调用 purge"


def test_apply_refuses_to_delete_without_a_backup_target(session, monkeypatch):
    """认不出库文件（内存库/非 SQLite）→ 返回 2 中止，**绝不"裸删不备份"**。"""
    mod, called = _stub(session, monkeypatch)
    _mock_only(session)

    assert mod.main(["--apply"]) == 2
    assert called == [], "中止之后更不许删"


def test_purge_demotes_and_keeps_real_data(session):
    meme = _mock_only(session)
    ids = _affected_ids(session)
    assert meme.id in ids
    assert _mock_counts(session)["meme_certifications"] >= 2

    removed = purge(session, ids)
    assert removed >= 2

    # 假证据没了 → 认证/准入按真实行重推：退回候选
    session.expire_all()
    fresh = session.get(Meme, meme.id)
    assert fresh.encyclopedia_confirmed is False
    assert fresh.guide_confirmed is False
    assert fresh.certified is False
    assert fresh.status == "candidate"
    assert cert_label(fresh) == "未认证"

    # 但真实数据一条都不能少
    assert session.scalar(
        select(func.count()).select_from(Video).where(Video.meme_id == meme.id)
    ) == 1
    assert _mock_counts(session) == {k: 0 for k in _mock_counts(session)}


def test_real_evidence_wins_when_mock_is_removed(session):
    """一边真、一边假：删掉假的那边，梗仍应靠真实那边保持认证。"""
    meme = _meme(session, "半真半假梗", status="certified", certified=True, data_source="bilibili")
    _cert(session, meme, "encyclopedia", source="bilibili")
    _cert(session, meme, "guide", source="mock")
    _real_video(session, meme)
    session.flush()

    purge(session, [meme.id])
    session.expire_all()
    fresh = session.get(Meme, meme.id)
    assert fresh.encyclopedia_confirmed is True
    assert fresh.guide_confirmed is False
    assert fresh.certified is False                 # 双 UP 徽章掉了
    assert fresh.status == "certified"              # 但准入还在（并集）
    assert cert_label(fresh) == "梗百科认证"


def test_purge_never_touches_real_rows(session):
    meme = _meme(session, "全真梗", status="certified", certified=True, data_source="bilibili")
    _cert(session, meme, "encyclopedia", source="bilibili")
    _cert(session, meme, "guide", source="bilibili")
    _real_video(session, meme)
    session.add(
        MemeDailyStats(meme_id=meme.id, stat_date=datetime.now().date(), view=100, data_source="bilibili")
    )
    session.flush()

    purge(session, [meme.id])
    session.expire_all()
    fresh = session.get(Meme, meme.id)
    assert fresh.certified is True
    assert fresh.status == "certified"
    assert session.scalar(
        select(func.count()).select_from(MemeDailyStats).where(MemeDailyStats.meme_id == meme.id)
    ) == 1


def test_backup_target_is_unresolvable_for_in_memory_db(session):
    """内存库认不出文件路径 → ``--apply`` 会中止，绝不"裸删不备份"。"""
    path = _sqlite_path()
    assert path is None or not path.exists()
