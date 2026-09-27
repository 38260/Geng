"""发现层准入（并集）与认证徽章（交集）是两层规则，这里把两层都测掉。

旧口径是"双 UP 交集才算入池"，实测 90 天里交集只有 8 个梗、梗百科单独就有 37 个，
门槛设错了会直接把正在热的梗挡在外面。所以这里专门有：
* 单 UP 也能入池、也能被算分；
* 但 ``certified``（双 UP 徽章）仍然是 AND，标签不会跟着准入放水。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import CertRole, MemeStatus
from app.services.meme.certification import (
    NotCertifiedError,
    admitted,
    cert_label,
    certified_by,
    record_certification,
    recompute_certification,
    require_certified,
)
from app.services.pipeline import recompute_meme

from .conftest import make_stats


def test_single_up_enters_the_pool(meme_factory, session):
    """并集准入：只有梗百科做过也入池，但徽章只是"梗百科认证"。"""
    meme = meme_factory()
    record_certification(session, meme, CertRole.ENCYCLOPEDIA, bvid="BV1enc0001")

    assert meme.encyclopedia_confirmed is True
    assert meme.guide_confirmed is False
    assert admitted(meme) is True
    assert meme.status == MemeStatus.CERTIFIED
    assert meme.certified is False, "准入是并集，但双 UP 徽章依旧是交集"
    assert cert_label(meme) == "梗百科认证"
    assert certified_by(meme) == ["梗百科"]
    require_certified(meme)  # 入池即允许分析，不抛异常


def test_guide_only_also_enters(meme_factory, session):
    meme = meme_factory()
    record_certification(session, meme, CertRole.GUIDE, bvid="BV1gui0009")

    assert admitted(meme) is True
    assert cert_label(meme) == "梗指南认证"


def test_both_up_certifies(meme_factory, session):
    meme = meme_factory()
    record_certification(session, meme, CertRole.ENCYCLOPEDIA, bvid="BV1enc0002")
    record_certification(session, meme, CertRole.GUIDE, bvid="BV1gui0002")

    assert meme.certified is True
    assert meme.status == MemeStatus.CERTIFIED
    assert meme.certified_at is not None
    assert cert_label(meme) == "双 UP 认证"
    assert certified_by(meme) == ["梗百科", "梗指南"]
    require_certified(meme)  # 不抛异常


def test_no_up_at_all_stays_out_of_the_pool(meme_factory, session):
    meme = meme_factory()

    assert admitted(meme) is False
    assert meme.status == MemeStatus.CANDIDATE
    assert cert_label(meme) == "未认证"
    with pytest.raises(NotCertifiedError):
        require_certified(meme)


def test_revoking_one_side_keeps_pool_but_loses_the_badge(meme_factory, session):
    meme = meme_factory()
    record_certification(session, meme, CertRole.ENCYCLOPEDIA, bvid="BV1enc0003")
    record_certification(session, meme, CertRole.GUIDE, bvid="BV1gui0003")
    assert meme.certified

    guide = next(c for c in meme.certifications if c.role == CertRole.GUIDE)
    guide.confirmed = False
    recompute_certification(meme)

    assert meme.certified is False
    assert meme.certified_at is None
    assert admitted(meme) is True, "掉一边只掉徽章，不该把梗踢出池子"
    assert meme.status == MemeStatus.CERTIFIED


def test_verification_state_follows_real_evidence(meme_factory, session):
    """在线核验状态只认"真实抓到的投稿"：演示自证的 confirmed 不算证据。"""
    demo = meme_factory()
    record_certification(session, demo, CertRole.ENCYCLOPEDIA, bvid="BV1fake")
    record_certification(session, demo, CertRole.GUIDE, bvid="BV1fake2")
    assert demo.certified is True
    assert demo.verification_state == "unverified", "演示证据不能冒充已核验"

    single = meme_factory()
    record_certification(session, single, CertRole.ENCYCLOPEDIA, bvid="BV1real", data_source="bilibili")
    assert single.verification_state == "partially_verified"

    both = meme_factory()
    record_certification(session, both, CertRole.ENCYCLOPEDIA, bvid="BV1real3", data_source="bilibili")
    record_certification(session, both, CertRole.GUIDE, bvid="BV1real4", data_source="bilibili")
    assert both.verification_state == "verified_both"


def test_pipeline_computes_single_up_meme(meme_factory, session):
    """入池的梗必须真的能被算出来——准入放宽了却不能只改标签不改管线。"""
    meme = meme_factory()
    record_certification(session, meme, CertRole.ENCYCLOPEDIA, bvid="BV1enc0004")
    for row in make_stats(meme.id, [50_000] * 30, end=date.today()):
        session.add(row)
    session.flush()

    assert recompute_meme(session, meme) is not None
    assert meme.status == MemeStatus.CERTIFIED


def test_pipeline_refuses_out_of_pool_meme(meme_factory, session):
    meme = meme_factory()
    for row in make_stats(meme.id, [50_000] * 30, end=date.today()):
        session.add(row)
    session.flush()

    assert recompute_meme(session, meme) is None
    assert meme.status == MemeStatus.CANDIDATE


def test_unknown_role_rejected(meme_factory, session):
    meme = meme_factory()
    with pytest.raises(ValueError):
        record_certification(session, meme, "抖音", bvid="BV1x")


def test_recompute_withdraws_snapshot_when_series_is_gone(meme_factory, session):
    """序列被清空之后，不能继续挂着上一版的分数留在榜单上。"""
    from app.models import HotnessSnapshot, LifecycleSnapshot, MemeDailyStats

    meme = meme_factory(
        certified=True,
        status=MemeStatus.CERTIFIED,
        encyclopedia_confirmed=True,
        guide_confirmed=True,
    )
    for row in make_stats(meme.id, [50_000] * 30, end=date.today()):
        session.add(row)
    session.flush()
    assert recompute_meme(session, meme) is not None
    session.flush()
    assert session.query(HotnessSnapshot).filter_by(meme_id=meme.id).count() == 1

    session.query(MemeDailyStats).filter(MemeDailyStats.meme_id == meme.id).delete()
    session.flush()

    assert recompute_meme(session, meme) is None
    assert session.query(HotnessSnapshot).filter_by(meme_id=meme.id).count() == 0
    assert session.query(LifecycleSnapshot).filter_by(meme_id=meme.id).count() == 0
