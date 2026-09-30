"""梗 / 双 UP 认证 数据模型。

「梗库准入」与「双 UP 认证」是两个层次，都真实落在数据模型上，而不是 README 里的说法：

    准入（发现层）= 梗百科 confirmed OR 梗指南 confirmed   → status == certified
    认证（徽章）  = 梗百科 confirmed AND 梗指南 confirmed  → certified == True

只有准入通过的梗才会被采集、算分并出现在榜单上；``certified`` 表示"两位 UP 主都
独立做过"，作为可信度标签展示（双 UP 认证 / 梗百科认证 / 梗指南认证）。
规则由 :mod:`app.services.meme.certification` 在写入时强制，读侧由
``Meme.is_official`` 与查询层的闸门把关。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .stats import MemeDailyStats
    from .video import Video

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class CertRole:
    """两个梗解释 UP 主的角色标识。"""

    ENCYCLOPEDIA = "encyclopedia"  # 梗百科
    GUIDE = "guide"                # 梗指南


class MemeStatus:
    CANDIDATE = "candidate"   # 只有单 UP 介绍过，等待另一个 UP 认证
    CERTIFIED = "certified"   # 双 UP 认证，进入正式梗库
    ARCHIVED = "archived"     # 过气归档，不再出现在榜单


class Meme(Base):
    __tablename__ = "memes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")

    # 人工维护的封面；留空则自动取"该梗播放量最高那条视频"的 B站封面。
    # 只影响展示，不参与任何指标计算。
    cover_url: Mapped[str] = mapped_column(String(500), default="")

    status: Mapped[str] = mapped_column(String(20), default=MemeStatus.CANDIDATE, index=True)

    # 双 UP 认证结果（冗余存储，便于直接查询；由服务层根据认证记录重算）
    encyclopedia_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    guide_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    certified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 双 UP 认证的在线核验状态：verified_both / partially_verified / unverified
    verification_state: Mapped[str] = mapped_column(String(24), default="unverified")

    # 这个梗的数据来自演示生成还是真实 B 站抓取（混跑时要能区分）
    data_source: Mapped[str] = mapped_column(String(16), default="mock", index=True)

    # 最近一次数据/指标重算的时间，前端"数据更新于"直接取它
    data_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_version: Mapped[str] = mapped_column(String(64), default="")

    # 主题标签：只存 key 数组（如 ["workplace", "abstract"]），展示时查 TAG_LABELS。
    # 取值只能来自 app/config/taxonomy.py 的固定清单——模型选了清单外的会被丢掉，
    # 否则标签会越标越碎，筛选失去意义。
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 标签来源：llm = 模型标的；manual = 有人在管理页改过；空 = 还没标过
    tags_source: Mapped[str] = mapped_column(String(16), default="")
    tags_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    certifications: Mapped[list["MemeCertification"]] = relationship(
        back_populates="meme",
        cascade="all, delete-orphan",
        order_by="MemeCertification.role",
        lazy="selectin",
    )
    daily_stats: Mapped[list["MemeDailyStats"]] = relationship(
        back_populates="meme", cascade="all, delete-orphan", lazy="noload"
    )
    videos: Mapped[list["Video"]] = relationship(
        back_populates="meme", cascade="all, delete-orphan", lazy="noload"
    )

    # ------------------------------------------------------------------ #
    @property
    def is_official(self) -> bool:
        """是否属于「赶梗潮」正式梗库。"""
        return bool(self.certified) and self.status == MemeStatus.CERTIFIED

    @property
    def encyclopedia(self) -> "MemeCertification | None":
        return next((c for c in self.certifications if c.role == CertRole.ENCYCLOPEDIA), None)

    @property
    def guide(self) -> "MemeCertification | None":
        return next((c for c in self.certifications if c.role == CertRole.GUIDE), None)

    def match_terms(self) -> list[str]:
        """用于 B 站搜索与相关性打分的词表：名称 + 别名 + 关键词。"""
        terms = [self.name, *(self.aliases or []), *(self.keywords or [])]
        seen: set[str] = set()
        out: list[str] = []
        for term in terms:
            term = (term or "").strip()
            if term and term.lower() not in seen:
                seen.add(term.lower())
                out.append(term)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "aliases": self.aliases or [],
            "keywords": self.keywords or [],
            "description": self.description,
            "status": self.status,
            "certified": self.certified,
            "verification_state": self.verification_state,
            "data_source": self.data_source,
            "encyclopedia_confirmed": self.encyclopedia_confirmed,
            "guide_confirmed": self.guide_confirmed,
            "certified_at": self.certified_at.isoformat() if self.certified_at else None,
            "data_updated_at": self.data_updated_at.isoformat() if self.data_updated_at else None,
            "tags": self.tags or [],
            "tags_source": self.tags_source or "",
        }

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Meme {self.id} {self.name} certified={self.certified}>"


class MemeCertification(Base):
    """单个 UP 主对某个梗的一次「介绍过」证据。"""

    __tablename__ = "meme_certifications"
    __table_args__ = (UniqueConstraint("meme_id", "role", name="uq_certification_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meme_id: Mapped[int] = mapped_column(ForeignKey("memes.id", ondelete="CASCADE"), index=True)

    role: Mapped[str] = mapped_column(String(20))
    up_name: Mapped[str] = mapped_column(String(80))
    up_mid: Mapped[int] = mapped_column(Integer, index=True)

    bvid: Mapped[str] = mapped_column(String(32), default="")
    video_title: Mapped[str] = mapped_column(String(200), default="")
    video_url: Mapped[str] = mapped_column(String(200), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # mock = 演示证据；bilibili = 真实抓取到的 UP 主投稿
    data_source: Mapped[str] = mapped_column(String(16), default="mock")

    meme: Mapped[Meme] = relationship(back_populates="certifications")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "up_name": self.up_name,
            "up_mid": self.up_mid,
            "bvid": self.bvid,
            "video_title": self.video_title,
            # 只有真实抓取到的投稿才给可点开的链接；演示/未核验证据不给，避免点进 404
            "linkable": self.data_source == "bilibili",
            "video_url": (
                self.video_url or (f"https://www.bilibili.com/video/{self.bvid}" if self.bvid else "")
            ) if self.data_source == "bilibili" else "",
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "confirmed": self.confirmed,
            "data_source": self.data_source,
        }
