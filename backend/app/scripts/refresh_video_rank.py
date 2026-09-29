"""只补「B 站综合排序名次」的轻量脚本：每个梗 1~2 次请求，不重采日序列。

为什么单独一个脚本：默认排序要的是 `videos.search_rank`，那是"在 B 站搜这个词
看到的第几条"。逐日头部样本采回来的视频根本没有这个信息，而重跑一遍 30 天
序列要两个多小时——为一个排名字段烧两次风控额度不值。

    python -m app.scripts.refresh_video_rank                 # 全库真实梗
    python -m app.scripts.refresh_video_rank --ids 47 12     # 点名几个
    python -m app.scripts.refresh_video_rank --limit 5       # 先试 5 个
    python -m app.scripts.refresh_video_rank --dry-run       # 只看会写什么

综合排序里出现、但库里没有的视频会一并入库（搜索行自带标题/封面/播放/弹幕/
发布时间，点赞投币要另开接口，这里不补——列表只用前者）。
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

from sqlalchemy import select

from app.collectors import make_collector
from app.collectors.bilibili import BilibiliBlocked
from app.config import get_logger, settings
from app.models import Meme, SessionLocal, Video
from app.models.base import ensure_schema

log = get_logger("refresh_rank")


def refresh_one(session, collector, meme: Meme, *, dry_run: bool) -> tuple[int, int]:
    """返回 (补上的名次条数, 新入库的视频条数)。"""
    ranked = collector._totalrank(meme)
    # 同一页里偶尔会重复出现同一个 bvid（B 站自己给的结果就不去重），
    # 只留第一次出现的名次，否则第二次插入会撞 videos.meme_id+bvid 唯一键
    first_seen: dict[str, dict] = {}
    for item in ranked:
        first_seen.setdefault(item["bvid"], item)
    ranked = list(first_seen.values())
    if not ranked:
        return 0, 0
    # 唯一键是 (meme_id, bvid)，不含 data_source：按来源过滤着查，
    # 就会漏掉"这条视频以演示来源先入库了"的情况，再插入直接 IntegrityError
    stored = {
        row.bvid: row
        for row in session.scalars(select(Video).where(Video.meme_id == meme.id))
    }
    touched = 0
    added = 0
    for item in ranked:
        row = stored.get(item["bvid"])
        if row is None:
            added += 1
            if dry_run:
                continue
            session.add(
                Video(
                    meme_id=meme.id,
                    bvid=item["bvid"],
                    aid=item.get("aid"),
                    title=str(item.get("title") or "")[:250],
                    description=str(item.get("description") or ""),
                    author=str(item.get("author") or ""),
                    author_mid=item.get("author_mid"),
                    cover=str(item.get("cover") or ""),
                    tags=[],
                    publish_time=item["publish_time"],
                    crawl_time=datetime.now(),
                    duration_seconds=int(item.get("duration_seconds") or 0),
                    view=int(item.get("view") or 0),
                    reply=int(item.get("reply") or 0),
                    danmaku=int(item.get("danmaku") or 0),
                    relevance_score=float(item.get("relevance_score") or 0.0),
                    matched_terms=list(item.get("matched_terms") or []),
                    search_rank=int(item["search_rank"]),
                    data_source=collector.source,
                )
            )
            continue
        if row.search_rank != item["search_rank"]:
            touched += 1
            if not dry_run:
                row.search_rank = item["search_rank"]
    if not dry_run:
        session.commit()
    return touched, added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="补 B 站综合排序名次（默认排序用）")
    parser.add_argument("--ids", type=int, nargs="*", default=None, help="只处理这些梗 id")
    parser.add_argument("--limit", type=int, default=None, help="最多处理几个梗")
    parser.add_argument("--all", action="store_true", help="连演示来源的梗也刷（默认只刷真实梗）")
    parser.add_argument("--dry-run", action="store_true", help="不写库，只报会改多少")
    parser.add_argument(
        "--gap", type=float, default=2.5,
        help="两个梗之间的间隔秒数。连打会被 B 站回空页（code=0 但 result 为空），"
             "空页重试三次仍空就等于这条梗一条名次都没拿到",
    )
    args = parser.parse_args(argv)

    ensure_schema()
    if settings.data_source != "bilibili" and not args.all:
        print(f"当前数据源是 {settings.data_source}，演示梗没有真实名次可取。加 --all 强制。")
        return 2

    collector = make_collector("bilibili")
    ok, reason = collector.is_available()
    if not ok:
        print(f"接口不可用：{reason}")
        return 2

    session = SessionLocal()
    try:
        stmt = select(Meme).order_by(Meme.id)
        if args.ids:
            stmt = stmt.where(Meme.id.in_(args.ids))
        elif not args.all:
            stmt = stmt.where(Meme.data_source == "bilibili")
        memes = list(session.scalars(stmt))
        if args.limit:
            memes = memes[: args.limit]
        log.info("待补名次的梗：%d 个（dry_run=%s）", len(memes), args.dry_run)

        done = skipped = failed = 0
        for index, meme in enumerate(memes, start=1):
            try:
                touched, added = refresh_one(session, collector, meme, dry_run=args.dry_run)
            except BilibiliBlocked as exc:
                log.warning("梗「%s」被风控：%s，停止", meme.name, exc)
                failed += 1
                break
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                log.warning("梗「%s」补名次失败：%s", meme.name, exc)
                failed += 1
                continue
            done += 1
            if index < len(memes) and args.gap > 0:
                time.sleep(args.gap)
            skipped += 1 if not (touched or added) else 0
            log.info("[%d/%d] %s：更新名次 %d，新入库 %d", index, len(memes), meme.name, touched, added)
        print(
            f"\n完成 {done} 个梗（其中 {skipped} 个名次无变化），新入库视频见上面日志，失败 {failed} 个"
            + ("（dry-run，未写库）" if args.dry_run else "")
        )
        return 1 if failed else 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
