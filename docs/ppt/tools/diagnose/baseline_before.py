# -*- coding: utf-8 -*-
"""采集前基线：全库观测率 + 各梗覆盖率 + 榜首。"""
import sqlite3, json
from collections import Counter
con = sqlite3.connect("backend/data/gengv1.db"); con.row_factory = sqlite3.Row
tot = con.execute("select count(*) from meme_daily_stats").fetchone()[0]
obs = con.execute("select count(*) from meme_daily_stats where observed=1").fetchone()[0]
print("全库日统计: %d 行，其中观测到 %d 行 (%.1f%%)" % (tot, obs, 100*obs/tot))
print("涉及梗数:", con.execute("select count(distinct meme_id) from meme_daily_stats").fetchone()[0])
print()
print("真实来源梗的覆盖率分布：")
rows = list(con.execute("""
    select m.name, count(*) n, sum(case when d.observed=1 then 1 else 0 end) o
    from meme_daily_stats d join memes m on m.id=d.meme_id
    where m.data_source='bilibili' group by m.id order by 1.0*sum(case when d.observed=1 then 1 else 0 end)/count(*) """))
zero = [r["name"] for r in rows if r["o"] == 0]
low = [r["name"] for r in rows if 0 < r["o"]/r["n"] <= 0.3]
mid = [r["name"] for r in rows if 0.3 < r["o"]/r["n"] <= 0.7]
high = [r["name"] for r in rows if r["o"]/r["n"] > 0.7]
print("  0%%      : %d 个" % len(zero))
print("  1-30%%   : %d 个" % len(low))
print("  31-70%%  : %d 个" % len(mid))
print("  71-100%% : %d 个" % len(high))
print()
print("阶段:", dict(Counter(r[0] for r in con.execute("select stage_label from lifecycle_snapshots"))))
print("赶梗:", dict(Counter(r[0] for r in con.execute("select catch_label from lifecycle_snapshots"))))
print()
print("榜首前 6:")
for r in con.execute("""select m.name, h.score from hotness_snapshots h join memes m on m.id=h.meme_id
    order by h.score desc limit 6"""):
    print("   %-14s %.1f" % (r[0], r[1]))
print()
print("入选池+有快照的真实梗:", con.execute("""
    select count(*) from memes m join hotness_snapshots h on h.meme_id=m.id
    where m.data_source='bilibili' and (m.encyclopedia_confirmed=1 or m.guide_confirmed=1)
      and m.status='certified' and m.verification_state in ('verified_both','partially_verified')
""").fetchone()[0])
