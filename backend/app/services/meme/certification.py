"""双 UP 梗认证规则。

两个 B 站梗解释 UP 主是本项目唯一认可的"梗来源"：

* 梗百科  https://space.bilibili.com/1544008396
* 梗指南  https://space.bilibili.com/94510621

只有两者都独立发视频介绍过同一个梗，该梗才进入正式梗库。
本模块是这条规则的唯一实现处：写入认证证据 -> 重算 certified -> 决定 status。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import CertRole, Meme, MemeCertification, MemeStatus

log = get_logger(__name__)


@dataclass(frozen=True)
class UpAuthor:
    role: str
    mid: int
    name: str
    space_url: str

    @property
    def profile_url(self) -> str:
        return self.space_url


ENCYCLOPEDIA = UpAuthor(
    role=CertRole.ENCYCLOPEDIA,
    mid=1544008396,
    name="梗百科",
    space_url="https://space.bilibili.com/1544008396",
)

GUIDE = UpAuthor(
    role=CertRole.GUIDE,
    mid=94510621,
    name="梗指南",
    space_url="https://space.bilibili.com/94510621",
)

UP_AUTHORS: dict[str, UpAuthor] = {ENCYCLOPEDIA.role: ENCYCLOPEDIA, GUIDE.role: GUIDE}
AUTHOR_MIDS: dict[int, str] = {author.mid: author.role for author in UP_AUTHORS.values()}


class NotCertifiedError(RuntimeError):
    """梗未通过双 UP 认证，禁止进入正式分析。"""


def role_for_mid(mid: int) -> str | None:
    return AUTHOR_MIDS.get(int(mid))


def get_or_create_certification(
    session: Session,
    meme: Meme,
    role: str,
) -> MemeCertification:
    if role not in UP_AUTHORS:
        raise ValueError(f"unknown certification role: {role}")
    author = UP_AUTHORS[role]
    existing = session.scalar(
        select(MemeCertification).where(
            MemeCertification.meme_id == meme.id, MemeCertification.role == role
        )
    )
    if existing:
        return existing
    cert = MemeCertification(
        meme_id=meme.id,
        role=role,
        up_name=author.name,
        up_mid=author.mid,
        confirmed=False,
    )
    session.add(cert)
    # 通过关系挂载，保证同一事务内 recompute 能立刻看到新证据
    if not any(c is cert for c in meme.certifications):
        meme.certifications.append(cert)
    return cert


def record_certification(
    session: Session,
    meme: Meme,
    role: str,
    *,
    bvid: str = "",
    video_title: str = "",
    published_at: datetime | None = None,
    confirmed: bool = True,
    data_source: str = "mock",
) -> Meme:
    """登记某个 UP 主介绍过该梗的证据，并重算认证结果。"""
    author = UP_AUTHORS[role]
    cert = get_or_create_certification(session, meme, role)
    cert.bvid = bvid or cert.bvid
    cert.video_title = video_title or cert.video_title
    cert.published_at = published_at or cert.published_at
    cert.confirmed = bool(confirmed)
    cert.up_name = author.name
    cert.up_mid = author.mid
    cert.data_source = data_source
    if confirmed and cert.confirmed_at is None:
        cert.confirmed_at = datetime.now()

    recompute_certification(meme)
    session.flush()
    return meme


def recompute_certification(meme: Meme) -> Meme:
    """``certified = encyclopedia_confirmed AND guide_confirmed``。"""
    certs = {c.role: c for c in meme.certifications}
    encyclopedia = certs.get(CertRole.ENCYCLOPEDIA)
    guide = certs.get(CertRole.GUIDE)

    meme.encyclopedia_confirmed = bool(encyclopedia and encyclopedia.confirmed)
    meme.guide_confirmed = bool(guide and guide.confirmed)
    newly_certified = meme.encyclopedia_confirmed and meme.guide_confirmed

    if newly_certified and not meme.certified:
        meme.certified_at = datetime.now()
    if not newly_certified:
        meme.certified_at = None

    meme.certified = bool(newly_certified)
    if meme.certified:
        meme.status = MemeStatus.CERTIFIED
    elif meme.status == MemeStatus.CERTIFIED:
        meme.status = MemeStatus.CANDIDATE
    else:
        meme.status = meme.status or MemeStatus.CANDIDATE
    return meme


def require_certified(meme: Meme) -> None:
    """分析管线入口守卫：未认证梗不得参与热度/生命周期计算。"""
    if not meme.certified:
        raise NotCertifiedError(
            f"梗「{meme.name}」未通过双 UP 认证"
            f"（梗百科={meme.encyclopedia_confirmed}, 梗指南={meme.guide_confirmed}）"
        )


def certification_progress(meme: Meme) -> dict[str, object]:
    """给前端展示的双 UP 认证状态。"""
    return {
        "encyclopedia": {
            "up_name": ENCYCLOPEDIA.name,
            "confirmed": meme.encyclopedia_confirmed,
            **(meme.encyclopedia.to_dict() if meme.encyclopedia else {}),
        },
        "guide": {
            "up_name": GUIDE.name,
            "confirmed": meme.guide_confirmed,
            **(meme.guide.to_dict() if meme.guide else {}),
        },
        "certified": meme.certified,
        "certified_at": meme.certified_at.isoformat() if meme.certified_at else None,
    }
