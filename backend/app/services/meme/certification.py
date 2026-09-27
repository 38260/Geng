"""梗库准入（发现层）与双 UP 认证标签。

两位 B 站梗解释 UP 主是本项目唯一认可的"梗来源"：

* 梗百科  https://space.bilibili.com/1544008396   ← 主来源（更新勤、覆盖广）
* 梗指南  https://space.bilibili.com/94510621     ← 补充来源

规则分两层，别混为一谈：

* **发现层（准入）**：任一 UP 主在 90 天滚动窗口内真实介绍过 → 入池，采集、算分、上榜。
  早期版本取的是两位 UP 的交集，实测 90 天里交集只有 8 个梗，而梗百科单独就有 37 个
  ——用交集当门槛，等于让一个日更 UP 的选题被一个周更 UP 的排期 veto 掉，梗库必然漏。
* **认证层（标签）**：``certified = 梗百科 AND 梗指南``，表示"两位都独立做过"，
  是可信度徽章而不是准入门槛。榜单卡片会如实显示"双 UP 认证 / 梗百科认证 / 梗指南认证"。

本模块是这两条规则的唯一实现处：写入证据 -> 重算 certified/admitted -> 决定 status。
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
    """梗未通过发现层准入：两位 UP 主都没有真实介绍过，禁止入池分析。"""


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
    if role not in UP_AUTHORS:
        raise ValueError(f"unknown certification role: {role}")
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
    """重算两层结论：``certified``（双 UP 徽章）与准入（status/verification_state）。

    ``certified = encyclopedia_confirmed AND guide_confirmed`` 仍然是"两位都独立做过"，
    只是可信度徽章；进不进梗库看的是 :func:`admitted`（任一 UP 介绍过即可）。
    """
    certs = {c.role: c for c in meme.certifications}
    encyclopedia = certs.get(CertRole.ENCYCLOPEDIA)
    guide = certs.get(CertRole.GUIDE)

    meme.encyclopedia_confirmed = bool(encyclopedia and encyclopedia.confirmed)
    meme.guide_confirmed = bool(guide and guide.confirmed)
    both = meme.encyclopedia_confirmed and meme.guide_confirmed

    if both and not meme.certified:
        meme.certified_at = datetime.now()
    if not both:
        meme.certified_at = None

    meme.certified = bool(both)
    # 在线核验状态只由"真实抓到的投稿"决定：演示数据自记自认的 confirmed 不算证据。
    # 这样榜单闸门（require_verified）能自动把演示梗挡在外面，
    # 而单 UP 的真梗会如实落在 partially_verified。
    real_roles = {
        c.role for c in meme.certifications if c.confirmed and c.data_source == "bilibili"
    }
    if real_roles:
        meme.verification_state = (
            "verified_both" if len(real_roles) >= 2 else "partially_verified"
        )

    if admitted(meme):
        meme.status = MemeStatus.CERTIFIED
    elif meme.status == MemeStatus.CERTIFIED:
        meme.status = MemeStatus.CANDIDATE
    else:
        meme.status = meme.status or MemeStatus.CANDIDATE
    return meme


def admitted(meme: Meme) -> bool:
    """发现层准入：任一 UP 主介绍过即可进池（梗百科为主，梗指南补）。"""
    return bool(meme.encyclopedia_confirmed or meme.guide_confirmed)


def certified_by(meme: Meme) -> list[str]:
    """给出该梗证据来源的 UP 主名，顺序固定为"梗百科、梗指南"。"""
    names: list[str] = []
    if meme.encyclopedia_confirmed:
        names.append(ENCYCLOPEDIA.name)
    if meme.guide_confirmed:
        names.append(GUIDE.name)
    return names


def cert_label(meme: Meme) -> str:
    """认证强度标签：双 UP 认证 > 单 UP 认证（写明是哪一位）。"""
    if meme.encyclopedia_confirmed and meme.guide_confirmed:
        return "双 UP 认证"
    if meme.encyclopedia_confirmed:
        return f"{ENCYCLOPEDIA.name}认证"
    if meme.guide_confirmed:
        return f"{GUIDE.name}认证"
    return "未认证"


def analysis_allowed(meme: Meme) -> bool:
    """该梗能否参与热度/生命周期计算 = 能否进池。

    发现层口径（并集）：任一 UP 主真实介绍过就允许算。
    在线核验被风控挡住时，允许人工整理的候选梗参与分析（ANALYSIS_ALLOW_UNVERIFIED 控制），
    但状态会一路带到前端如实标注，不会伪装成已核验。
    """
    from app.config import settings

    if admitted(meme):
        return True
    return bool(settings.analysis_allow_unverified) and meme.status == MemeStatus.CERTIFIED


def require_certified(meme: Meme) -> None:
    """分析管线入口守卫：两位 UP 都没介绍过的梗不得参与热度/生命周期计算。"""
    if analysis_allowed(meme):
        return
    raise NotCertifiedError(
        f"梗「{meme.name}」两位 UP 主都没有介绍过"
        f"（梗百科={meme.encyclopedia_confirmed}, 梗指南={meme.guide_confirmed}，"
        f"核验状态={meme.verification_state}）"
    )


def certification_progress(meme: Meme) -> dict[str, object]:
    """给前端展示的认证状态（含准入与强度标签）。"""
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
        "admitted": admitted(meme),
        "certified_by": certified_by(meme),
        "cert_label": cert_label(meme),
        "cert_window_days": settings_cert_window_days(),
        "certified_at": meme.certified_at.isoformat() if meme.certified_at else None,
    }


def settings_cert_window_days() -> int:
    """认证窗口天数（供接口如实说明"证据看的是最近多少天"）。"""
    from app.config import settings

    return int(getattr(settings, "cert_window_days", 90))

