"""热度指数与生命周期快照（每个梗保留最新一份，接口直接读，避免现算）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class HotnessSnapshot(Base):
    """梗热度指数：0-100，完全由本项目算法计算，不使用 B 站官方指数。"""

    __tablename__ = "hotness_snapshots"

    meme_id: Mapped[int] = mapped_column(
        ForeignKey("memes.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    window_days: Mapped[int] = mapped_column(Integer, default=7)

    # 五个子分数：view / interaction / content / creator / growth
    components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 各窗口原始量与增长率，供详情页展示
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    data_version: Mapped[str] = mapped_column(String(64), default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "window_days": self.window_days,
            "components": self.components or {},
            "metrics": self.metrics or {},
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }


class LifecycleSnapshot(Base):
    """生命周期阶段：🌱 萌芽 / 📈 上升 / 🔥 爆发 / 🌊 平稳 / 📉 退潮 / 🪦 过气。"""

    __tablename__ = "lifecycle_snapshots"

    meme_id: Mapped[int] = mapped_column(
        ForeignKey("memes.id", ondelete="CASCADE"), primary_key=True
    )
    stage: Mapped[str] = mapped_column(String(20), index=True)
    stage_label: Mapped[str] = mapped_column(String(20))
    emoji: Mapped[str] = mapped_column(String(8), default="")

    # 判定依据（增长率、距峰值差、活跃度等），用于详情页解释"为什么是这个阶段"
    indicators: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    data_version: Mapped[str] = mapped_column(String(64), default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "stage_label": self.stage_label,
            "emoji": self.emoji,
            "indicators": self.indicators or {},
            "reasons": self.reasons or [],
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }
