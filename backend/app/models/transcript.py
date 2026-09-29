"""解说视频逐字稿（字幕原文）。

为什么单独一张表：详情页「这个梗是什么」以前只有解说视频的**标题和简介**，
那不是视频里说的话。要拿到内容，唯一来路是 B 站字幕轨（实测：匿名请求
`player/wbi/v2` 返回空轨、AI 视频总结直接 -101 未登录），而字幕是按 bvid
一次性抓的、不会天天变，所以单独存表、单独刷新，不跟 `videos` 混在一起。

诚实约定：``text`` 只放 B 站下发的字幕原文，不做改写；``kind`` 区分人工 CC
与 AI 自动字幕（后者错字更多，界面上要标出来）。
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def transcript_digest(bvid: str, text: str | None) -> str:
    """字幕内容指纹：详情接口与 AI 浓缩缓存都用它当版本号。

    键里带 bvid 是因为字幕会被重抓/UP 主改，文本一变旧结论就该自动失效。
    """
    return f"{bvid}:{hashlib.sha1((text or '').encode('utf-8')).hexdigest()[:12]}"


class TranscriptKind:
    CC = "cc"        # UP 主/字幕组上传的人工字幕
    AI = "ai"        # B 站自动识别的字幕，错字与断句明显更多


TRANSCRIPT_LABELS = {TranscriptKind.CC: "人工字幕", TranscriptKind.AI: "AI 识别字幕"}


class VideoTranscript(Base):
    """一条视频的逐字稿。主键用 bvid：一条视频只留一份当前字幕。"""

    __tablename__ = "video_transcripts"

    bvid: Mapped[str] = mapped_column(String(32), primary_key=True)
    meme_id: Mapped[int | None] = mapped_column(
        ForeignKey("memes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    cid: Mapped[int] = mapped_column(Integer, default=0)
    video_title: Mapped[str] = mapped_column(String(250), default="")
    # cc / ai，见 TranscriptKind
    kind: Mapped[str] = mapped_column(String(8), default=TranscriptKind.CC)
    lang: Mapped[str] = mapped_column(String(16), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    chars: Mapped[int] = mapped_column(Integer, default=0)
    # 抓这条字幕时是不是登录态。匿名抓到的空轨不入库，只记在日志里
    logged_in: Mapped[bool] = mapped_column(default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bvid": self.bvid,
            "meme_id": self.meme_id,
            "kind": self.kind,
            "kind_label": TRANSCRIPT_LABELS.get(self.kind, self.kind),
            "lang": self.lang,
            "video_title": self.video_title,
            "chars": self.chars,
            "url": f"https://www.bilibili.com/video/{self.bvid}",
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }
