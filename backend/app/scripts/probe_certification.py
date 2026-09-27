"""探测：能不能拿到两位梗解释 UP 主的真实投稿（双 UP 认证证据）。

只读，不写库。逐个试可用路径，把结果原样打出来。
"""

from __future__ import annotations

import json
import time

import httpx

from app.collectors.bilibili import BiliClient, sign_params, SPACE_ARCHIVE_URL

MIDS = {"梗百科": 1544008396, "梗指南": 94510621}

client = BiliClient(cookie="")
headers = client.headers()

print("=== 1) 官方 space/wbi/arc/search（当前采集器用的） ===")
try:
    data = client.signed_get(SPACE_ARCHIVE_URL, {"mid": MIDS["梗百科"], "ps": 5, "pn": 1, "order": "pubdate"})
    vlist = (data.get("list") or {}).get("vlist") or []
    print("  OK", len(vlist), [v.get("title", "")[:18] for v in vlist[:2]])
except Exception as exc:  # noqa: BLE001
    print("  失败:", str(exc)[:120])

print("\n=== 2) 搜索结果里按 mid 反查 UP 主投稿 ===")
for name, mid in MIDS.items():
    try:
        rows = client.search_videos(name, pages=2)
        hit = [r for r in rows if int(r.get("mid") or 0) == mid]
        print(f"  搜索「{name}」共 {len(rows)} 条，命中该 UP 的 {len(hit)} 条")
        for row in hit[:3]:
            print("    -", row.get("bvid"), str(row.get("title"))[:40])
    except Exception as exc:  # noqa: BLE001
        print(f"  {name} 搜索失败:", str(exc)[:100])
    time.sleep(0.8)

print("\n=== 3) 搜索「UP名 + 梗词」能否定位到介绍视频 ===")
for keyword in ["梗百科 哈基米", "梗指南 哈基米", "梗指南 电子木鱼", "梗百科 电子木鱼"]:
    try:
        rows = client.search_videos(keyword, pages=1)
        mid = MIDS["梗百科"] if keyword.startswith("梗百科") else MIDS["梗指南"]
        hit = [r for r in rows if int(r.get("mid") or 0) == mid]
        print(f"  「{keyword}」{len(rows)} 条，该UP {len(hit)} 条", [r.get("bvid") for r in hit[:2]])
    except Exception as exc:  # noqa: BLE001
        print(f"  「{keyword}」失败:", str(exc)[:80])
    time.sleep(0.8)

print("\n=== 4) 其他可能的投稿接口 ===")
candidates = [
    ("x/series/recArchivesByKeywords", "https://api.bilibili.com/x/series/recArchivesByKeywords",
     {"mid": MIDS["梗指南"], "keywords": "哈基米", "ps": 10}),
    ("app space cursor", "https://app.bilibili.com/x/v2/space/archive/cursor",
     {"vmid": MIDS["梗指南"], "pn": 1, "ps": 10, "order": "pubdate"}),
    ("polymer web-space archives", "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list",
     {"mid": MIDS["梗指南"], "season_id": 0, "page_num": 1, "page_size": 10}),
]
for label, url, params in candidates:
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=10)
        payload = response.json()
        print(f"  {label}: http={response.status_code} code={payload.get('code')} msg={str(payload.get('message'))[:30]}")
        body = json.dumps(payload, ensure_ascii=False)
        print("     ", body[:160])
    except Exception as exc:  # noqa: BLE001
        print(f"  {label}: 异常 {exc.__class__.__name__}")
