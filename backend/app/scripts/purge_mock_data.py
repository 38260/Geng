"""把库里剩下的 mock 数据清干净 —— 目标是「库里每一行都是真抓来的」。

背景：真实采集上线之后，库里仍留着一批早期手写的演示**证据行**
（``meme_certifications.data_source='mock'``）。它们进不了热榜——``_load_rows``
要求 ``verification_state`` 是 verified_both / partially_verified，而演示证据自记自认的
``confirmed`` 一律算未核验。**但 ``cert_label()`` 与 ``meme.certified`` 只看 ``confirmed``、
不看 ``data_source``**，所以只要绕过那道闸门（梗管理页就是），就会看到一条
由假证据撑着的「双 UP 认证」。库里混着模拟数字这件事本身没法向用户解释，所以清掉。

默认**只报告**，一行都不删；要真删得显式带 ``--apply``，动手前先备份整库：

    python -m app.scripts.purge_mock_data            # 先看要删什么、会影响谁
    python -m app.scripts.purge_mock_data --apply    # 备份 → 真删 → 重算认证

边界（刻意划清，避免误伤真数据）：

* 只删 ``data_source='mock'`` 的**子表行**（认证 / 日统计 / 视频）。
  **不删任何 ``memes`` 行**：删梗要连子表一起级联，那是
  :mod:`app.scripts.prune_mock_memes` 的活，本脚本碰上就直接报出来让人去跑它。
* 删完只重算**认证与准入状态**（``recompute_certification``，由剩下的真实行重新推出）。
  只有假证据的梗会从 ``certified`` 退回 ``candidate``；
  它的真实视频与逐日序列**一条不删**——那是真数据，删了才是造孽。
* 不改任何 ``data_source`` 标签：标错的用 :mod:`app.scripts.fix_data_source_state`。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select, text

from app.config import PROJECT_DIR, get_logger, settings
from app.models import (
    Meme,
    MemeCertification,
    MemeDailyStats,
    SessionLocal,
    Video,
)
from app.services.meme.certification import (
    cert_label,
    recompute_certification,
)

log = get_logger(__name__)

# 带 data_source 的子表：目前全库只有 meme_certifications 命中
MOCK_MODELS = (MemeCertification, MemeDailyStats, Video)


def _sqlite_path() -> Path | None:
    """当前库文件路径。非 SQLite 返回 None（本脚本只给自家这台 SQLite 用）。"""
    url = settings.database_url
    if not url.startswith("sqlite"):
        return None
    raw = url.split("///", 1)[-1]
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_DIR / "backend" / raw
    return path


def _backup(session, path: Path, backup: Path) -> None:
    """给整库做一份**一致性**快照。

    不能用 ``shutil.copyfile`` 只拷主库文件：库跑在 WAL 模式下时，最近提交的数据
    还在 ``.db-wal`` 里，只拷 ``.db`` 会得到一份**偏旧甚至撕裂**的快照——
    备份的意义恰恰是在"准备做破坏性操作"的时候，这种时候绝不能拷出半份数据。
    ``VACUUM INTO`` 由 SQLite 自己读事务快照写新文件，一条语句拿到自洽副本。
    """
    backup.unlink(missing_ok=True)
    try:
        session.execute(text("VACUUM INTO :target"), {"target": str(backup)})
    except Exception as exc:  # noqa: BLE001 - 老版本 SQLite 没有 VACUUM INTO，退回整组拷贝
        log.warning("VACUUM INTO 失败（%s），退回拷贝 db + wal + shm", exc)
        for suffix in ("", "-wal", "-shm"):
            sibling = path.with_name(path.name + suffix)
            if sibling.exists():
                shutil.copyfile(sibling, backup.with_name(backup.name + suffix))
        return
    if not backup.exists() or backup.stat().st_size == 0:
        raise RuntimeError("备份文件没写成功，已中止，未做任何删除")


def _mock_counts(session) -> dict[str, int]:
    return {
        model.__tablename__: session.scalar(
            select(func.count()).select_from(model).where(model.data_source == "mock")
        )
        for model in MOCK_MODELS
    }


def _affected_ids(session) -> list[int]:
    ids: set[int] = set()
    for model in MOCK_MODELS:
        ids.update(
            row[0]
            for row in session.execute(select(model.meme_id).where(model.data_source == "mock"))
        )
    ids.update(
        row[0] for row in session.execute(select(Meme.id).where(Meme.data_source == "mock"))
    )
    return sorted(ids)


def _real_row_count(session, meme_id: int) -> dict[str, int]:
    return {
        model.__tablename__: session.scalar(
            select(func.count())
            .select_from(model)
            .where(model.meme_id == meme_id, model.data_source == "bilibili")
        )
        for model in MOCK_MODELS
    }


def _visible_ids(session) -> set[int]:
    """对外可见（热榜／梗库）的梗 id —— 复刻 ``_load_rows`` 的那几道谓词。

    清 mock 前后各算一次，用来证明"这次清理不会让任何梗从用户眼前消失"。
    """
    stmt = select(Meme.id).where(
        (Meme.encyclopedia_confirmed.is_(True)) | (Meme.guide_confirmed.is_(True)),
        Meme.status == "certified",
    )
    if settings.data_source == "bilibili" and settings.leaderboard_require_verified:
        stmt = stmt.where(
            Meme.data_source == "bilibili",
            Meme.verification_state.in_(("verified_both", "partially_verified")),
        )
    return set(session.scalars(stmt))


def _delete_mock_rows(session) -> int:
    removed = 0
    for model in MOCK_MODELS:
        removed += session.query(model).filter(model.data_source == "mock").delete(
            synchronize_session=False
        )
    return removed


def purge(session, ids: list[int]) -> int:
    """删掉 mock 子表行，并按**剩下那些真实行**重推认证/准入状态。

    抽成独立函数是为了能被单测直接调用（`main()` 还要管备份与报告，
    在内存库上跑不起来）。返回删除的行数；**不 commit**，由调用方决定。
    """
    removed = _delete_mock_rows(session)
    session.flush()
    # 批量 DELETE 走的是 SQL，不会同步已加载的关系对象。
    # expire_all() 让 `meme.certifications` 下次访问时**从库里重新读**——
    # 既避开"关系级联与批量删除重复命中同一行"的告警，
    # 也让下面的重算只基于真正剩下的行，而不是会话里的旧快照。
    session.expire_all()
    for meme_id in ids:
        meme = session.get(Meme, meme_id)
        if meme is not None:
            recompute_certification(meme)
    session.flush()
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 清掉全库 mock 数据")
    parser.add_argument("--apply", action="store_true", help="真的删（默认只报告）")
    args = parser.parse_args(argv)

    session = SessionLocal()
    try:
        counts = _mock_counts(session)
        total = sum(counts.values())
        if total == 0:
            print("库里已经没有任何 mock 行，不用清。")
            return 0

        ids = _affected_ids(session)
        mock_memes = list(session.scalars(select(Meme).where(Meme.data_source == "mock")))
        visible_before = _visible_ids(session)

        print("要删的 mock 行：")
        for table, count in counts.items():
            if count:
                print(f"  {table:<24} {count} 行")
        print(f"  合计 {total} 行，涉及 {len(ids)} 只梗\n")

        print("逐只影响面（删掉假证据后，认证状态由**剩下那些真实行**重推）：")
        for meme_id in ids:
            meme = session.get(Meme, meme_id)
            if meme is None:
                continue
            mock_rows = {
                model.__tablename__: session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.meme_id == meme_id, model.data_source == "mock")
                )
                for model in MOCK_MODELS
            }
            real_rows = _real_row_count(session, meme_id)
            picked = " / ".join(f"{k}={v}" for k, v in mock_rows.items() if v)
            left = " / ".join(f"{k}={v}" for k, v in real_rows.items() if v) or "无"
            print(
                f"  #{meme_id:<3} {meme.name[:14]:<16} 删[{picked}] "
                f"剩真实[{left}]  认证={cert_label(meme)} → 按真实行重推"
            )

        if mock_memes:
            print(
                f"\n⚠ 还有 {len(mock_memes)} 只梗本身标着 mock（{', '.join(m.name for m in mock_memes[:5])}）。"
                "\n  删梗要连带子表级联，本脚本不动它们——请跑 "
                "`python -m app.scripts.prune_mock_memes --apply`。"
            )

        if not args.apply:
            print(
                f"\n只是报告，一行都没删。\n"
                f"  当前对外可见（热榜/梗库）的梗：{len(visible_before)} 只；\n"
                f"  预计清理后：{_simulate_after(session, ids)} 只"
                f"（若数字相同，说明这些梗本来就被在线核验闸门挡在外面）。\n"
                "要真删加 --apply（会先自动备份整库）。"
            )
            return 0

        path = _sqlite_path()
        if path is None or not path.exists():
            print(f"认不出 SQLite 库文件（DATABASE_URL={settings.database_url}），"
                  "不敢在别的数据库上自动备份，已中止。")
            return 2
        backup_dir = PROJECT_DIR / "backend" / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{path.stem}.pre-purge-mock-{datetime.now():%Y%m%d-%H%M%S}{path.suffix}"
        _backup(session, path, backup)
        print(f"\n已备份整库 → {backup}")

        removed = purge(session, ids)
        session.commit()

        visible_after = _visible_ids(session)
        left = sum(_mock_counts(session).values())
        print(f"已删除 {removed} 行 mock 数据，重算了 {len(ids)} 只梗的认证/准入状态。")
        print(f"复核：库里剩余 mock 行 = {left}（应为 0）")
        print(f"可见梗 {len(visible_before)} → {len(visible_after)}"
              + ("（无变化，符合预期）" if len(visible_before) == len(visible_after) else "（⚠ 有变化，请核对）"))

        if path.suffix == ".db":
            # 把 WAL 并回主库，这样只有一个自洽的文件、便于复制或分发
            session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            session.commit()
        return 0
    finally:
        session.close()


def _simulate_after(session, ids: list[int]) -> int:
    """预演：把假证据行删掉、重推认证之后，对外可见的梗有多少只。

    真的在事务里删一遍再 ``rollback``——比手工复制一套判定逻辑可靠：
    判定规则只有 `recompute_certification` 一处定义，不会两边漂移。
    """
    before = _visible_ids(session)
    snapshot = {
        meme.id: (meme.certified, meme.status, meme.encyclopedia_confirmed, meme.guide_confirmed)
        for meme in session.scalars(select(Meme).where(Meme.id.in_(ids)))
    }
    try:
        purge(session, ids)
        return len(_visible_ids(session))
    finally:
        session.rollback()
        for meme_id, (certified, status, enc, gui) in snapshot.items():
            meme = session.get(Meme, meme_id)
            if meme is not None:
                meme.certified, meme.status = certified, status
                meme.encyclopedia_confirmed, meme.guide_confirmed = enc, gui
        # 回滚后重新读一次，确保调用方拿到的还是"清理前"的状态
        assert _visible_ids(session) == before


if __name__ == "__main__":
    sys.exit(main())
