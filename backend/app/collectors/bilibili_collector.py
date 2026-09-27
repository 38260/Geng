"""真实 B 站采集器：梗库驱动 + 定向搜索 + 逐条补齐指标。

流程（对应文档 §七 的"正确方式"）：

    已认证梗 → 名称/别名 → B站搜索 → 时间窗口过滤 → 逐条补齐指标
    → 相关性过滤（在管线里）→ 去重 → 每日聚合

明确不做的事：
* 不下载全站视频；
* 不用 LLM 判断每条视频是否相关（那是 §十 的相关性打分在做）；
* 拿不到数据时不伪造——直接抛 :class:`BilibiliBlocked` 让上层回退。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from app.config import get_logger
from app.models import CertRole, Meme

from .base import CollectedBundle, CertificationEvidence
from .bilibili import BilibiliBlocked, BiliClient, get_client, parse_search_row
from ..analytics.aggregation import aggregate_videos
from ..services.meme.certification import UP_AUTHORS

log = get_logger(__name__)

SOURCE = "bilibili"


class BilibiliCollector:
    source = SOURCE

    def __init__(
        self,
        client: BiliClient | None = None,
        *,
        pages_per_term: int = 2,
        enrich_limit: int = 25,
        request_gap: float = 0.35,
    ) -> None:
        self.client = client or get_client()
        self.pages_per_term = pages_per_term
        self.enrich_limit = enrich_limit
        self.request_gap = request_gap

    # ------------------------------------------------------------------ #
    def is_available(self) -> tuple[bool, str]:
        return self.client.probe()

    def _search(self, terms: list[str]) -> dict[str, dict]:
        found: dict[str, dict] = {}
        for term in terms:
            try:
                rows = self.client.search_videos(term, pages=self.pages_per_term, order="pubdate")
            except BilibiliBlocked as exc:
                log.warning("搜索「%s」被拒：%s", term, exc)
                raise
            for row in rows:
                parsed = parse_search_row(row)
                bvid = parsed.get("bvid") or ""
                if bvid and bvid not in found:
                    found[bvid] = parsed
            time.sleep(self.request_gap)
        return found

    def _enrich(self, bvids: list[str]) -> dict[str, dict]:
        """搜索结果不含点赞/投币/收藏，逐条查详情接口补齐（只补前 N 条）。"""
        stats: dict[str, dict] = {}
        for bvid in bvids[: self.enrich_limit]:
            try:
                payload = self.client._get_payload(
                    "https://api.bilibili.com/x/web-interface/view", {"bvid": bvid}
                )
            except BilibiliBlocked as exc:
                log.warning("补齐 %s 失败：%s", bvid, exc)
                continue
            data = payload.get("data") or {}
            stat = data.get("stat") or {}
            if not stat:
                continue
            stats[bvid] = {
                "view": int(stat.get("view") or 0),
                "like": int(stat.get("like") or 0),
                "coin": int(stat.get("coin") or 0),
                "favorite": int(stat.get("favorite") or 0),
                "reply": int(stat.get("reply") or 0),
                "danmaku": int(stat.get("danmaku") or 0),
                "duration_seconds": int(data.get("duration") or 0),
                "description": str(data.get("desc") or "")[:500],
                "tags": [str(tag) for tag in (data.get("tags") or [])][:8]
                if isinstance(data.get("tags"), list)
                else [],
                "author_mid": data.get("mid"),
            }
            time.sleep(self.request_gap)
        return stats

    # ------------------------------------------------------------------ #
    def collect(self, meme: Meme, *, window_days: int = 30) -> CollectedBundle:
        from app.models import Video

        terms = meme.match_terms()[:4]  # 名称 + 别名，够定向了，别把接口打爆
        cutoff = datetime.now() - timedelta(days=window_days)

        rows = self._search(terms)
        fresh = [row for row in rows.values() if row["publish_time"] >= cutoff]
        log.info("梗「%s」搜索到 %s 条，窗口内 %s 条", meme.name, len(rows), len(fresh))

        # 播放量高的先补指标
        fresh.sort(key=lambda row: row["view"], reverse=True)
        extra = self._enrich([row["bvid"] for row in fresh])

        videos: list[Video] = []
        for row in fresh:
            merged = extra.get(row["bvid"], {})
            videos.append(
                Video(
                    bvid=row["bvid"],
                    aid=row.get("aid"),
                    title=row["title"][:250],
                    description=merged.get("description") or row.get("description", ""),
                    author=row.get("author", ""),
                    author_mid=merged.get("author_mid") or row.get("author_mid"),
                    cover=row.get("cover", ""),
                    tags=merged.get("tags", []),
                    publish_time=row["publish_time"],
                    crawl_time=datetime.now(),
                    duration_seconds=merged.get("duration_seconds", 0),
                    view=merged.get("view", row.get("view", 0)),
                    like=merged.get("like", 0),
                    coin=merged.get("coin", 0),
                    favorite=merged.get("favorite", 0),
                    reply=merged.get("reply", row.get("reply", 0)),
                    danmaku=merged.get("danmaku", row.get("danmaku", 0)),
                    data_source=SOURCE,
                )
            )

        return CollectedBundle(daily_stats=aggregate_videos(meme.id, videos, data_source=SOURCE), videos=videos)

    # ------------------------------------------------------------------ #
    def collect_certification(self, meme: Meme) -> list[CertificationEvidence]:
        """用两位 UP 主的真实投稿验证认证。空间接口需要 Cookie，被拒时返回空。"""
        evidences: list[CertificationEvidence] = []
        for role, author in UP_AUTHORS.items():
            try:
                rows = self.client.space_videos(author.mid, page_size=50)
            except BilibiliBlocked as exc:
                log.warning("读取 %s 投稿失败：%s", author.name, exc)
                return []
            needle = meme.name.lower()
            hit = next(
                (row for row in rows if needle in str(row.get("title", "")).lower()),
                None,
            )
            if hit is None:
                return []  # 少一个 UP 主认证就不算通过，不拼半份证据
            published = hit.get("created") or hit.get("pubdate") or 0
            evidences.append(
                CertificationEvidence(
                    role=role,
                    bvid=str(hit.get("bvid") or ""),
                    video_title=str(hit.get("title") or "")[:200],
                    published_at=datetime.fromtimestamp(published) if published else None,
                    confirmed=True,
                    data_source=SOURCE,
                )
            )
        return evidences
