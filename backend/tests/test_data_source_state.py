# -*- coding: utf-8 -*-
"""新梗的来源状态：必须是显式的 pending，不能是空串。

来历：库里曾经积了 11 条 ``data_source=''`` 的梗（见 docs/改进建议.md B2）。
空串是第三种"无来源"状态——既不是 ``bilibili`` 也不是 ``mock``，
于是既进不了真实榜单、也拿不到「演示数据」标注，界面上无从解释。
"""

from __future__ import annotations

from app.models import Meme, SessionLocal
from app.services.meme.manage import create_meme, meme_view
from app.models.meme import MemeStatus


def test_created_meme_has_explicit_pending_source(session):
    payload = {"name": "来源状态测试梗", "description": "验证 pending 落库"}
    created = create_meme(session, payload)
    meme_id = created["meme"]["id"]

    raw = session.get(Meme, meme_id)
    assert raw.data_source == "pending", (
        f"新建梗的 data_source 落库为 {raw.data_source!r}；"
        "空串会让这条梗既不像真实数据也不像演示数据"
    )
    assert meme_view(session, raw)["data_source"] == "pending"


def test_no_meme_has_an_empty_source(session):
    """整库不允许出现空串来源。"""
    from sqlalchemy import or_, select

    bad = list(session.scalars(
        select(Meme).where(or_(Meme.data_source.is_(None), Meme.data_source == ""))))
    assert not bad, f"仍有 {len(bad)} 条梗的 data_source 为空：{[m.name for m in bad][:5]}"


def test_pending_source_is_not_treated_as_demo(session):
    """pending 是"已入池、等采集"，不是演示数据——不该被 scope=real 跳过。"""
    from app.services.pipeline import _demo_only_ids

    meme = Meme(name="待采集梗", slug="pending-source-test", status=MemeStatus.CANDIDATE,
                certified=False, verification_state="unverified", data_source="pending")
    session.add(meme)
    session.flush()

    assert meme.id not in _demo_only_ids(session), (
        "pending 来源的梗被当成纯演示梗跳过了，它会永远采不到数据"
    )


def test_mock_label_with_real_series_is_relabelled_not_deleted(session):
    """标着 mock、但库里已经躺着 B 站真实日统计的梗：错的是标签，不是数据。

    「你干嘛哎哟」就是这么一条——30 天真实序列，标签还停在演示时代。
    删它会丢掉真数据，留着错标签又会让它被"纯演示梗"判定误伤。
    """
    from datetime import date

    from app.models import MemeDailyStats
    from app.scripts.fix_data_source_state import _mislabelled, main

    meme = Meme(name="标签错梗", slug="mislabel-src", data_source="mock",
                status=MemeStatus.CERTIFIED)
    session.add(meme)
    session.flush()
    session.add(MemeDailyStats(meme_id=meme.id, stat_date=date.today(),
                               video_count=1, view=100, data_source="bilibili"))
    session.commit()

    # 只断言"这一只在待修列表里"：测试库是全 suite 共享的内存库，
    # 别的用例也会留下同类 mock+真实数据的梗，断言整个列表相等就是给自己埋隔离坑
    # （第一版就是这么写的，单独跑过、全量跑就红）。
    assert meme.name in [m.name for m in _mislabelled(session)], \
        "该被认成「标签错」而不是「演示数据」"

    main(["--apply"])
    session.expire_all()
    assert session.get(Meme, meme.id).data_source == "bilibili"
    assert session.query(MemeDailyStats).filter_by(meme_id=meme.id).count() == 1, \
        "真实数据一行都不许被顺手删掉"
    assert meme.name not in [m.name for m in _mislabelled(session)], \
        "改完就不该再出现在待修列表里"
