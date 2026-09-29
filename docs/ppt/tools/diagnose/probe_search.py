# -*- coding: utf-8 -*-
"""B 站搜索「琵琶曲」实测：综合排序 / 播放量 / 当日区间，与采集器同一套接口。"""
import sys, os, time, json
from collections import Counter
from datetime import datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "backend"))
os.chdir(os.path.join(_ROOT, "backend"))
from app.config import settings
from app.collectors.bilibili import BiliClient, parse_search_row

TERM = "琵琶曲"
client = BiliClient(cookie=settings.bili_cookie, timeout=settings.bili_timeout)
print("cookie:", "已配置" if settings.bili_cookie else "空（匿名）")
ok, msg = client.probe()
print("接口探测:", ok, msg)
print()
def show(tag, raw_rows):
    rows = [parse_search_row(r) for r in raw_rows]
    print("【%s】返回 %d 条" % (tag, len(rows)))
    total_view = sum(r["view"] for r in rows)
    for i, r in enumerate(rows, 1):
        print("   %2d. %-44s 播放 %-11s UP %-14s %s  %s" % (
            i, r["title"][:44], format(r["view"], ","), (r["author"] or "")[:14],
            r["publish_time"].strftime("%Y-%m-%d"), r["bvid"]))
    print("   → 这 %d 条合计播放 %s；单条最高 %s" % (
        len(rows), format(total_view, ","),
        format(max((r["view"] for r in rows), default=0), ",")))
    return rows


# ---- 1) 综合排序（不传 order）= 用户自己在站内搜看到的顺序 ----
try:
    rows = show("综合排序 page 1（站内默认）",
                client.search_videos(TERM, pages=1, order=""))
except Exception as e:
    print("综合排序失败:", type(e).__name__, e)
    rows = []
print()
time.sleep(3)

# ---- 2) 按播放量（order=click），采集器的日区间查询用的就是它 ----
try:
    rows2 = show("播放量排序 page 1", client.search_videos(TERM, pages=1, order="click"))
except Exception as e:
    print("播放量排序失败:", type(e).__name__, e)
    rows2 = []
print()

# ---- 3) 当天的区间查询：采集器逐日就是这么打的 ----
print("=" * 78)
print("逐日区间查询（采集器的真实口径）：day 偏移 1~8 天，order=click，ps=20")
print("=" * 78)
today = datetime.now().date()
for offset in range(1, 9):
    day = today - timedelta(days=offset)
    begin = datetime.combine(day, datetime.min.time())
    end = begin + timedelta(days=1)
    try:
        raw, total = client.search_range(TERM, begin=begin, end=end, order="click")
        parsed = [parse_search_row(r) for r in raw]
        vsum = sum(p["view"] for p in parsed)
        print("  %s  返回 %2d 条  total=%-8s  头部合计播放 %s" % (
            day, len(parsed), format(total, ",") if isinstance(total, int) else total,
            format(vsum, ",")))
    except Exception as e:
        print("  %s  失败 %s: %s" % (day, type(e).__name__, e))
    time.sleep(3)


