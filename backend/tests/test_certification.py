"""双 UP 认证是数据模型的硬约束，这里把闸门本身测掉。"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import CertRole, MemeStatus
from app.services.meme.certification import (
    NotCertifiedError,
    record_certification,
    recompute_certification,
    require_certified,
)
from app.services.pipeline import recompute_meme

from .conftest import make_stats


def test_single_up_is_not_certified(meme_factory, session):
    meme = meme_factory()
    record_certification(session, meme, CertRole.ENCYCLOPEDIA, bvid="BV1enc0001")

    assert meme.encyclopedia_confirmed is True
    assert meme.guide_confirmed is False
    assert meme.certified is False
    assert meme.status == MemeStatus.CANDIDATE
    with pytest.raises(NotCertifiedError):
        require_certified(meme)


def test_both_up_certifies(meme_factory, session):
    meme = meme_factory()
    record_certification(session, meme, CertRole.ENCYCLOPEDIA, bvid="BV1enc0002")
    record_certification(session, meme, CertRole.GUIDE, bvid="BV1gui0002")

    assert meme.certified is True
    assert meme.status == MemeStatus.CERTIFIED
    assert meme.certified_at is not None
    require_certified(meme)  # 不抛异常


def test_revoking_one_side_uncertifies(meme_factory, session):
    meme = meme_factory()
    record_certification(session, meme, CertRole.ENCYCLOPEDIA, bvid="BV1enc0003")
    record_certification(session, meme, CertRole.GUIDE, bvid="BV1gui0003")
    assert meme.certified

    guide = next(c for c in meme.certifications if c.role == CertRole.GUIDE)
    guide.confirmed = False
    recompute_certification(meme)

    assert meme.certified is False
    assert meme.certified_at is None
    assert meme.status == MemeStatus.CANDIDATE


def test_pipeline_refuses_uncertified_meme(meme_factory, session):
    meme = meme_factory()
    record_certification(session, meme, CertRole.ENCYCLOPEDIA, bvid="BV1enc0004")
    for row in make_stats(meme.id, [50_000] * 30, end=date.today()):
        session.add(row)
    session.flush()

    assert recompute_meme(session, meme) is None
    assert meme.status == MemeStatus.CANDIDATE


def test_unknown_role_rejected(meme_factory, session):
    meme = meme_factory()
    with pytest.raises(ValueError):
        record_certification(session, meme, "抖音", bvid="BV1x")
