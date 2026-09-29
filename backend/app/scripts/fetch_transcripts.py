"""把解说视频的字幕原文抓进 `video_transcripts`，给详情页的「这个梗是什么」补内容层。

为什么要有这一步：以前详情页只有解说视频的**标题和简介**。标题是「XX梗到底是啥」，
简介是 UP 主随手写的推广话——都不是视频里真正讲的内容。想知道梗的来历，只有字幕。

代价要先说清楚（2026-09-29 实测）：B 站字幕轨只在**登录态**下下发，匿名请求
`player/wbi/v2` 返回 code=0 但 `subtitles` 是空数组，AI 视频总结端点直接 -101。
所以这个脚本没有 BILI_COOKIE 就是白跑，脚本会先拦下来告诉你，不会烧请求数。

    python -m app.scripts.fetch_transcripts                 # 所有真实梗的双 UP 认证视频
    python -m app.scripts.fetch_transcripts --ids 47 12     # 点名几个梗
    python -m app.scripts.fetch_transcripts --top 3         # 再抓每个梗播放最高的 3 条
    python -m app.scripts.fetch_transcripts --bvids BV1xx  # 只试某几条视频（排查用）
    python -m app.scripts.fetch_transcripts --dry-run       # 只看清单和接口结论，不写库

抓到的字幕按 bvid 去重：已经在库里的默认跳过（字幕不会天天改），`--force` 才重抓。
结束时如实报覆盖率——多少拿到人工 CC、多少只有 AI 识别、多少根本没字幕轨、
多少被风控，四类分开列，别把「没抓到」混成「抓到了但没用」。
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import datetime

from sqlalchemy import select

from app.collectors.bilibili import BilibiliBlocked, get_client
from app.config import get_logger, settings
from app.models import Meme, MemeCertification, SessionLocal, Video, VideoTranscript
from app.models.base import ensure_schema
from app.models.transcript import TRANSCRIPT_LABELS, TranscriptKind

log = get_logger("fetch_transcripts")

# 每条请求之间的小憩：字幕要连打 view + player + 下载三次，全库连打必撞风控
DEFAULT_SLEEP = 1.5


def reason_bucket(reason: str) -> str:
    """把一句人话失败原因归到可统计的档位里（覆盖率报告要的是分母，不是一串字符串）。"""
    if not reason:
        return "unknown"
    if "风控" in reason or "412" in reason or "安全校验" in reason:
        return "blocked"
    if "匿名" in reason:
        return "anonymous"
    if "没有字幕轨" in reason:
        return "no_track"
    if "cid" in reason:
        return "no_cid"
    if "下载" in reason:
        return "download_failed"
    if "空的" in reason or "下载地址" in reason:
        return "empty"
    return "request_failed"


def collect_targets(
    session,
    *,
    meme_ids: list[int] | None,
    limit: int | None,
    top: int,
    include_demo: bool,
) -> list[dict]:
    """待抓清单：每个梗先排双 UP 认证视频，再排播放最高的相关视频。

    同一 bvid 只留一次（两个梗命中同一条视频时，归属第一个梗）。
    """
    stmt = select(Meme).order_by(Meme.id)
    if meme_ids:
        stmt = stmt.where(Meme.id.in_(meme_ids))
    elif not include_demo:
        stmt = stmt.where(Meme.data_source == "bilibili")
    memes = list(session.scalars(stmt))
    if limit:
        memes = memes[:limit]

    wanted: list[dict] = []
    seen: set[str] = set()
    for meme in memes:
        certs = list(
            session.scalars(
                select(MemeCertification)
                .where(
                    MemeCertification.meme_id == meme.id,
                    MemeCertification.confirmed.is_(True),
                    MemeCertification.bvid != "",
                )
                .order_by(MemeCertification.role)
            )
        )
        for cert in certs:
            if cert.bvid not in seen:
                seen.add(cert.bvid)
                wanted.append(
                    {
                        "meme_id": meme.id,
                        "meme_name": meme.name,
                        "bvid": cert.bvid,
                        "title": cert.video_title or "",
                        "why": f"{cert.up_name}认证解说",
                    }
                )
        if top > 0:
            videos = list(
                session.scalars(
                    select(Video)
                    .where(Video.meme_id == meme.id, Video.data_source == "bilibili")
                    .order_by(Video.view.desc())
                    .limit(top)
                )
            )
            for video in videos:
                if video.bvid and video.bvid not in seen:
                    seen.add(video.bvid)
                    wanted.append(
                        {
                            "meme_id": meme.id,
                            "meme_name": meme.name,
                            "bvid": video.bvid,
                            "title": video.title,
                            "why": f"头部相关视频（{video.view} 播放）",
                        }
                    )
    return wanted


def store(session, item: dict, result, *, dry_run: bool) -> None:
    if dry_run:
        return
    row = session.get(VideoTranscript, result.bvid)
    if row is None:
        row = VideoTranscript(bvid=result.bvid)
        session.add(row)
    row.meme_id = item["meme_id"]
    row.cid = result.cid
    # view 下发的当前标题优先：库里存的标题是抓取当时的，UP 主改过题就对不上了
    row.video_title = ((result.title or item.get("title") or ""))[:250]
    row.kind = result.kind or TranscriptKind.CC
    row.lang = result.lang
    row.text = result.text
    row.chars = len(result.text)
    row.logged_in = bool(result.logged_in)
    row.fetched_at = datetime.now()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓 B 站解说视频字幕入库")
    parser.add_argument("--ids", type=int, nargs="*", default=None, help="只处理这些梗 id")
    parser.add_argument("--limit", type=int, default=None, help="最多处理几个梗")
    parser.add_argument("--top", type=int, default=0, help="每个梗额外抓播放最高的 N 条相关视频")
    parser.add_argument("--bvids", nargs="*", default=None, help="直接点 name bvid（排查用，忽略梗清单）")
    parser.add_argument("--force", action="store_true", help="已在库里的字幕也重抓")
    parser.add_argument("--all", action="store_true", help="连演示来源的梗一起抓（默认只抓真实梗）")
    parser.add_argument("--dry-run", action="store_true", help="只打印清单，不发请求也不写库")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="每条视频的间隔秒数")
    parser.add_argument(
        "--allow-anonymous", action="store_true",
        help="没配 BILI_COOKIE 也照跑（只会证明匿名拿不到轨，用来核对接口结论）",
    )
    args = parser.parse_args(argv)

    ensure_schema()
    client = get_client()

    if not client.cookie:
        print(
            "没有 BILI_COOKIE：B 站只对登录态下发字幕轨，匿名请求返回的是空数组。\n"
            "请在 backend/.env 里填 BILI_COOKIE（浏览器登录 B 站后从请求头整段复制）再跑。\n"
            "想先看清单可以用 --dry-run；想验证「匿名确实拿不到」加 --allow-anonymous。"
        )
        if not args.dry_run and not args.allow_anonymous:
            return 2

    session = SessionLocal()
    try:
        if args.bvids:
            wanted = [
                {
                    "meme_id": None,
                    "meme_name": "（点名）",
                    "bvid": bvid,
                    "title": "",
                    "why": "手工指定",
                }
                for bvid in args.bvids
            ]
        else:
            wanted = collect_targets(
                session,
                meme_ids=args.ids,
                limit=args.limit,
                top=args.top,
                include_demo=args.all,
            )

        have = set(session.scalars(select(VideoTranscript.bvid)))
        pending = [item for item in wanted if args.force or item["bvid"] not in have]
        skipped_done = len(wanted) - len(pending)
        print(
            f"清单：{len(wanted)} 条视频（{len(wanted) - len(pending)} 条已有字幕，跳过）\n"
            f"待抓：{len(pending)} 条，每条最多 3 个请求（view / player / 字幕文件）"
            f"，约 {len(pending) * (3 * args.sleep + 1):.0f} 秒"
            + ("；dry-run 不写库" if args.dry_run else "")
        )
        if args.dry_run:
            for item in pending[:20]:
                print(f"  - [{item['meme_name']}] {item['bvid']}  {item['why']}  {item['title'][:30]}")
            if len(pending) > 20:
                print(f"  …另有 {len(pending) - 20} 条")
            return 0

        stats: Counter[str] = Counter()
        chars = 0
        blocked: str = ""
        for index, item in enumerate(pending, start=1):
            try:
                result = client.subtitle_of(item["bvid"])
            except BilibiliBlocked as exc:
                log.warning("[%d/%d] %s 被风控：%s，停止", index, len(pending), item["bvid"], exc)
                stats["blocked"] += 1
                blocked = str(exc)
                break
            except Exception as exc:  # noqa: BLE001 - 一条视频失败不该拖垮整轮
                session.rollback()
                log.warning("[%d/%d] %s 抓取异常：%s", index, len(pending), item["bvid"], exc)
                stats["request_failed"] += 1
                continue

            if result.ok:
                store(session, item, result, dry_run=args.dry_run)
                session.commit()
                stats[result.kind or "cc"] += 1
                chars += len(result.text)
                log.info(
                    "[%d/%d] [%s] %s ← %s：%d 字（%s）",
                    index, len(pending), item["meme_name"], item["bvid"],
                    TRANSCRIPT_LABELS.get(result.kind, result.kind), len(result.text), item["why"],
                )
            else:
                bucket = reason_bucket(result.reason)
                stats[bucket] += 1
                log.warning(
                    "[%d/%d] [%s] %s 没拿到：%s",
                    index, len(pending), item["meme_name"], item["bvid"], result.reason,
                )
            if index < len(pending):
                time.sleep(args.sleep)

        total = sum(stats.values())
        got = stats[TranscriptKind.CC] + stats[TranscriptKind.AI]
        print(f"\n处理 {total} 条：有字幕 {got}，无字幕/失败 {total - got}")
        for key, label in (
            (TranscriptKind.CC, "人工 CC 字幕"),
            (TranscriptKind.AI, "AI 识别字幕"),
            ("anonymous", "匿名请求拿不到轨（要配 cookie）"),
            ("no_track", "这条视频确实没字幕轨"),
            ("blocked", "被风控中断"),
            ("no_cid", "视频查不到 cid（可能已删）"),
            ("download_failed", "字幕文件下载失败"),
            ("empty", "字幕轨是空的"),
            ("request_failed", "接口报错"),
        ):
            if stats[key]:
                pct = stats[key] / total * 100 if total else 0
                print(f"  {label}：{stats[key]} 条（{pct:.0f}%）")
        if got:
            print(f"  字幕合计 {chars} 字，平均每条 {chars / got:.0f} 字")
        if blocked:
            print(f"\n风控中断：{blocked}\n稍后重跑同一命令即可，已入库的会自动跳过。")
        if settings.data_source != "bilibili":
            print("提醒：当前 DATA_SOURCE 不是 bilibili，详情页展示的仍是演示数据。")
        return 0 if got or not pending else 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
