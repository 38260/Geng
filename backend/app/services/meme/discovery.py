"""从两位 UP 主的真实投稿里构建梗库候选池（发现层的真实实现）。

之前认证证据是演示数据里造的假 BV 号——那不能算真数据。这里的做法是：

    翻页拉取 梗百科 / 梗指南 的投稿 → 从标题里抽取梗名
    → **取并集**：任一 UP 主在认证窗口（默认 90 天滚动）内介绍过就进候选池
    → 池子里的梗带上真实 bvid / 标题 / 发布时间，两位都做过的那批另标「双 UP 认证」

为什么不再取交集：交集是拿"两位 UP 的排期都要撞上"当门槛，实测 90 天里
梗百科单独介绍过 37 个梗、梗指南 22 个，交集只剩 8 个——日更 UP 的选题被
周更 UP 的排期 veto，梗库必然漏掉正在热的梗（「闪身步」实测热度 81.0 就是这么漏的）。
交集降级成标签，不再当闸门。

空间接口限流很凶（大量 412/-352），所以索引拉取带退避重试；并且只拿到一位 UP
的数据也照样出池（梗百科是主来源），拉不到的部分如实报告，不拿旧证据凑数。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

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
# UP 主为了避敏感词会把梗名写成占位（"xx在哪"、"你会xxx吗"）。这种名字不能拿去搜索，
# 采回来的全是噪声，所以抽取阶段就丢掉——跟"宁可漏不可造"是同一条底线。
PLACEHOLDER = re.compile(r"[xXｘＸ×]{2,}")
# 短于此长度不做写法合并：两三个字的梗名互相包含纯属巧合（"牛来" ⊂ "牛来也"）
MIN_MERGE_LEN = 4


@dataclass
class UpVideo:
    bvid: str
    title: str
    pubdate: datetime
    mid: int
    author: str
    play: int = 0


@dataclass
class PoolEntry:
    """候选池里的一条：梗名 + 各自那一期真实投稿（没做过的那一边就是 None）。"""

    key: str
    encyclopedia: UpVideo | None = None
    guide: UpVideo | None = None

    @property
    def name(self) -> str:
        video = self.encyclopedia or self.guide
        return (video.title.strip() if video and video.title.strip() else self.key)

    @property
    def both(self) -> bool:
        return bool(self.encyclopedia and self.guide)

    @property
    def certified_by(self) -> list[str]:
        """证据来自哪一位 UP（顺序固定：梗百科在前，它是主来源）。"""
        out: list[str] = []
        if self.encyclopedia:
            out.append(ENCYCLOPEDIA.name)
        if self.guide:
            out.append(GUIDE.name)
        return out

    @property
    def cert_label(self) -> str:
        if self.both:
            return "双 UP 认证"
        return f"{self.certified_by[0]}认证" if self.certified_by else "未认证"


@dataclass
class DiscoveryReport:
    per_author: dict[str, int] = field(default_factory=dict)
    pages_fetched: dict[str, int] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)
    extracted: dict[str, int] = field(default_factory=dict)
    pool: list[PoolEntry] = field(default_factory=list)
    certified: list[tuple[str, UpVideo, UpVideo]] = field(default_factory=list)
    single_sided: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def double(self) -> list[PoolEntry]:
        return [entry for entry in self.pool if entry.both]


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
    # 冒号/破折号前往往才是梗名："XX：一句话解释" → 叫 XX。
    # 优先取这一截，否则整条"XX：一句话解释"会当成梗名进库，既难看又搜不到。
    heads: list[str] = []
    for candidate in candidates:
        for splitter in ("：", ":", "—", "|", "｜"):
            if splitter in candidate:
                head = candidate.split(splitter)[0].strip()
                if head:
                    heads.append(head)

    for candidate in [*heads, *candidates]:
        cleaned = re.sub(r"^[\s「『\"'']+", "", candidate).strip(" \t\"'』」？?！!。.，,、")
        if not (2 <= len(cleaned) <= 16):
            continue
        if any(word in cleaned for word in _STOP_WORDS):
            continue
        if PLACEHOLDER.search(cleaned):
            continue        # 避敏感词写成的 "xx/xxx" 占位名，搜不动也不该入库
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
    """梗名 -> 该 UP 主**最近**介绍它的那期。

    认证窗口是 90 天滚动的，所以证据要取最新一期：拿首发那期当证据，
    一个被反复回锅的老梗会一直"看起来是新的"，而窗口内的最新投稿才是
    "这段时间确实介绍过"的凭据。
    """
    index: dict[str, UpVideo] = {}
    for video in sorted(videos, key=lambda item: item.pubdate, reverse=True):
        name = extract_meme_name(video.title)
        if not name:
            continue
        key = name.lower()
        if key not in index:
            index[key] = video
    return index


def merge_pool(
    enc: dict[str, UpVideo], gui: dict[str, UpVideo]
) -> tuple[list[PoolEntry], list[tuple[str, str]]]:
    """并集入池（梗百科在前），并把"写法不同、显然是同一个梗"的条目合并。

    合并条件刻意保守：**只有一方的梗名是另一方的连续子串**才算同一个梗
    （"胆子肥嘟嘟" ⊂ "胆子肥嘟嘟的"）。只是长得像的不并（"宗主第一招"和
    "宗主第二招"很可能是两个梗），宁可在库里留两条让人去梗管理页判断，
    也不要机器悄悄把两个梗的证据合成一条。

    返回 (池子, 合并记录[(保留的名字, 被并掉的写法)])。
    """
    pool: list[PoolEntry] = []
    for key in sorted(enc, key=lambda k: enc[k].pubdate, reverse=True):
        pool.append(PoolEntry(key, enc[key], gui.get(key)))

    merged: list[tuple[str, str]] = []
    rest = sorted((k for k in gui if k not in enc), key=lambda k: gui[k].pubdate, reverse=True)
    for key in rest:
        target = next(
            (
                entry
                for entry in pool
                if entry.key
                and (
                    (len(key) >= MIN_MERGE_LEN and key in entry.key)
                    or (len(entry.key) >= MIN_MERGE_LEN and entry.key in key)
                )
            ),
            None,
        )
        if target is None:
            pool.append(PoolEntry(key, None, gui[key]))
            continue
        target.guide = gui[key]
        merged.append((target.key, key))
        log.info("合并写法差异：「%s」←「%s」（同一梗，两种标题写法）", target.key, key)
    return pool, merged


def discover(
    client: BiliClient,
    *,
    max_pages: int = 8,
    gap: float = 1.2,
    cert_days: int | None = None,
) -> DiscoveryReport:
    """拉两位 UP 主的投稿，按**并集**建候选池（梗百科为主、梗指南补）。

    ``cert_days`` 是认证窗口（默认取 ``settings.cert_window_days``=90 天滚动）：
    只看这段时间内的投稿，窗口外的老梗不再算"最近介绍过"。
    """
    from app.config import settings

    window = cert_days or int(getattr(settings, "cert_window_days", 90))
    not_before = datetime.now() - timedelta(days=window)

    report = DiscoveryReport()
    indexes: dict[str, dict[str, UpVideo]] = {}

    for author in (ENCYCLOPEDIA, GUIDE):
        try:
            videos, pages_ok, blocked = fetch_up_index(
                client, author, max_pages=max_pages, gap=gap, not_before=not_before
            )
        except Exception as exc:  # noqa: BLE001 - 单个 UP 失败要如实报告而不是假装成功
            report.errors.append(f"{author.name}: {exc}")
            continue
        report.per_author[author.name] = len(videos)
        report.pages_fetched[author.name] = pages_ok
        report.failures[author.name] = blocked
        indexes[author.name] = index_by_meme(
            [video for video in videos if video.pubdate >= not_before]
        )
        report.extracted[author.name] = len(indexes[author.name])
        log.info("%s：拉到 %s 条投稿，%s 天内识别出 %s 个梗名（%s 页成功 / %s 次被风控）",
                 author.name, len(videos), window, len(indexes[author.name]), pages_ok, blocked)

    if not indexes:
        log.warning("两位 UP 主的投稿都拉不到，候选池为空：%s", "；".join(report.errors))
        return report
    if len(indexes) < 2:
        missing = {ENCYCLOPEDIA.name, GUIDE.name} - set(indexes)
        log.warning("%s 的投稿拉不到（%s），本轮只用并集里拿到的那部分入池",
                    "、".join(missing), "；".join(report.errors))

    enc = indexes.get(ENCYCLOPEDIA.name, {})
    gui = indexes.get(GUIDE.name, {})
    pool, merged = merge_pool(enc, gui)
    report.pool = pool
    report.certified = [
        (entry.encyclopedia.title.strip() or entry.key, entry.encyclopedia, entry.guide)
        for entry in pool
        if entry.both and entry.encyclopedia and entry.guide
    ]
    report.single_sided = [entry.key for entry in pool if not entry.both]
    log.info(
        "并集候选池：%s 个梗（双 UP：%s／仅梗百科：%s／仅梗指南：%s／写法合并：%s）",
        len(pool),
        len(report.certified),
        sum(1 for e in pool if e.encyclopedia and not e.guide),
        sum(1 for e in pool if e.guide and not e.encyclopedia),
        len(merged),
    )
    return report
