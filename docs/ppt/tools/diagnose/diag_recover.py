# -*- coding: utf-8 -*-
"""测惩罚解除时间：完全停手后，每隔一段时间试 3 次，看何时恢复。"""
import sys, os, time
from datetime import datetime, timedelta
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "backend"))
os.chdir(os.path.join(_ROOT, "backend"))
from app.config import settings
from app.collectors.bilibili import BiliClient

URL = "https://api.bilibili.com/x/web-interface/wbi/search/type"
client = BiliClient(cookie=settings.bili_cookie, timeout=settings.bili_timeout)
client.bootstrap_fingerprint()
today = datetime.now().date()


def try3(term="哈基米", off=5):
    hits = 0
    for _ in range(3):
        day = today - timedelta(days=off)
        b = datetime.combine(day, datetime.min.time()); e = b + timedelta(days=1)
        try:
            d = client.signed_get(URL, {"search_type": "video", "keyword": term, "page": 1,
                "ps": 20, "order": "click", "pubtime_begin_s": int(b.timestamp()),
                "pubtime_end_s": int(e.timestamp())})
            hits += 1 if (d.get("result") or []) else 0
        except Exception:
            pass
        time.sleep(1.5)
    return hits


CHECK = [0, 120, 300, 600, 900]      # 秒
start = time.time()
for target in CHECK:
    wait = target - (time.time() - start)
    if wait > 0:
        print("   ... 静默等待 %.0f 秒（不发任何请求）" % wait)
        time.sleep(wait)
    h = try3()
    print("  t=%4ds 后试 3 次：命中 %d/3" % (time.time() - start, h))
    if h >= 3:
        print("\n=> 已恢复，累计静默约 %.0f 秒" % (time.time() - start))
        break
else:
    print("\n=> 900 秒内未完全恢复")
