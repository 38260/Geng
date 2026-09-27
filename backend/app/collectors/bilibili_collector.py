"""真实 B 站采集器：梗库驱动 + 逐日定向搜索 + 相关性过滤。

流程（对应文档 §七 的"正确方式"）：

    已认证梗 → 梗名 → 对最近 30 天逐日查询（带发布时间区间，按播放排序）
    → 相关性打分过滤 → 当日聚合 → 头部视频逐条补齐点赞/投币/收藏

为什么要逐日查：B 站搜索不带日期区间时，结果会被最近发布的内容占满，
早期日期根本查不到，直接聚合会算出 "+23616%" 这种被截断放大的假增长。

明确不做的事：
* 不下载全站视频；
* 不用 LLM 判断每条视频是否相关（那是 §十 的相关性打分在做）；
* 拿不到数据时不伪造——直接抛 :class:`BilibiliBlocked` 让上层回退。
"""

from __future__ import annotations

import time
from datetime import date, datetime, time as _time, timedelta

from app.config import get_logger, settings
from app.models import Meme

from .base import CollectedBundle, CertificationEvidence
from .bilibili import BilibiliBlocked, BiliClient, get_client, parse_search_row
from ..analytics.relevance import MemeTerms, score_text
from ..services.meme.certification import UP_AUTHORS

log = get_logger(__name__)

SOURCE = "bilibili"

# 有内容天数达到这个数就认为序列已经能画出形状，不再为别名多打接口
_ENOUGH_DAYS = 8


