"""梗库去重：把同一个梗的多条记录找出来，默认只报告，不删。

来由：早期梗库是我手写的名单，「胆子真的肥嘟嘟的」（搜出来的名字打错一个字）和
「胆子真是肥嘟嘟的」（梗百科的真实投稿名）会同时存在，「牛来也」/「牛来」也一样。
并集准入上线后新条目都按抽取出来的梗名建，历史遗留的重复行得清掉，否则
同一个梗在榜单上占两个坑、各带一份数据，两边都不对。

安全边界（这个项目被"跑错脚本清空真实数据"伤过一次）：

* 默认 dry-run，必须 ``--apply`` 才写库；
* ``--apply`` 必须同时给出 ``--drop``，且只删点名的那些 id；
* 只允许删**没有任何真实 UP 证据**的条目——有证据的说明它就是正主；
* 被删条目的视频/统计/快照/洞察由外键 CASCADE 一起带走（`base.py` 里开了
  ``PRAGMA foreign_keys=ON``），不做"挪给正主"的合并：两个梗名各自采来的
  序列是同一批内容的两次不同抽样，硬拼成一条序列等于自己造数据。

    cd backend
    python -m app.scripts.dedupe_memes                 # 看有哪些重复
    python -m app.scripts.dedupe_memes --apply --drop 40,41
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_logger, settings
from app.models import Meme, MemeDailyStats, Video
from app.services.meme.certification import admitted, cert_label

log = get_logger("dedupe")

MIN_NAME_LEN = 2         # 报告配对时允许短名（"牛来" / "牛来也"），只删点名的所以不怕误合


def _norm(name: str) -> str:
    return (name or "").strip().lower()


def duplicate_pairs(memes: list[Meme]) -> list[tuple[Meme, Meme]]:
    """名字互相包含（且不是同名）的两条 = 疑似同一个梗。

    规则跟发现层一样保守：只看连续包含，不靠"长得像"。像 "宗主第一招" 和
    "宗主第二招" 这种确实是两个梗，宁可让人来看。
    """
    out: list[tuple[Meme, Meme]] = []
    for i, a in enumerate(memes):
        for b in memes[i + 1:]:
            na, nb = _norm(a.name), _norm(b.name)
            if not na or not nb or na == nb:
                continue
            if len(na) >= MIN_NAME_LEN and len(nb) >= MIN_NAME_LEN and (na in nb or nb in na):
                out.append((a, b))
    return out


def keeper_of(pair: tuple[Meme, Meme]) -> tuple[Meme, Meme]:
    """正主 = 有真实 UP 证据的那条；都没有就取名字短的（更接近抽取口径）。"""
    a, b = pair

    def rank(meme: Meme) -> tuple[int, int]:
        return (1 if meme.verification_state != "unverified" else 0, -len(meme.name))

    return (a, b) if rank(a) >= rank(b) else (b, a)


def stats_of(session: Session, meme: Meme) -> dict[str, object]:
    days = session.scalar(
        select(func.count(MemeDailyStats.id)).where(MemeDailyStats.meme_id == meme.id)
    )
    views = session.scalar(
        select(func.sum(MemeDailyStats.view)).where(MemeDailyStats.meme_id == meme.id)
    )
    videos = session.scalar(select(func.count(Video.id)).where(Video.meme_id == meme.id))
    return {
        "days": int(days or 0),
        "views": int(views or 0),
        "videos": int(videos or 0),
        "admitted": admitted(meme),
        "cert_label": cert_label(meme),
        "verification_state": meme.verification_state,
        "data_source": meme.data_source or "pending",
    }


def backup_database(label: str = "pre-dedupe") -> Path | None:
    """删数据之前先拿一份一致快照（WAL 模式下直接 cp 主文件是不够的）。"""
    url = settings.database_url
    if not url.startswith("sqlite"):
        log.warning("非 SQLite 数据源（%s），跳过本地快照，请先自行备份数据库", url.split("://")[0])
        return None
    target = BACKEND_DIR / "data" / "backups"
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target / f"{label}-{stamp}.db"
    source = sqlite3.connect(url.replace("sqlite:///", ""))
    dest = sqlite3.connect(path)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return path


def drop_memes(session: Session, ids: list[int]) -> list[str]:
    """删掉点名的重复条目。有真实 UP 证据的一律拒绝。"""
    removed: list[str] = []
    for meme_id in ids:
        meme = session.get(Meme, meme_id)
        if meme is None:
            log.warning("id %s 不存在，跳过", meme_id)
            continue
        if meme.verification_state != "unverified":
            raise SystemExit(
                f"拒绝删除「{meme.name}」(id {meme.id})：它是在线核验过的证据载体（{meme.verification_state}）"
            )
        info = stats_of(session, meme)
        session.delete(meme)
        removed.append(meme.name)
        log.info(
            "删除重复条目「%s」(id %s)：%s 天序列 / %s 条视频 / %s 播放",
            meme.name, meme.id, info["days"], info["videos"], f"{info['views']:,}",
        )
    session.commit()
    return removed


def report(session: Session) -> int:
    memes = list(session.scalars(select(Meme).order_by(Meme.id)))
    pairs = duplicate_pairs(memes)
    if not pairs:
        print("没有互相包含的梗名对，梗库不存在这类重复。")
        return 0
    print(f"疑似同一个梗：{len(pairs)} 组（规则=梗名互相包含；只报告，删除要点名 --drop）\n")
    for pair in pairs:
        keep, gone = keeper_of(pair)
        for tag, meme in (("保留", keep), ("重复", gone)):
            info = stats_of(session, meme)
            print(
                f"  [{tag}] id {meme.id:<4} {meme.name:<14} "
                f"{info['cert_label']:<10} 状态={info['admitted'] and '已入池' or '未入池'} "
                f"{info['days']}天/{info['videos']}视频/{info['views']:,}播放 源={info['data_source']}"
            )
        print()
    print("确认无误后：python -m app.scripts.dedupe_memes --apply --drop <要删的id,逗号分隔>")
    return len(pairs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 梗库去重（默认只报告）")
    parser.add_argument("--apply", action="store_true", help="真的删除（必须配合 --drop）")
    parser.add_argument("--drop", default="", help="要删除的 meme id，逗号分隔")
    args = parser.parse_args(argv)

    from app.models import SessionLocal

    session = SessionLocal()
    try:
        report(session)
        if not args.apply:
            return 0
        ids = [int(x) for x in args.drop.split(",") if x.strip()]
        if not ids:
            raise SystemExit("--apply 必须配合 --drop 点名要删的 id")
        snap = backup_database()
        print(f"\n已备份到 {snap}" if snap else "\n（非 SQLite 数据源，未做本地快照）")
        removed = drop_memes(session, ids)
        print(f"删除 {len(removed)} 条：{'、'.join(removed)}")
        print("接着跑一次重算，让榜单不再引用已删除的条目：python -m app.scripts.rebuild_from_bilibili --recompute-only")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
