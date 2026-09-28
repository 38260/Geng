"""从历史快照回填"更好的一次观测"，修掉采集抖动造成的序列变薄。

场景（2026-09-27 实测）：并集入池后重采 51 个梗，B 站对同一个词、同一天两次返回的
头部 20 条差别很大，「琵琶曲」从 4 天 / 3,976 万播放被刷成 1 天 / 18 条，热度 44.2 → 0.0。
那是接口抖动，不是梗凉了。当前管线已经改成"同一天取样本更多的那一次"
（见 ``pipeline.split_daily_stats``），本脚本负责把**这次已经变薄的**数据从快照里救回来。

规则跟管线一致，只做一件事：同一个梗的同一天，比较 (video_count, view)，
快照里更好就用快照的那行覆盖线上那一行，其余一律不动。不相加、不新增梗、
不改梗名与认证数据。读快照用只读连接，绝无误写线上库之外的可能。

    cd backend
    python -m app.scripts.backfill_days data/backups/gengv1-snapshot.db           # dry-run
    python -m app.scripts.backfill_days data/backups/gengv1-snapshot.db --apply
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import Meme, MemeDailyStats, SessionLocal
from app.services.pipeline import _quality

log = get_logger("backfill")

FIELDS = ("video_count", "creator_count", "view", "like", "coin", "favorite", "reply", "danmaku")


def _name_key(name: str) -> str:
    return (name or "").strip().lower()


def _quality_of(video_count: int, view: int, observed: bool = True) -> tuple[int, int, int]:
    return _quality(SimpleNamespace(video_count=video_count, view=view, observed=observed))


def snapshot_stats(path: Path, source: str) -> dict[str, dict[date, dict]]:
    """快照里的日统计：{梗名(归一化): {日期: 那一天的各字段}}。"""
    if not path.exists():
        raise SystemExit(f"快照文件不存在：{path}")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "select m.name as name, s.stat_date as stat_date, s.video_count, s.creator_count,"
            " s.view, s.like, s.coin, s.favorite, s.reply, s.danmaku"
            " from meme_daily_stats s join memes m on m.id = s.meme_id"
            " where s.data_source = ?",
            (source,),
        ).fetchall()
    finally:
        conn.close()

    out: dict[str, dict[date, dict]] = {}
    for row in rows:
        stamp = str(row["stat_date"])[:10]
        try:
            day = date.fromisoformat(stamp)
        except ValueError:
            continue
        out.setdefault(_name_key(row["name"]), {})[day] = {field: row[field] for field in FIELDS}
    return out


def build_plan(session: Session, snapshot: dict[str, dict[date, dict]], source: str) -> list[dict]:
    """列出"快照比线上更好"的天。返回每项 = {meme_id, name, day, before, after, action}。"""
    plan: list[dict] = []
    for meme in session.scalars(select(Meme).order_by(Meme.id)):
        days = snapshot.get(_name_key(meme.name))
        if not days:
            continue
        live = {
            row.stat_date: row
            for row in session.scalars(
                select(MemeDailyStats).where(
                    MemeDailyStats.meme_id == meme.id, MemeDailyStats.data_source == source
                )
            )
        }
        for day, values in days.items():
            quality = _quality_of(values["video_count"], values["view"])
            row = live.get(day)
            if row is not None:
                # 线上那行是接口空壳（observed=False）时，快照里有内容就该盖回去
                if _quality_of(row.video_count, row.view, row.observed is not False) >= quality:
                    continue
                action, before = "update", (row.video_count, row.view)
            else:
                if (values["video_count"], values["view"]) == (0, 0):
                    continue        # 空的一天不值得补
                action, before = "insert", (0, 0)
            plan.append({
                "meme_id": meme.id, "name": meme.name, "day": day, "action": action,
                "before": before, "after": (values["video_count"], values["view"]),
                "values": values,
            })
    return plan


def apply_plan(session: Session, plan: list[dict], source: str) -> int:
    """把计划写回线上：同日覆盖、缺失补行。梗与认证数据一律不碰。"""
    by_meme: dict[int, list[dict]] = {}
    for item in plan:
        by_meme.setdefault(item["meme_id"], []).append(item)

    written = 0
    for meme_id, items in by_meme.items():
        live = {
            row.stat_date: row
            for row in session.scalars(
                select(MemeDailyStats).where(
                    MemeDailyStats.meme_id == meme_id, MemeDailyStats.data_source == source
                )
            )
        }
        for item in items:
            if item["action"] == "update":
                row = live[item["day"]]
                for field, value in item["values"].items():
                    setattr(row, field, value)
            else:
                session.add(
                    MemeDailyStats(
                        meme_id=meme_id, stat_date=item["day"], data_source=source, **item["values"]
                    )
                )
            written += 1
    session.commit()
    return written


def summarize(plan: list[dict]) -> list[str]:
    per_meme: dict[str, dict[str, int]] = {}
    for item in plan:
        bucket = per_meme.setdefault(item["name"], {"days": 0, "views": 0})
        bucket["days"] += 1
        bucket["views"] += item["after"][1] - item["before"][1]
    return [
        f"  {name:16s} 补 {value['days']} 天，播放量回到 {value['views']:+,}"
        for name, value in sorted(per_meme.items(), key=lambda kv: -kv[1]["days"])
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 从快照回填更好的日观测")
    parser.add_argument("snapshot", help="快照 db 文件路径（只读打开）")
    parser.add_argument("--source", default="bilibili", help="只比较这个数据源的日统计（默认 bilibili）")
    parser.add_argument("--apply", action="store_true", help="真的写回线上库（默认只报告）")
    args = parser.parse_args(argv)

    snapshot = snapshot_stats(Path(args.snapshot), args.source)
    session = SessionLocal()
    try:
        from app.models.base import DATABASE_URL

        print(f"快照：{args.snapshot}（可比对 {len(snapshot)} 个梗名）")
        print(f"写入目标：{DATABASE_URL}")
        if not DATABASE_URL.startswith("sqlite") or "gengv1" not in DATABASE_URL:
            raise SystemExit("为安全起见，本脚本默认只允许写回本地 gengv1.db；确认后再手动跑")
        plan = build_plan(session, snapshot, args.source)
        if not plan:
            print("线上每一条同日观测都不比快照差，无需回填。")
            return 0
        print(f"快照更好的天：{len(plan)} 天，涉及 {len({item['name'] for item in plan})} 个梗")
        for line in summarize(plan):
            print(line)
        if not args.apply:
            print("\n（dry-run）确认无误后加 --apply 写回，然后跑一次重算。")
            return 0
        written = apply_plan(session, plan, args.source)
        print(f"已回填 {written} 天。")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