class BilibiliCollector:
    source = SOURCE
    aggregates_from_videos = False

    def __init__(
        self,
        client: BiliClient | None = None,
        *,
        pages_per_term: int = 2,
        enrich_limit: int = 12,
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
    def collect_daily(
        self, meme: Meme, *, window_days: int = 30
    ) -> tuple[list, dict, int]:
        """逐日定向采集，返回 (每日统计, 视频样本, 被剔除的无关条数)。

        搜索词先用梗名；梗名本身是常用口语时（「啊对对对」「这很难评」），
        B 站会把结果模糊匹配到一堆无关内容，相关性过滤后什么都不剩，
        整条序列就空掉了。这时退回用别名再查一轮，取有内容天数更多的那一版。
        """
        candidates = [meme.name] + [
            alias for alias in (meme.aliases or []) if alias and alias != meme.name
        ][:2]
        best: tuple[list, dict, int] | None = None

        def days_of(rows: list) -> int:
            return sum(1 for row in rows if row.video_count)

        for term in candidates:
            result = self._daily_pass(meme, term, window_days=window_days)
            # 第一版无条件收下：哪怕全是 0，也要保留"逐日跑满窗口"的骨架，
            # 否则调用方看到的行数是 0 而不是 window_days，日志和空窗判断都会误导。
            if best is None or days_of(result[0]) > days_of(best[0]):
                best = result
            if days_of(best[0]) >= _ENOUGH_DAYS:
                break
            if term == candidates[0]:
                log.info(
                    "梗「%s」用梗名只查到 %s 天有内容，改用别名再查一轮（B站对口语梗名会模糊匹配到无关内容）",
                    meme.name, days_of(result[0]),
                )
        return best or ([], {}, 0)

    def _daily_pass(
        self, meme: Meme, term: str, *, window_days: int = 30
    ) -> tuple[list, dict, int]:
        """用给定搜索词跑一遍逐日区间查询。

        为什么必须逐日查：B 站搜索不带日期区间时，结果会被最近发布的内容占满，
        早期日期根本查不到 —— 直接聚合会得到"+23616%"这种被截断放大的假增长。

        注意口径：单日只取回 top 20，所以"当日播放量"是该日头部内容的合计，
        不是该梗全站绝对量；跨日、跨梗比较用同一把尺子，形状可信。
        """
        from app.models import MemeDailyStats

        terms = MemeTerms.from_meme(meme)
        threshold = settings.relevance_threshold
        today = date.today()
        stats: list[MemeDailyStats] = []
        seen: dict[str, dict] = {}
        filtered_out = 0

        for offset in range(1, window_days + 1):          # 不含今天（今天还没过完）
            day = today - timedelta(days=offset)
            begin = datetime.combine(day, _time.min)
            end = begin + timedelta(days=1)
            try:
                rows, total = self.client.search_range(term, begin=begin, end=end, order="click")
            except BilibiliBlocked as exc:
                log.warning("梗「%s」%s 采集被拒：%s", term, day, exc)
                raise
            except Exception as exc:  # noqa: BLE001 - 单日失败不该毁掉整条序列
                log.warning("梗「%s」%s 查询异常：%s", term, day, exc)
                rows, total = [], 0

            parsed = []
            for row in rows:
                item = parse_search_row(row)
                if not item.get("bvid"):
                    continue
                # 搜索会把短词模糊匹配到一大堆无关内容，先按相关性打分过滤
                result = score_text(terms, item["title"], item.get("description", ""),
                                    [item.get("tag") or ""])
                item["relevance_score"] = result.score
                item["matched_terms"] = result.matched_terms
                if result.score < threshold:
                    filtered_out += 1
                    continue
                parsed.append(item)
            for item in parsed:
                seen.setdefault(item["bvid"], item)

            authors = {item.get("author") for item in parsed if item.get("author")}
            stats.append(
                MemeDailyStats(
                    stat_date=day,
                    video_count=len(parsed),
                    creator_count=len(authors) or (1 if parsed else 0),
                    view=sum(int(item.get("view") or 0) for item in parsed),
                    like=0,
                    coin=0,
                    favorite=0,
                    reply=sum(int(item.get("reply") or 0) for item in parsed),
                    danmaku=sum(int(item.get("danmaku") or 0) for item in parsed),
                    search_total=total,
                    data_source=SOURCE,
                )
            )
            time.sleep(self.request_gap)

        stats.sort(key=lambda row: row.stat_date)
        return stats, seen, filtered_out

    def collect(self, meme: Meme, *, window_days: int = 30) -> CollectedBundle:
        """逐日采集 + 头部视频样本补齐，产出与 MockCollector 同构的 bundle。"""
        from app.models import Video

        stats, seen, filtered_out = self.collect_daily(meme, window_days=window_days)
        active = [row for row in stats if row.video_count > 0]
        log.info(
            "梗「%s」逐日采集：%s/%s 天有内容，累计样本视频 %s 条",
            meme.name, len(active), len(stats), len(seen),
        )

        # 视频列表：按播放量取头部若干条，逐条补齐点赞/投币/收藏
        ranked = sorted(seen.values(), key=lambda item: int(item.get("view") or 0), reverse=True)
        enriched = self._enrich([item["bvid"] for item in ranked])

        videos: list[Video] = []
        for item in ranked:
            merged = enriched.get(item["bvid"], {})
            videos.append(
                Video(
                    bvid=item["bvid"],
                    aid=item.get("aid"),
                    title=str(item.get("title") or "")[:250],
                    description=merged.get("description") or str(item.get("description") or ""),
                    author=str(item.get("author") or ""),
                    author_mid=merged.get("author_mid") or item.get("author_mid"),
                    cover=str(item.get("cover") or ""),
                    tags=merged.get("tags", []),
                    publish_time=item["publish_time"],
                    crawl_time=datetime.now(),
                    duration_seconds=merged.get("duration_seconds", 0),
                    view=merged.get("view", int(item.get("view") or 0)),
                    like=merged.get("like", 0),
                    coin=merged.get("coin", 0),
                    favorite=merged.get("favorite", 0),
                    reply=merged.get("reply", int(item.get("reply") or 0)),
                    danmaku=merged.get("danmaku", int(item.get("danmaku") or 0)),
                    relevance_score=float(item.get("relevance_score") or 0.0),
                    matched_terms=list(item.get("matched_terms") or []),
                    data_source=SOURCE,
                )
            )

        return CollectedBundle(
            daily_stats=stats, videos=videos, dropped_irrelevant=filtered_out
        )

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
