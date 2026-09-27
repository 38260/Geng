"""AI 结果缓存。

LLM 只负责把已经算好的数据讲成人话，因此这里缓存的是"针对某一版数据"的解释文本：

    cache key = (meme_id, kind, data_version)

数据没明显变化（``data_version`` 相同）就不会再打 LongCat，避免每次刷新页面都调用。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class InsightKind:
    TREND_EXPLANATION = "trend_explanation"
    CATCH_UP_ADVICE = "catch_up_advice"


class InsightSource:
    LLM = "llm"          # 真实来自 LongCat
    RULE = "rule"        # LLM 不可用时的纯算法兜底
    CACHE = "cache"      # 命中缓存


class InsightStatus:
    OK = "ok"
    UNAVAILABLE = "unavailable"   # 未配置 / 调用失败，前端显示降级提示
    ERROR = "error"


class AIInsight(Base):
    __tablename__ = "ai_insights"
    __table_args__ = (
        UniqueConstraint("meme_id", "kind", "data_version", name="uq_insight_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meme_id: Mapped[int] = mapped_column(
        ForeignKey("memes.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)

    model: Mapped[str] = mapped_column(String(80), default="")
    data_version: Mapped[str] = mapped_column(String(64), default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    status: Mapped[str] = mapped_column(String(20), default=InsightStatus.OK)
    source: Mapped[str] = mapped_column(String(16), default=InsightSource.LLM)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "source": self.source,
            "model": self.model,
            "data_version": self.data_version,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "result": self.result or {},
        }
