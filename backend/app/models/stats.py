"""每日聚合统计（时间序列的存储单元）。"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .meme import Meme

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class MemeDailyStats(Base):
    """某个梗在某一天的聚合数据。

    热度不直接取历史累计，而是按天存原始量，再由算法在 1/3/7/30 天窗口上计算。
    """

    __tablename__ = "meme_daily_stats"
    __table_args__ = (UniqueConstraint("meme_id", "stat_date", name="uq_daily_meme_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meme_id: Mapped[int] = mapped_column(
        ForeignKey("memes.id", ondelete="CASCADE"), index=True
    )
    stat_date: Mapped[date] = mapped_column(Date, index=True)

    video_count: Mapped[int] = mapped_column(Integer, default=0)
    creator_count: Mapped[int] = mapped_column(Integer, default=0)

    view: Mapped[int] = mapped_column(Integer, default=0)
    like: Mapped[int] = mapped_column(Integer, default=0)
    coin: Mapped[int] = mapped_column(Integer, default=0)
    favorite: Mapped[int] = mapped_column(Integer, default=0)
    reply: Mapped[int] = mapped_column(Integer, default=0)
    danmaku: Mapped[int] = mapped_column(Integer, default=0)

    # 当日热度指数（0-100），由算法预计算，接口不再现算
    hotness: Mapped[float] = mapped_column(Float, default=0.0)

    data_source: Mapped[str] = mapped_column(String(16), default="mock")

    meme: Mapped["Meme"] = relationship(back_populates="daily_stats")  # noqa: F821

    @property
    def interaction(self) -> int:
        return self.like + self.coin + self.favorite + self.reply + self.danmaku

    @property
    def discussion(self) -> int:
        """「讨论量」= 评论 + 弹幕，首页卡片用的就是这个口径。"""
        return self.reply + self.danmaku

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.stat_date.isoformat(),
            "video_count": self.video_count,
            "creator_count": self.creator_count,
            "view": self.view,
            "like": self.like,
            "coin": self.coin,
            "favorite": self.favorite,
            "reply": self.reply,
            "danmaku": self.danmaku,
            "interaction": self.interaction,
            "discussion": self.discussion,
            "hotness": round(self.hotness, 1),
            "data_source": self.data_source,
        }
