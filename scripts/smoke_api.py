#!/usr/bin/env python
"""接口冒烟测试：对正在运行的后端逐个打一遍，输出通过/失败清单。

    python scripts/smoke_api.py                      # 默认 http://127.0.0.1:8010
    BASE=http://127.0.0.1:8000 python scripts/smoke_api.py

只读为主；会写入的接口（重新计算 / 设置保存）也覆盖，但保存用例会还原。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:8010").rstrip("/")
TIMEOUT = float(os.environ.get("TIMEOUT", "20"))

results: list[tuple[str, str, bool, str]] = []


def call(method: str, path: str, body=None, *, expect=(200,), note=""):
    # 中文查询参数必须百分号编码，否则 urllib 直接抛 ascii 错误
    quoted = urllib.parse.quote(path, safe="/?&=:%")  # 中文参数必须百分号编码
    url = f"{BASE}{quoted}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            status, payload = response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status, payload = exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        results.append((method, path, False, f"连接失败：{exc}"))
        return None

    try:
        parsed = json.loads(payload) if payload else None
    except json.JSONDecodeError:
        results.append((method, path, False, "返回不是合法 JSON"))
        return None

    ok = status in expect
    detail = f"{status}" + (f" · {note}" if note else "")
    if not ok:
        detail += f" · {payload[:120]}"
    results.append((method, path, ok, detail))
    return parsed


def check(condition: bool, label: str):
    results.append(("assert", label, bool(condition), "ok" if condition else "不满足"))


print(f"目标：{BASE}\n")

health = call("GET", "/api/health")
check(health and health.get("status") == "ok", "health.status == ok")

meta = call("GET", "/api/meta")
check(meta and meta.get("certified_count", 0) >= 30, "meta.certified_count >= 30")
check(meta and meta.get("is_demo") is True, "meta.is_demo 标记为演示数据")
check(meta and len(meta.get("lifecycle_stages", [])) == 6, "六个生命周期阶段")

lst = call("GET", "/api/memes?limit=10")
items = (lst or {}).get("items", [])
check(len(items) > 0, "榜单非空")
check([i["hotness"] for i in items] == sorted([i["hotness"] for i in items], reverse=True), "榜单按热度倒序")
check(all(0 <= i["hotness"] <= 100 for i in items), "热度都在 0-100")

for key, stages in (("hot", {"explosive"}), ("taking_off", {"sprouting", "rising"}), ("receding", {"receding", "obsolete"})):
    filtered = call("GET", f"/api/memes?filter={key}&limit=50")
    got = {item["stage"] for item in (filtered or {}).get("items", [])}
    check(got <= stages and len(got) > 0, f"筛选 {key} 只返回 {sorted(stages)}")

searched = call("GET", "/api/memes?search=赛博木鱼")
check([i["name"] for i in (searched or {}).get("items", [])] == ["电子木鱼"], "别名搜索命中")
call("GET", "/api/memes?filter=douyin", expect=(400,), note="非法筛选应 400")
call("GET", "/api/memes/999999", expect=(404,), note="不存在的梗应 404")

if items:
    meme_id = items[0]["id"]
    detail = call("GET", f"/api/memes/{meme_id}")
    check(detail and set(detail) >= {"meme", "hotness", "lifecycle", "metrics", "certification", "videos", "trend", "insight"}, "详情结构完整")
    check(detail and sum(detail["hotness"]["weights"].values()) == 1.0, "热度权重合计为 1")
    check(detail and sum(1 for s in detail["lifecycle"]["stages"] if s["active"]) == 1, "生命周期只有一个当前阶段")
    check(detail and detail["certification"]["certified"] is True, "详情梗已通过双 UP 认证")
    check(detail and all(v["relevance_score"] >= 0.5 for v in detail["videos"]), "相关视频都过相关性阈值")
    check(detail and len(detail["trend"]["points"]) == (detail["metrics"]["window_days"]), "趋势点数等于统计窗口")
    check("NaN" not in json.dumps(detail), "详情响应里没有 NaN")

    call("GET", f"/api/memes/{meme_id}/trend?window=7")
    call("GET", f"/api/memes/{meme_id}/trend?window=30")
    call("GET", f"/api/memes/{meme_id}/trend?window=12", expect=(400,), note="非法窗口应 400")
    videos = call("GET", f"/api/memes/{meme_id}/videos?limit=3")
    check(videos and len(videos["items"]) <= 3, "相关视频数量受 limit 约束")

    insight = call("POST", f"/api/memes/{meme_id}/insight", {"refresh": True})
    check(insight and insight["trend_explanation"]["status"] == "ok", "无 Key 时趋势解释走算法兜底而非报错")
    check(insight and insight["catch_up_advice"]["result"]["status"] in {"can_catch", "caution", "too_late"}, "赶梗状态是三枚举之一")

settings_before = call("GET", "/api/settings/llm")
check(settings_before and "api_key" not in settings_before["config"], "设置接口不回显明文 Key")
call("GET", "/api/llm/models", expect=(400,), note="未配置 Key 时应 400")
tested = call("POST", "/api/llm/test")
check(tested and tested["ok"] is False and "LLM_API_KEY" in tested["message"], "未配置 Key 时测试连接给出可执行提示")

recomputed = call("POST", "/api/jobs/recompute")
check(recomputed and recomputed["computed"] >= 30, "重算任务覆盖全部正式梗")
after = call("GET", "/api/memes?limit=10")
check([i["hotness"] for i in after["items"]] == [i["hotness"] for i in items], "重算是幂等的（榜单不变）")

# 采集接口只验证"可达且会拒绝非法参数"：真跑一次会改写当前数据集，
# 完整行为由 backend/tests/test_collectors.py 用假客户端覆盖。
call("POST", "/api/jobs/collect?source=douyin", expect=(422,), note="非法数据源应被参数校验拦下")

passed = sum(1 for _, _, ok, _ in results if ok)
for method, target, ok, note in results:
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {method:7} {target[:52]:52} {note}")
print(f"\n通过 {passed}/{len(results)}")
sys.exit(0 if passed == len(results) else 1)
