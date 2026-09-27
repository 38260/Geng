"""双 UP 认证的在线核验。

现实约束（本机实测，2026-09-27）：
* `space/wbi/arc/search`（UP 主投稿列表）带匿名指纹后**偶尔**可用，深翻页基本被 -352/412 挡住；
* `wbi/search/type` 对匿名请求会**间歇性返回空结果**（同一查询上一次 9 条含该 UP，下一次 0 条）。

所以这里只做"有把握的正向确认"：
在真实拉到的投稿索引里命中某个梗 → 认证通过，并记下真实 bvid / 标题 / 发布时间；
没命中 → 标记为「未在线验证」，**绝不**把演示证据或猜测当成已认证。

索引缓存到 data/up_index.json，避免每次都去撞风控。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from app.config import BACKEND_DIR, get_logger
from app.models import Meme

from ...collectors.bilibili import BilibiliBlocked, BiliClient
from .certification import ENCYCLOPEDIA, GUIDE, UpAuthor
from .discovery import UpVideo, fetch_up_index, index_by_meme

log = get_logger(__name__)

INDEX_FILE = BACKEND_DIR / "data" / "up_index.json"
AUTHORS: dict[str, UpAuthor] = {ENCYCLOPEDIA.role: ENCYCLOPEDIA, GUIDE.role: GUIDE}


@dataclass
class RoleEvidence:
    """某一位 UP 主对该梗的核验结果。"""

    role: str
    up_name: str
    up_mid: int
    verified: bool = False
    bvid: str = ""
    video_title: str = ""
    published_at: datetime | None = None
    note: str = "未在线验证"


@dataclass
class VerificationOutcome:
    meme_name: str
    roles: dict[str, RoleEvidence] = field(default_factory=dict)

    @property
    def both_verified(self) -> bool:
        return len(self.roles) == 2 and all(item.verified for item in self.roles.values())

    @property
    def state(self) -> str:
        if self.both_verified:
            return "verified_both"
        if any(item.verified for item in self.roles.values()):
            return "partially_verified"
        return "unverified"


def _serialise(indexes: dict[str, dict[str, UpVideo]]) -> dict:
    return {
        author: {
            key: {**asdict(video), "pubdate": video.pubdate.isoformat()}
            for key, video in items.items()
        }
        for author, items in indexes.items()
    }


def _deserialise(raw: dict) -> dict[str, dict[str, UpVideo]]:
    out: dict[str, dict[str, UpVideo]] = {}
    for author, items in (raw.get("indexes") or {}).items():
        videos: dict[str, UpVideo] = {}
        for key, payload in items.items():
            try:
                pubdate = datetime.fromisoformat(str(payload.get("pubdate")))
            except ValueError:
                pubdate = datetime.min
            videos[key] = UpVideo(
                bvid=payload.get("bvid", ""),
                title=payload.get("title", ""),
                pubdate=pubdate,
                mid=int(payload.get("mid") or 0),
                author=payload.get("author", author),
                play=int(payload.get("play") or 0),
            )
        out[author] = videos
    return out


def load_or_build_index(
    client: BiliClient,
    *,
    max_pages: int = 4,
    gap: float = 1.5,
    refresh: bool = False,
    cache_hours: float = 12.0,
) -> tuple[dict[str, dict[str, UpVideo]], str]:
    """返回 (索引, 状态说明)。缓存命中就不去撞风控。"""
    fresh_until = datetime.now().timestamp() - cache_hours * 3600
    if not refresh and INDEX_FILE.exists():
        try:
            raw = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            if float(raw.get("built_at_ts") or 0) >= fresh_until:
                indexes = _deserialise(raw)
                if indexes:
                    counts = {author: len(items) for author, items in indexes.items()}
                    return indexes, f"复用 {INDEX_FILE.name} 缓存（{counts}）"
        except Exception as exc:  # noqa: BLE001 - 缓存坏了就重建
            log.warning("索引缓存不可用，将重新拉取：%s", exc)

    indexes: dict[str, dict[str, UpVideo]] = {}
    notes: list[str] = []
    for role, author in AUTHORS.items():
        try:
            videos, pages_ok, blocked = fetch_up_index(client, author, max_pages=max_pages, gap=gap)
        except BilibiliBlocked as exc:
            notes.append(f"{author.name}: {exc}")
            continue
        indexes[author.name] = index_by_meme(videos)
        notes.append(f"{author.name}: {pages_ok} 页 / {len(videos)} 条投稿 / {blocked} 次被风控")
        log.info("核验索引 %s", notes[-1])

    if indexes:
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_FILE.write_text(
            json.dumps(
                {"built_at_ts": datetime.now().timestamp(), "indexes": _serialise(indexes)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return indexes, "；".join(notes) or "未能拉到任何投稿"


def _match_key(name: str) -> str:
    return (name or "").strip().lower()


def verify_meme(meme: Meme, indexes: dict[str, dict[str, UpVideo]]) -> VerificationOutcome:
    """在真实投稿索引里找这个梗被哪位 UP 主介绍过。"""
    outcome = VerificationOutcome(meme_name=meme.name)
    terms = [meme.name, *(meme.aliases or [])]

    for role, author in AUTHORS.items():
        evidence = RoleEvidence(role=role, up_name=author.name, up_mid=author.mid)
        items = indexes.get(author.name) or {}
        for term in terms:
            hit = items.get(_match_key(term))
            if hit:
                evidence.verified = True
                evidence.bvid = hit.bvid
                evidence.video_title = hit.title
                evidence.published_at = hit.pubdate
                evidence.note = "已在该 UP 主真实投稿中命中"
                break
        if not evidence.verified:
            evidence.note = (
                "未在该 UP 主已拉取的投稿中命中"
                + ("" if items else "（该 UP 索引为空：接口被风控）")
            )
        outcome.roles[role] = evidence
    return outcome


def apply_outcome(session, meme: Meme, outcome: VerificationOutcome) -> int:
    """把核验结果写回认证记录。

    规则：**只有正向命中才改数据**。抽样里没找到不等于该 UP 没做过
    （我们只能翻动几页投稿，接口在限流），所以未命中时只把证据标成
    "未在线核验"、清掉可能存在的假 BV 号，但不撤销认证位——
    撤销会让整库被误降级，等于用一个测不准的接口去否定人工整理的梗库。
    """
    from .certification import get_or_create_certification, recompute_certification

    upgraded = 0
    for role, evidence in outcome.roles.items():
        record = get_or_create_certification(session, meme, role)
        record.up_name = evidence.up_name
        record.up_mid = evidence.up_mid
        if evidence.verified:
            record.confirmed = True
            record.bvid = evidence.bvid
            record.video_title = evidence.video_title
            record.published_at = evidence.published_at
            record.video_url = f"https://www.bilibili.com/video/{evidence.bvid}"
            record.data_source = "bilibili"          # 真实证据，前端可点开
            record.confirmed_at = record.confirmed_at or datetime.now()
            upgraded += 1
        else:
            # 未命中：保留人工整理的认证位，但绝不保留伪造的 BV 号
            record.bvid = ""
            record.video_title = ""
            record.video_url = ""
            record.published_at = None
            if record.data_source != "bilibili":
                record.data_source = "unverified"
    recompute_certification(meme)
    meme.verification_state = outcome.state
    return upgraded
