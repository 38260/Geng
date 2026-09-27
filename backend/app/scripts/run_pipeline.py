"""重算热度与生命周期，并打印榜单（用于校准演示数据）。

    python -m app.scripts.run_pipeline
    python -m app.scripts.run_pipeline --report
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.analytics import nickname
from app.config import get_logger, settings
from app.models import HotnessSnapshot, LifecycleSnapshot, Meme, SessionLocal
from app.services.pipeline import recompute_all

log = get_logger(__name__)


def report(top: int | None = None) -> int:
    session = SessionLocal()
    try:
        rows = list(
            session.execute(
                select(Meme, HotnessSnapshot, LifecycleSnapshot)
                .join(HotnessSnapshot, HotnessSnapshot.meme_id == Meme.id)
                .join(LifecycleSnapshot, LifecycleSnapshot.meme_id == Meme.id)
                .where(Meme.certified.is_(True))
                .order_by(HotnessSnapshot.score.desc())
            )
        )
        print(f"{'排名':<4}{'梗名称':<14}{'热度':>6}  {'生命周期':<8}{'卡片标签':<8}{'赶梗':<8}{'7天增长':>9}")
        print("-" * 70)
        shown = rows[: top] if top else rows
        for index, (meme, hotness, lifecycle) in enumerate(shown, start=1):
            growth = (hotness.metrics or {}).get("growth")
            growth_text = "—" if growth is None else f"{growth * 100:+.0f}%"
            print(
                f"{index:<4}{meme.name:<14}{hotness.score:>6.1f}  "
                f"{lifecycle.stage_label:<8}{nickname(lifecycle.stage, growth):<8}"
                f"{lifecycle.catch_label:<8}{growth_text:>9}"
            )
        print("-" * 70)
        print(f"共 {len(rows)} 个已认证梗参与榜单")
        return 0
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 指标计算")
    parser.add_argument("--days", type=int, default=settings.analysis_window_days)
    parser.add_argument("--report", action="store_true", help="计算完打印热度榜单")
    parser.add_argument("--top", type=int, default=None)
    args = parser.parse_args(argv)

    result = recompute_all(window_days=args.days)
    print(
        f"指标计算完成：已计算 {result['computed']} 个，"
        f"跳过 {result['skipped']} 个（未认证或暂无数据），共 {result['total']} 个梗"
    )
    if args.report:
        report(args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
