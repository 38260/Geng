# -*- coding: utf-8 -*-
"""端到端：用真实采集流程跑 5 个梗 × 30 天，统计实际拿到多少天。
这才是唯一有意义的口径——重试策略在真实采集下的效果。"""
import sys, os, time, json, sqlite3
from datetime import date
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "backend"))
os.chdir(os.path.join(_ROOT, "backend"))
from app.config import settings
from app.models import Meme
from app.collectors.bilibili import BiliClient
from app.collectors.bilibili_collector import BilibiliCollector

con = sqlite3.connect("data/gengv1.db"); con.row_factory = sqlite3.Row
rows = list(con.execute("""select id,name,aliases,keywords from memes
    where data_source='bilibili' order by id limit 5"""))
con.close()

client = BiliClient(cookie=settings.bili_cookie, timeout=settings.bili_timeout)
client.bootstrap_fingerprint()
col = BilibiliCollector(client=client)

print("重试设置: collect_day_retries=%s, gap=%s"
      % (settings.collect_day_retries, settings.collect_retry_gap))
print()
tot_days = tot_obs = 0
t0 = time.time()
for r in rows:
    meme = Meme(id=r["id"], name=r["name"], slug="probe-%d" % r["id"],
                aliases=json.loads(r["aliases"] or "[]"),
                keywords=json.loads(r["keywords"] or "[]"))
    stats, seen, filtered = col.collect_daily(meme, window_days=30)
    obs = sum(1 for s in stats if s.observed)
    tot_days += len(stats); tot_obs += obs
    print("  %-14s 观测 %2d/%2d 天  (%.0f%%)  样本 %d 条" % (
        r["name"], obs, len(stats), 100*obs/len(stats), len(seen)))
print()
print("合计：%d/%d 天 = %.0f%% （耗时 %.0f 秒）" % (
    tot_obs, tot_days, 100*tot_obs/tot_days, time.time()-t0))
