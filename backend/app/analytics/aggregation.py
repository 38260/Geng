"""视频 → 每日聚合。

B 站接口给出的是"截至抓取时刻"的累计指标，因此 V1 的口径是：

    某天的统计 = 当天发布、且通过相关性过滤的那批视频，在当前时刻的指标之和

这也是为什么 ``MemeDailyStats`` 需要每天跑一次采集才能形成完整时间序列：
越靠近今天的日期，样本越完整；历史日期只保留当时能搜到的那批视频。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.models import MemeDailyStats, Video

from .series import Series


def aggregate_videos(meme_id: int, videos: list[Video], *, data_source: str = "bilibili") -> list[MemeDailyStats]:
    """按发布日聚合，UP 主数按天去重。"""
    buckets: dict[date, dict[str, object]] = defaultdict(
        lambda: {
            "videos": 0, "authors": set(), "view": 0, "like": 0, "coin": 0,
            "favorite": 0, "reply": 0, "danmaku": 0,
        }
    )
    for video in videos:
        day = video.publish_time.date()
        bucket = buckets[day]
        bucket["videos"] = int(bucket["videos"]) + 1  # type: ignore[arg-type]
        if video.author:
            bucket["authors"].add(video.author)  # type: ignore[union-attr]
        for field in ("view", "like", "coin", "favorite", "reply", "danmaku"):
            bucket[field] = int(bucket[field]) + int(getattr(video, field) or 0)  # type: ignore[arg-type]

    stats: list[MemeDailyStats] = []
    for day in sorted(buckets):
        bucket = buckets[day]
        stats.append(
            MemeDailyStats(
                meme_id=meme_id,
                stat_date=day,
                video_count=int(bucket["videos"]),  # type: ignore[arg-type]
                creator_count=len(bucket["authors"]),  # type: ignore[arg-type]
                view=int(bucket["view"]),  # type: ignore[arg-type]
                like=int(bucket["like"]),  # type: ignore[arg-type]
                coin=int(bucket["coin"]),  # type: ignore[arg-type]
                favorite=int(bucket["favorite"]),  # type: ignore[arg-type]
                reply=int(bucket["reply"]),  # type: ignore[arg-type]
                danmaku=int(bucket["danmaku"]),  # type: ignore[arg-type]
                data_source=data_source,
            )
        )
    return stats


def series_from_stats(meme_id: int, stats: list[MemeDailyStats], *, window_days: int = 30) -> Series:
    return Series.from_stats(meme_id, stats, window_days=window_days)
