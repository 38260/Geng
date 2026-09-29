# -*- coding: utf-8 -*-
"""把一只梗的采集数据回滚到备份里的状态（只动这一只梗的行）。

用途：排查性采集如果改到了库，用它可以只回滚被影响的那只梗，
而不像整库还原那样把其它改动（比如算法修复后的快照）一起冲掉。

    python docs/ppt/tools/rollback_meme.py --from <备份.db> --name 琵琶曲 --apply
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
DB = os.path.join(_ROOT, "backend", "data", "gengv1.db")

# 与「这只梗的采集结果」直接相关的表；快照表不在此列，
# 它们由 run_pipeline 依据恢复后的数据重算，避免出现数据与结论不一致。
DATA_TABLES = ("meme_daily_stats", "videos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True, help="备份库路径")
    ap.add_argument("--name", required=True, help="梗名")
    ap.add_argument("--apply", action="store_true", help="真的写库（默认只报告）")
    a = ap.parse_args()

    if not os.path.exists(a.src):
        print("备份不存在:", a.src)
        return 2

    live = sqlite3.connect(DB)
    live.row_factory = sqlite3.Row
    bak = sqlite3.connect(a.src)
    bak.row_factory = sqlite3.Row

    row = live.execute("select id from memes where name=?", (a.name,)).fetchone()
    if not row:
        print("现库找不到梗:", a.name)
        return 2
    mid = row["id"]

    print("梗「%s」id=%d" % (a.name, mid))
    for t in DATA_TABLES:
        cur = live.execute("select count(*) from %s where meme_id=?" % t, (mid,)).fetchone()[0]
        old = bak.execute("select count(*) from %s where meme_id=?" % t, (mid,)).fetchone()[0]
        print("  %-18s 现库 %4d 行  ->  备份 %4d 行" % (t, cur, old))

    if not a.apply:
        print("\n以上只是报告。确认后加 --apply 执行回滚。")
        return 0

    # 备份一份当前库，免得回滚本身出问题没法退
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safety = os.path.join(os.path.dirname(DB), "gengv1.rollback-safety-%s.db" % stamp)
    live.close()
    shutil.copy2(DB, safety)
    print("\n已备份当前库 ->", os.path.basename(safety))

    live = sqlite3.connect(DB)
    for t in DATA_TABLES:
        live.execute("delete from %s where meme_id=?" % t, (mid,))
        cols = [r[1] for r in bak.execute("pragma table_info(%s)" % t)]
        rows = bak.execute("select * from %s where meme_id=?" % t, (mid,)).fetchall()
        placeholders = ",".join("?" * len(cols))
        live.executemany(
            "insert into %s (%s) values (%s)" % (t, ",".join(cols), placeholders),
            [tuple(r) for r in rows])
        print("  恢复 %-18s %d 行" % (t, len(rows)))
    live.commit()

    for t in DATA_TABLES:
        cur = live.execute("select count(*) from %s where meme_id=?" % t, (mid,)).fetchone()[0]
        print("  校验 %-18s 现为 %d 行" % (t, cur))
    live.close()
    print("\n下一步必须重算，否则结论与数据不一致：")
    print("  cd backend && python -m app.scripts.run_pipeline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
