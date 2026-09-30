"""删掉"纯演示梗"：``data_source=mock``、库里没有任何 B 站真实证据的那些。

为什么要有这个脚本：这些梗是早期手写的演示数据（「这也太刑了」热度 67.7、
「我是大学生」65.3……），认证记录也是自造口径。真实模式下热榜本来就不显示它们
（``_load_rows`` 要求真实来源 + 在线核验过），但它们仍然躺在库里，
带着 mock 日统计和热度快照——一共 10 份快照，占全库快照的 14%。
"数据里混着模拟数字"这件事本身就没法向用户解释，所以清掉。

默认**只报告**，一行都不删；要真删得显式带 ``--apply``，
脚本会在动手前先备份一份整库，并把"每个梗删掉多少行"逐条列出来。

    python -m app.scripts.prune_mock_memes                 # 先看要删什么
    python -m app.scripts.prune_mock_memes --apply         # 备份后真删

不动的东西（重要）：

* **有真实证据的梗**——哪怕它的 ``data_source`` 还写着 mock。这种是"标错来源"，
  该用 ``fix_data_source_state`` 改标签，而不是把真数据删了。
* **最新准入池里的梗**（认证窗口内有真实解说证据）——那说明两位 UP 真做过它，
  它现在该被采集，不该被删。
* ``pending`` 状态的梗：那是刚发现还没采到数的，不是演示数据。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from app.config import PROJECT_DIR, get_logger, settings
from app.models import (
    AIInsight,
    HotnessSnapshot,
    LifecycleSnapshot,
    Meme,
    MemeCertification,
    MemeDailyStats,
    SessionLocal,
    Video,
    VideoTranscript,
)
from app.services.meme.query import fresh_cert_ids

log = get_logger(__name__)

# 每张子表都按 meme_id 挂梗，删梗必须连这些一起删干净，
# 否则留下没有父记录的孤行，页面取列表时会被 JOIN 掉、却还在占库。
CHILD_MODELS = (
    MemeDailyStats,
    Video,
    VideoTranscript,
    MemeCertification,
    HotnessSnapshot,
    LifecycleSnapshot,
    AIInsight,
)


def _sqlite_path() -> Path | None:
    """真实库文件路径。非 SQLite 时返回 None（这脚本只给自己家里那台 SQLite 用）。"""
    url = settings.database_url
    if not url.startswith("sqlite"):
        return None
    raw = url.split("///", 1)[-1]
    path = Path(raw)
    return path if path.is_absolute() else (PROJECT_DIR / "backend" / raw)


def _has_real_evidence(session, meme_id: int) -> bool:
    """有任何一条 B 站真实证据（认证/视频/日统计）就不算纯演示梗。"""
    for model in (MemeCertification, Video, MemeDailyStats):
        found = session.scalar(
            select(model).where(
                model.meme_id == meme_id, model.data_source == "bilibili"
            ).limit(1)
        )
        if found is not None:
            return True
    return False


def _candidates(session) -> tuple[list[tuple], list[tuple]]:
    """返回 (要删的纯演示梗, 只是标错来源的梗)。"""
    in_pool = fresh_cert_ids(session)
    doomed: list[tuple] = []
    mislabelled: list[tuple] = []
    memes = list(session.scalars(select(Meme).order_by(Meme.id)))
    for meme in memes:
        if (meme.data_source or "") != "mock":
            continue
        if meme.id in in_pool:
            continue                      # 最新池里的梗不碰，哪怕来源还写着 mock
        score = session.scalar(
            select(HotnessSnapshot.score).where(HotnessSnapshot.meme_id == meme.id)
        )
        if _has_real_evidence(session, meme.id):
            mislabelled.append((meme.id, meme.name, round(score or 0, 1)))
            continue
        rows = {
            model.__tablename__: session.scalar(
                select(func.count()).select_from(model).where(model.meme_id == meme.id)
            )
            for model in CHILD_MODELS
        }
        doomed.append((meme.id, meme.name, meme.status, round(score or 0, 1), rows))
    return doomed, mislabelled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 清掉纯演示梗")
    parser.add_argument("--apply", action="store_true", help="真的删（默认只报告）")
    args = parser.parse_args(argv)

    session = SessionLocal()
    try:
        doomed, mislabelled = _candidates(session)
        if not doomed:
            print("库里没有纯演示梗，不用删。")
        else:
            print(f"纯演示梗 {len(doomed)} 个（data_source=mock、且无任何 B 站真实证据）：\n")
            total_rows = 0
            for meme_id, name, status, score, rows in doomed:
                picked = " / ".join(f"{k}={v}" for k, v in rows.items() if v)
                total_rows += sum(rows.values())
                print(f"  #{meme_id:<3} {name:<14} {status:<10} 热度 {score:<5} 删 {picked or '只有梗本身'}")
            print(f"\n合计要删 {len(doomed)} 只梗、连带 {total_rows} 行子表数据。")

        if mislabelled:
            print("\n另外这些梗标着 mock 却已有真实数据，本脚本**不动**它们：")
            for meme_id, name, score in mislabelled:
                print(f"  #{meme_id:<3} {name:<14} 热度 {score}  ← 该用 fix_data_source_state 改标签")

        if not args.apply:
            print("\n只是报告，没删任何东西。要真删加 --apply（会先自动备份整库）。")
            return 0

        if not doomed:
            return 0

        path = _sqlite_path()
        if path is None or not path.exists():
            print(f"认不出 SQLite 库文件（当前 DATABASE_URL={settings.database_url}），"
                  "不敢在别的数据库上自动备份，已中止。")
            return 2
        backup = path.with_name(f"{path.stem}.pre-prune-mock-{datetime.now():%Y%m%d-%H%M%S}{path.suffix}")
        shutil.copyfile(path, backup)
        print(f"\n已备份整库 → {backup}")

        ids = [d[0] for d in doomed]
        for model in CHILD_MODELS:
            session.query(model).filter(model.meme_id.in_(ids)).delete(synchronize_session=False)
        session.query(Meme).filter(Meme.id.in_(ids)).delete(synchronize_session=False)
        session.commit()
        print(f"已删除 {len(ids)} 只纯演示梗及其子表数据。备份在上面那行，随时可以还原。")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
