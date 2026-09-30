# -*- coding: utf-8 -*-
"""Normalise the legacy ``data_source=''`` state to ``pending``.

来历：新建梗时写的是空串，于是库里出现第三种"无来源"状态——
既不是 ``bilibili`` 也不是 ``mock``，既进不了真实榜单也拿不到演示标注，
界面上无从解释。模型与两个写入点已经修好，这个脚本负责把历史数据对齐。

第二类要修的是**标错来源**：``data_source='mock'`` 但库里已经躺着 B 站真实序列的梗
（「你干嘛哎哟」就是——30 天真实日统计，标签还停在演示时代）。
这种不能删（数据是真的），只能把标签改对，否则真实模式下它会被
`_demo_only_ids` 之类"纯演示"判定误伤，也会让用户以为榜单里混了假数字。

    python -m app.scripts.fix_data_source_state            # 只报告
    python -m app.scripts.fix_data_source_state --apply    # 真的改
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, or_, select, union, update

from app.config.logging import get_logger
from app.models import Meme, MemeDailyStats, SessionLocal, Video

log = get_logger(__name__)

PENDING = "pending"
BILIBILI = "bilibili"


def _affected(session):
    return list(session.scalars(
        select(Meme).where(or_(Meme.data_source.is_(None), Meme.data_source == ""))))


def _mislabelled(session):
    """标着 mock、但已经有 B 站真实序列或真实视频的梗：错的是标签，不是数据。"""
    real_ids = union(
        select(MemeDailyStats.meme_id).where(MemeDailyStats.data_source == BILIBILI),
        select(Video.meme_id).where(Video.data_source == BILIBILI),
    ).subquery()
    return list(session.scalars(
        select(Meme).where(Meme.data_source == "mock",
                           Meme.id.in_(select(real_ids.c.meme_id)))
        .order_by(Meme.id)
    ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="收敛 data_source 的错误状态")
    parser.add_argument("--apply", action="store_true", help="真的写库（默认只报告）")
    args = parser.parse_args(argv)

    session = SessionLocal()
    try:
        rows = _affected(session)
        stale = _mislabelled(session)
        if not rows and not stale:
            log.info("库里的 data_source 已经没有异常状态")
            return 0

        if rows:
            log.info("发现 %d 条 data_source 为空的梗：", len(rows))
            for meme in rows:
                log.info("  id=%-4s %-24s status=%-10s verification=%s",
                         meme.id, meme.name[:24], meme.status, meme.verification_state)
        if stale:
            log.info("发现 %d 条标着 mock、但库里已有 B 站真实数据的梗（要改标签，不是删数据）：",
                     len(stale))
            for meme in stale:
                days = session.scalar(
                    select(func.count()).select_from(MemeDailyStats)
                    .where(MemeDailyStats.meme_id == meme.id,
                           MemeDailyStats.data_source == BILIBILI)
                )
                log.info("  id=%-4s %-24s 真实日统计 %s 行", meme.id, meme.name[:24], days)

        if not args.apply:
            log.info("以上只是报告。确认无误后加 --apply 写库。")
            return 0

        changed = 0
        if rows:
            session.execute(
                update(Meme)
                .where(or_(Meme.data_source.is_(None), Meme.data_source == ""))
                .values(data_source=PENDING)
            )
            changed += len(rows)
            log.info("已把这 %d 条改成 data_source='%s'（已入池、待采集）", len(rows), PENDING)
        if stale:
            session.execute(
                update(Meme).where(Meme.id.in_([m.id for m in stale]))
                .values(data_source=BILIBILI)
            )
            changed += len(stale)
            log.info("已把这 %d 条的标签改成 '%s'——数据早就是真的了"
                     "（verification_state 不动：没有 UP 主解说证据就仍然不算入池）",
                     len(stale), BILIBILI)
        session.commit()
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
