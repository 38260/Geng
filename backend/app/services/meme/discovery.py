"""从两位 UP 主的真实投稿里构建梗库（双 UP 认证的真实实现）。

之前认证证据是演示数据里造的假 BV 号——那不能算真数据。这里的做法是：

    翻页拉取 梗百科 / 梗指南 的投稿 → 从标题里抽取梗名 → 取交集
    → 交集里的梗才算 certified，并带上真实 bvid / 标题 / 发布时间

为什么取交集而不是各自单独判：项目规则就是"两个 UP 主都独立介绍过"。
空间接口限流很凶（大量 412），所以索引拉取带退避重试，并且能拉多少算多少，
拉不到的部分会如实报告，不会拿旧证据凑数。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from app.config import get_logger
from app.services.meme.certification import ENCYCLOPEDIA, GUIDE, UpAuthor

from ...collectors.bilibili import BilibiliBlocked, BiliClient

log = get_logger(__name__)

# 标题里梗名的常见写法：「XX是什么梗【梗指南】」「【梗百科】XX是啥梗？」「XX：…【梗指南】」
_TITLE_PATTERNS = [
    re.compile(r"^(.*?)\s*(?:是什么梗|是啥梗|什么意思|什么来头|是什么|是啥)\s*[？?!！。.\|｜-]*"),
    re.compile(r"^(.*?)\s*(?:梗|热梗|新梗)\s*[？?!！。]?\s*$"),
]
_BRACKET = re.compile(r"【[^】]*】|\[[^\]]*\]|（[^）]*）")
_STOP_WORDS = {"这个", "那个", "一个", "一种", "到底", "原来", "居然", "竟然", "什么", "为啥", "为什么"}


@dataclass
class UpVideo:
    bvid: str
    title: str
    pubdate: datetime
    mid: int
    author: str
    play: int = 0


@dataclass
class DiscoveryReport:
    per_author: dict[str, int] = field(default_factory=dict)
    pages_fetched: dict[str, int] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)
    extracted: dict[str, int] = field(default_factory=dict)
    certified: list[tuple[str, UpVideo, UpVideo]] = field(default_factory=list)
    single_sided: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def extract_meme_name(title: str) -> str | None:
    """从投稿标题里抽出被介绍的梗名；抽不出就返回 None（宁可漏不可造）。"""
    text = _BRACKET.sub("", title or "").strip()
    text = re.sub(r"^[|｜·\-\s]+|[|｜·\s]+$", "", text)
    if not text:
        return None

    candidates: list[str] = []
    for pattern in _TITLE_PATTERNS:
        match = pattern.match(text)
        if match:
            candidates.append(match.group(1).strip())
    # 冒号/破折号前往往才是梗名："XX：一句话解释"
    for candidate in list(candidates):
        for splitter in ("：", ":", "—", "|", "｜"):
            if splitter in candidate:
                head = candidate.split(splitter)[0].strip()
                if head:
                    candidates.append(head)

    for candidate in candidates:
        cleaned = re.sub(r"^[\s「『\"'']+", "", candidate).strip(" \t\"'』」？?！!。.，,、")
        if 2 <= len(cleaned) <= 16 and not any(word in cleaned for word in _STOP_WORDS):
            return cleaned
    return None


def fetch_up_index(
    client: BiliClient,
    author: UpAuthor,
    *,
    max_pages: int = 8,
    page_size: int = 50,
    gap: float = 1.2,
    retries: int = 6,
    not_before: datetime | None = None,
) -> tuple[list[UpVideo], int, int]:
    """翻页拉某个 UP 主的投稿。返回 (视频列表, 成功页数, 被风控页数)。

    空间投稿接口风控很凶：第 1 页（最新投稿）失败一次，就会拿到一整页老视频，
    看起来"拉到了 150 条"其实全是过期的。所以 retries 给到 6，
    并且允许传 not_before——只要这一页最旧的一条已经早于时间窗，就不必再往后翻。
    """
    videos: list[UpVideo] = []
    pages_ok = 0
    blocked = 0

    for page in range(1, max_pages + 1):
        attempt = 0
        while attempt <= retries:
            try:
                rows = client.space_videos(author.mid, page_size=page_size, page=page)
            except BilibiliBlocked as exc:
                attempt += 1
                blocked += 1
                if page == 1 and attempt > 2:
                    # 首页拿不到就没法判断时间窗，后面的页再新也是旧的，直接报错
                    raise RuntimeError(f"{author.name} 最新投稿取不到：{exc}") from exc
                wait = min(2.0 * attempt, 10.0)
                log.warning("%s 第 %s 页被风控（%s），%.1fs 后重试", author.name, page, str(exc)[:40], wait)
                time.sleep(wait)
                continue

            pages_ok += 1
            for row in rows:
                bvid = str(row.get("bvid") or "")
                if not bvid:
                    continue
                stamp = row.get("created") or row.get("pubdate") or 0
                videos.append(
                    UpVideo(
                        bvid=bvid,
                        title=str(row.get("title") or ""),
                        pubdate=datetime.fromtimestamp(stamp) if stamp else datetime.min,
                        mid=author.mid,
                        author=author.name,
                        play=int(row.get("play") or 0),
                    )
                )
            break

        if not_before and videos and min(v.pubdate for v in videos if v.pubdate) < not_before:
            log.info("%s：已翻到时间窗之前（%s），停止翻页", author.name, not_before.strftime("%Y-%m-%d"))
            break
        time.sleep(gap)

    return videos, pages_ok, blocked


def index_by_meme(videos: list[UpVideo]) -> dict[str, UpVideo]:
    """梗名 -> 该 UP 主最早介绍它的那期（认证看的是"介绍过"，取首发更合理）。"""
    index: dict[str, UpVideo] = {}
    for video in sorted(videos, key=lambda item: item.pubdate, reverse=True):
        name = extract_meme_name(video.title)
        if not name:
            continue
        key = name.lower()
        if key not in index:
            index[key] = video
    return index


def discover(client: BiliClient, *, max_pages: int = 8, gap: float = 1.2) -> DiscoveryReport:
    report = DiscoveryReport()
    indexes: dict[str, dict[str, UpVideo]] = {}

    for author in (ENCYCLOPEDIA, GUIDE):
        try:
            videos, pages_ok, blocked = fetch_up_index(client, author, max_pages=max_pages, gap=gap)
        except Exception as exc:  # noqa: BLE001 - 单个 UP 失败要如实报告而不是假装成功
            report.errors.append(f"{author.name}: {exc}")
            continue
        report.per_author[author.name] = len(videos)
        report.pages_fetched[author.name] = pages_ok
        report.failures[author.name] = blocked
        indexes[author.name] = index_by_meme(videos)
        report.extracted[author.name] = len(indexes[author.name])
        log.info("%s：拉到 %s 条投稿，识别出 %s 个梗名（%s 页成功 / %s 次被风控）",
                 author.name, len(videos), len(indexes[author.name]), pages_ok, blocked)

    if len(indexes) < 2:
        log.warning("只拿到 %s 位 UP 的数据，无法做双 UP 交集认证", len(indexes))
        return report

    enc, gui = indexes[ENCYCLOPEDIA.name], indexes[GUIDE.name]
    shared = sorted(set(enc) & set(gui))
    for key in shared:
        report.certified.append((enc[key].title.strip() or key, enc[key], gui[key]))
    report.single_sided = sorted(set(enc) ^ set(gui))
    log.info("双 UP 交集：%s 个梗；单边：%s 个", len(shared), len(report.single_sided))
    return report
