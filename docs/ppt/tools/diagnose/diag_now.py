# -*- coding: utf-8 -*-
"""限流到底持续多久？冷启动 vs 长期被限的对比，以及现在处于什么状态。"""
import sys, os, time
from datetime import datetime, timedelta
_HERE = os.path.dirname(os.path.abspath(__file__))
# diagnose/ -> tools/ -> ppt/ -> docs/ -> 仓库根
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "backend"))
os.chdir(os.path.join(_ROOT, "backend"))
from app.config import settings
from app.collectors.bilibili import BiliClient

URL = "https://api.bilibili.com/x/web-interface/wbi/search/type"
client = BiliClient(cookie=settings.bili_cookie, timeout=settings.bili_timeout)
client.bootstrap_fingerprint()
today = datetime.now().date()


def probe(tag, term="哈基米", off=5):
    day = today - timedelta(days=off)
    b = datetime.combine(day, datetime.min.time()); e = b + timedelta(days=1)
    d = client.signed_get(URL, {"search_type": "video", "keyword": term, "page": 1,
        "ps": 20, "order": "click", "pubtime_begin_s": int(b.timestamp()),
        "pubtime_end_s": int(e.timestamp())})
    v = "v_voucher" in d
    n = len(d.get("result") or [])
    print("  %-22s 行数=%d  voucher=%s" % (tag, n, v))
    return not v and n > 0


print("当前会话状态（连打 3 次，间隔 3 秒）：")
for i in range(3):
    probe("第 %d 次" % (i + 1))
    time.sleep(3)
