# -*- coding: utf-8 -*-
"""看原始返回体：空返回里到底有没有可诊断的信息。"""
import sys, os, time, json
from datetime import datetime, timedelta
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "backend"))
os.chdir(os.path.join(_ROOT, "backend"))
from app.config import settings
from app.collectors.bilibili import BiliClient

client = BiliClient(cookie=settings.bili_cookie, timeout=settings.bili_timeout)
client.bootstrap_fingerprint()
today = datetime.now().date()

KEYS_TO_SHOW = ("code", "message", "numResults", "numPages", "pages", "suggest_keyword",
                "rqt_type", "seid", "egg_hit", "is_hit", "num_result")


def probe(tag, keyword, day):
    begin = datetime.combine(day, datetime.min.time())
    end = begin + timedelta(days=1)
    try:
        data = client.signed_get(
            "https://api.bilibili.com/x/web-interface/wbi/search/type",
            {"search_type": "video", "keyword": keyword, "page": 1, "ps": 20,
             "order": "click", "pubtime_begin_s": int(begin.timestamp()),
             "pubtime_end_s": int(end.timestamp())})
    except Exception as e:
        print("%-34s 异常 %s: %s" % (tag, type(e).__name__, e))
        return
    rows = data.get("result") or []
    shown = {k: data.get(k) for k in KEYS_TO_SHOW if k in data}
    print("%-34s 行数=%-3d  %s" % (tag, len(rows), json.dumps(shown, ensure_ascii=False)))
    if not rows:
        extra = {k: v for k, v in data.items()
                 if k not in ("result",) and not isinstance(v, (list, dict))}
        print("%-34s   其它标量字段: %s" % ("", json.dumps(extra, ensure_ascii=False)))


print("=== A) 琵琶曲：09-24（库里说没观测到，但我今天搜到过 20 条）===")
d = today - timedelta(days=5)
for i in range(3):
    probe("  第 %d 次" % (i + 1), "琵琶曲", d)
    time.sleep(3)
print()
print("=== B) 换一个极常见词做对照：动画 ===")
for i in range(2):
    probe("  第 %d 次" % (i + 1), "动画", d)
    time.sleep(3)
print()
print("=== C) 换一个大概率真没内容的词：qwertyzzz ===")
for i in range(2):
    probe("  第 %d 次" % (i + 1), "qwertyzzz", d)
    time.sleep(3)
