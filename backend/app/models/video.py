"""B 站相关视频（梗匹配后的样本）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .meme import Meme

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (UniqueConstraint("meme_id", "bvid", name="uq_video_meme_bvid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meme_id: Mapped[int | None] = mapped_column(
        ForeignKey("memes.id", ondelete="CASCADE"), nullable=True, index=True
    )

    bvid: Mapped[str] = mapped_column(String(32), index=True)
    aid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(120), default="")
    author_mid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover: Mapped[str] = mapped_column(String(300), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    publish_time: Mapped[datetime] = mapped_column(DateTime)
    crawl_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    view: Mapped[int] = mapped_column(Integer, default=0)
    like: Mapped[int] = mapped_column(Integer, default=0)
    coin: Mapped[int] = mapped_column(Integer, default=0)
    favorite: Mapped[int] = mapped_column(Integer, default=0)
    reply: Mapped[int] = mapped_column(Integer, default=0)
    danmaku: Mapped[int] = mapped_column(Integer, default=0)

    # 梗匹配结果：命中了哪些检索词 + 相关性打分
    matched_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)

    # mock = 演示数据；bilibili = 真实抓取
    data_source: Mapped[str] = mapped_column(String(16), default="mock")

    meme: Mapped["Meme"] = relationship(back_populates="videos")  # noqa: F821

    @property
    def url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"

    @property
    def interaction_total(self) -> int:
        return int(self.like or 0) + int(self.coin or 0) + int(self.favorite or 0) + int(
            self.reply or 0
        ) + int(self.danmaku or 0)

    def to_dict(self, include_meme: bool = True) -> dict[str, Any]:
        return {
            "bvid": self.bvid,
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "cover": self.cover,
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "view": self.view,
            "like": self.like,
            "coin": self.coin,
            "favorite": self.favorite,
            "reply": self.reply,
            "danmaku": self.danmaku,
            "duration_seconds": self.duration_seconds,
            "relevance_score": round(self.relevance_score, 3),
            "data_source": self.data_source,
            **({"meme_id": self.meme_id} if include_meme else {}),
        }
