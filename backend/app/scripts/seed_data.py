"""生成 / 重建演示数据。

    python -m app.scripts.seed_data            # 重建全部演示数据
    python -m app.scripts.seed_data --days 30  # 指定时间窗口

只有双 UP 认证通过的梗才会被写入时间序列（未认证梗保留为 candidate，
用于证明认证闸门真的在工作）。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from app.analytics import MemeTerms, match_videos
from app.collectors.base import CollectedBundle
from app.collectors.mock_collector import MockCollector
from app.config import get_logger, settings
from app.models import (
    Meme,
    MemeDailyStats,
    MemeStatus,
    SessionLocal,
    Video,
    init_db,
    reset_db,
)
from app.services.meme.certification import record_certification, recompute_certification
from app.mock.catalogue import MEME_CATALOGUE, MemeSpec, stage_counts

log = get_logger(__name__)


def _slug(index: int, spec: MemeSpec) -> str:
    return f"meme-{index:02d}"


def upsert_meme(session, spec: MemeSpec, index: int) -> Meme:
    meme = session.query(Meme).filter(Meme.name == spec.name).one_or_none()
    if meme is None:
        meme = Meme(name=spec.name)
        session.add(meme)
    meme.slug = _slug(index, spec)
    meme.aliases = list(spec.aliases)
    meme.keywords = list(spec.keywords)
    meme.description = spec.description
    meme.data_source = "mock"
    meme.status = MemeStatus.CANDIDATE
    recompute_certification(meme)
    session.flush()
    return meme


def purge_generated(session, meme: Meme) -> None:
    """重跑 seed 时清掉旧的演示数据，避免叠加。"""
    session.query(MemeDailyStats).filter(MemeDailyStats.meme_id == meme.id).delete()
    session.query(Video).filter(Video.meme_id == meme.id).delete()
    session.commit()


def real_footprint(session=None) -> tuple[int, int]:
    """库里还留着多少 B 站真实采集的数据（梗数、日统计行数）。"""
    from sqlalchemy import func

    own = session is None
    session = session or SessionLocal()
    try:
        init_db()
        memes = session.query(func.count(func.distinct(MemeDailyStats.meme_id))).filter(
            MemeDailyStats.data_source == "bilibili"
        ).scalar()
        rows = session.query(func.count(MemeDailyStats.stat_date)).filter(
            MemeDailyStats.data_source == "bilibili"
        ).scalar()
        return int(memes or 0), int(rows or 0)
    finally:
        if own:
            session.close()


def seed(days: int | None = None, do_reset: bool = True, force: bool = False) -> dict[str, int]:
    window_days = days or settings.analysis_window_days
    collector = MockCollector()

    if not force:
        # 演示数据是整库重建（reset_db 会 drop 所有表），拿它盖掉真实采集
        # 结果是致命的——本项目就翻过一次这个车。所以默认拒绝，要覆盖得显式 --force。
        memes, rows = real_footprint()
        if rows:
            raise RuntimeError(
                f"库里还有 {memes} 个梗 / {rows} 行 B 站真实采集数据，"
                "演示数据会整库重建并删掉它们。确认要覆盖请加 --force。"
            )

    if do_reset:
        reset_db()
    else:
        init_db()

    session = SessionLocal()
    summary = {"memes": 0, "certified": 0, "candidate": 0, "stats": 0, "videos": 0}
    try:
        for index, spec in enumerate(MEME_CATALOGUE, start=1):
            meme = upsert_meme(session, spec, index)
            summary["memes"] += 1

            bundle: CollectedBundle = collector.collect(meme, window_days=window_days)
            for evidence in bundle.certifications:
                record_certification(
                    session,
                    meme,
                    evidence.role,
                    bvid=evidence.bvid,
                    video_title=evidence.video_title,
                    published_at=evidence.published_at,
                    confirmed=evidence.confirmed,
                    data_source=evidence.data_source,
                )
            session.flush()

            purge_generated(session, meme)

            if meme.certified:
                summary["certified"] += 1
                # 演示数据也走一遍相关性打分：抽查列表里显示的分数得是真算出来的，
                # 全留 0 会让人以为这些样本根本没通过过滤。
                match_videos(MemeTerms.from_meme(meme), bundle.videos)
                for stat in bundle.daily_stats:
                    stat.meme_id = meme.id
                    session.add(stat)
                for video in bundle.videos:
                    video.meme_id = meme.id
                    session.add(video)
                summary["stats"] += len(bundle.daily_stats)
                summary["videos"] += len(bundle.videos)
                meme.data_updated_at = datetime.now()
            else:
                summary["candidate"] += 1
                log.info("跳过未认证梗：%s（梗百科=%s 梗指南=%s）",
                         meme.name, meme.encyclopedia_confirmed, meme.guide_confirmed)

        session.commit()
    finally:
        session.close()

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 演示数据生成")
    parser.add_argument("--days", type=int, default=settings.analysis_window_days)
    parser.add_argument("--no-reset", action="store_true", help="保留表结构，仅覆盖演示数据")
    parser.add_argument("--force", action="store_true", help="确认覆盖库里的 B 站真实采集数据")
    args = parser.parse_args(argv)

    try:
        summary = seed(days=args.days, do_reset=not args.no_reset, force=args.force)
    except RuntimeError as exc:
        print(f"已中止：{exc}")
        return 2
    print(
        "演示数据写入完成："
        f"梗 {summary['memes']} 个（正式 {summary['certified']} / 候选 {summary['candidate']}），"
        f"每日统计 {summary['stats']} 行，视频样本 {summary['videos']} 条"
    )
    print("生命周期原型分布：", stage_counts())
    print("下一步：python -m app.scripts.run_pipeline  # 计算热度指数与生命周期")
    return 0


if __name__ == "__main__":
    sys.exit(main())
