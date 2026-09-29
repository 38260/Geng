# -*- coding: utf-8 -*-
"""Normalise the legacy ``data_source=''`` state to ``pending``.

来历：新建梗时写的是空串，于是库里出现第三种"无来源"状态——
既不是 ``bilibili`` 也不是 ``mock``，既进不了真实榜单也拿不到演示标注，
界面上无从解释。模型与两个写入点已经修好，这个脚本负责把历史数据对齐。

    python -m app.scripts.fix_data_source_state            # 只报告
    python -m app.scripts.fix_data_source_state --apply    # 真的改
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import or_, select, update

from app.config.logging import get_logger
from app.models import Meme, SessionLocal

log = get_logger(__name__)

PENDING = "pending"


def _affected(session):
    return list(session.scalars(
        select(Meme).where(or_(Meme.data_source.is_(None), Meme.data_source == ""))))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 data_source 的空状态收敛成 pending")
    parser.add_argument("--apply", action="store_true", help="真的写库（默认只报告）")
    args = parser.parse_args(argv)

    session = SessionLocal()
    try:
        rows = _affected(session)
        if not rows:
            log.info("没有 data_source 为空的梗，库已经是干净的")
            return 0

        log.info("发现 %d 条 data_source 为空的梗：", len(rows))
        for meme in rows:
            log.info("  id=%-4s %-24s status=%-10s verification=%s",
                     meme.id, meme.name[:24], meme.status, meme.verification_state)

        if not args.apply:
            log.info("以上只是报告。确认无误后加 --apply 写库。")
            return 0

        session.execute(
            update(Meme)
            .where(or_(Meme.data_source.is_(None), Meme.data_source == ""))
            .values(data_source=PENDING)
        )
        session.commit()
        log.info("已把这 %d 条改成 data_source='%s'（已入池、待采集）", len(rows), PENDING)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
