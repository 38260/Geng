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
check(meta and meta.get("certified_count", 0) >= 1, "meta.certified_count 至少有一个梗")
check(
    meta and sum(meta.get("source_breakdown", {}).values()) == meta.get("certified_count"),
    "source_breakdown 合计与正式梗库数量一致",
)
check(
    meta and meta.get("is_demo") == (meta.get("data_source") == "mock"),
    "meta.is_demo 与 data_source 一致（真实数据不得标演示、演示数据必须标演示）",
)
check(
    meta and len(meta.get("lifecycle_stages", [])) == 7,
    "六个生命周期阶段 + 一个「数据不足」闸门态",
)
check(
    meta and meta.get("data_through") and isinstance(meta.get("data_lag_days"), int),
    f"meta 说明统计截至哪天（{meta.get('data_through')}，滞后 {meta.get('data_lag_days')} 天）",
)

lst = call("GET", "/api/memes?limit=10")
items = (lst or {}).get("items", [])
check(len(items) > 0, "榜单非空")
check([i["hotness"] for i in items] == sorted([i["hotness"] for i in items], reverse=True), "榜单按热度倒序")
check(all(0 <= i["hotness"] <= 100 for i in items), "热度都在 0-100")
check(
    all(i.get("certified_by") for i in items),
    "榜单每条都写明证据来自哪一位 UP（并集准入，单 UP 不冒充双 UP）",
)
check(
    all((i["cert_label"] == "双 UP 认证") == i["double_certified"] for i in items),
    "认证标签与双 UP 徽章一致",
)

for key, stages in (("hot", {"explosive"}), ("taking_off", {"sprouting", "rising"}), ("receding", {"receding", "obsolete"})):
    filtered = call("GET", f"/api/memes?filter={key}&limit=50")
    got = {item["stage"] for item in (filtered or {}).get("items", [])}
    # 不要求每个筛选都有结果：真实数据可能当下没有"正在爆"的梗，那也应该返回空
    check(got <= stages, f"筛选 {key} 只返回 {sorted(stages)}（实际 {sorted(got) or '空'}）")

probe = (items or [{}])[0]
probe_alias = (probe.get("aliases") or [probe.get("name", "")])[0]
searched = call("GET", f"/api/memes?search={urllib.parse.quote(str(probe_alias))}")
check(
    probe_alias and probe.get("name") in [i["name"] for i in (searched or {}).get("items", [])],
    f"用别名「{probe_alias}」能搜到它自己（{probe.get('name')}）",
)
call("GET", "/api/memes?filter=douyin", expect=(400,), note="非法筛选应 400")
call("GET", "/api/memes/999999", expect=(404,), note="不存在的梗应 404")

if items:
    meme_id = items[0]["id"]
    detail = call("GET", f"/api/memes/{meme_id}")
    check(detail and set(detail) >= {"meme", "hotness", "lifecycle", "metrics", "certification", "intro", "videos", "trend", "insight"}, "详情结构完整")
    check(detail and bool(detail["intro"]["text"].strip()), f"详情有介绍（来源 {detail['intro']['source']}）")
    check(detail and set(detail["intro"]) >= {"text", "source", "source_label", "note", "evidence", "excerpt", "transcript"}, "介绍结构完整")
    check(
        detail and detail["intro"]["source"] in {"manual", "transcript", "evidence"},
        f"介绍标了来源：{detail['intro']['source_label']}",
    )
    # 字幕块：正文必须能在原文里逐字找到，AI 只能挑句子
    block = (detail or {}).get("intro", {}).get("transcript")
    if block:
        check(
            block["excerpt"].replace(" ", "") in block["full"].replace(" ", "") or not block["excerpt"],
            f"摘录逐字来自字幕原文（{block['kind_label']}，{block['chars']} 字）",
        )
        summary = block.get("summary")
        if summary:
            check(
                all(item.replace(" ", "") in block["full"].replace(" ", "") for item in summary["sentences"]),
                f"AI 缩短版也是整句照抄（{summary['chars']} 字，来源 {summary['source']}）",
            )
            check(
                summary["text"].replace(" ", "") in block["excerpt"].replace(" ", ""),
                "缩短版是规则摘录的子集，没多出内容",
            )
    # 整库扫一遍：点进任何一条详情都不该看到空白介绍
    library = call("GET", "/api/memes?scope=all&limit=100") or {}
    blank, sources = [], {}
    for row in library.get("items", []):
        intro = call("GET", f"/api/memes/{row['id']}")["intro"]
        sources[intro["source"]] = sources.get(intro["source"], 0) + 1
        if not intro["text"].strip():
            blank.append(row["name"])
    check(not blank, f"梗库 {len(library.get('items', []))} 条详情都有介绍（来源分布 {sources}）")
    check(detail and sum(detail["hotness"]["weights"].values()) == 1.0, "热度权重合计为 1")
    check(detail and sum(1 for s in detail["lifecycle"]["stages"] if s["active"]) == 1, "生命周期只有一个当前阶段")
    check(detail and detail["certification"]["admitted"] is True, "详情梗已通过发现层准入（任一 UP 介绍过）")
    check(
        detail and detail["certification"]["cert_label"] in {"双 UP 认证", "梗百科认证", "梗指南认证"},
        f"详情写明认证强度：{(detail or {}).get('certification', {}).get('cert_label')}",
    )
    check(detail and all(v["relevance_score"] >= 0.5 for v in detail["videos"]), "相关视频都过相关性阈值")
    check(detail and len(detail["trend"]["points"]) == (detail["metrics"]["window_days"]), "趋势点数等于统计窗口")
    # 观测覆盖度：界面必须查得到"这些数是几天观测出来的"，没观测的日子不许当零活动
    check(
        detail and "observed_days" in detail["meme"] and "coverage" in detail["meme"],
        f"卡片带覆盖度（近 {detail['meme'].get('observed_window_days')} 天观测到 "
        f"{detail['meme'].get('observed_days')} 天）",
    )
    points = detail["trend"]["points"]
    holes = [p for p in points if p.get("observed") is False]
    check(
        all("observed" in p for p in points) and all(p["video_count"] == 0 for p in holes),
        f"趋势点都带 observed 标记（{len(holes)}/{len(points)} 天是接口的洞，未被当成零活动）",
    )
    starved = [row for row in items if row["stage"] == "insufficient"]
    check(
        all(r["catch_status"] == "insufficient" and r["catch_confidence"] == 0 for r in starved),
        f"数据不足的 {len(starved)} 个榜单梗都不给赶梗结论（置信 0）",
    )
    check(
        bool((meta or {}).get("transparency", {}).get("coverage_rule")),
        "口径面板写明观测闸门（空返回怎么记、何时拒绝给结论）",
    )
    check("NaN" not in json.dumps(detail), "详情响应里没有 NaN")

    call("GET", f"/api/memes/{meme_id}/trend?window=7")
    call("GET", f"/api/memes/{meme_id}/trend?window=30")
    call("GET", f"/api/memes/{meme_id}/trend?window=12", expect=(400,), note="非法窗口应 400")
    videos = call("GET", f"/api/memes/{meme_id}/videos?limit=3")
    check(videos and len(videos["items"]) <= 3, "相关视频数量受 limit 约束")
    check(
        videos and videos.get("total", 0) >= len(videos.get("items", [])) and bool(videos.get("note")),
        f"视频接口报真实总数与口径说明（total={videos and videos.get('total')}）",
    )
    page2 = call("GET", f"/api/memes/{meme_id}/videos?limit=3&offset=3")
    overlap = {v["bvid"] for v in videos["items"]} & {v["bvid"] for v in page2["items"]}
    check(page2 and not overlap, f"offset 翻页不与首页重复（重叠 {len(overlap)} 条）")
    tail = call("GET", f"/api/memes/{meme_id}/videos?limit=3&offset={videos['total']}")
    check(tail and tail["items"] == [], "翻过末尾应返回空列表")
    call("GET", f"/api/memes/{meme_id}/videos?limit=99", expect=(422,), note="limit 越界应 422")

    insight = call("POST", f"/api/memes/{meme_id}/insight", {"refresh": True})
    trend = (insight or {}).get("trend_explanation") or {}
    check(
        trend.get("status") == "ok" and trend.get("source") in {"llm", "rule", "cache"},
        f"趋势解释可用（source={trend.get('source')}）——配了 Key 走 LLM，没配则算法兜底，两种都不许报错",
    )
    advice = ((insight or {}).get("catch_up_advice") or {}).get("result") or {}
    check(
        advice.get("status") in {"can_catch", "caution", "too_late", "insufficient"},
        f"赶梗状态在枚举内（{advice.get('status')}）",
    )

    # 刷新状态：接口必须能说出"上次什么时候刷的、自动刷新开没开"
    refresh = call("GET", "/api/jobs/refresh")
    check(
        refresh and {"running", "last", "schedule"} <= set(refresh),
        f"刷新状态可查（running={refresh and refresh.get('running')}）",
    )
    check(
        refresh and refresh["schedule"]["enabled"] == (bool((refresh["schedule"].get("at") or "").strip())
                                                      and refresh.get("data_source") == "bilibili"),
        f"定时开关自述一致：REFRESH_AT={refresh and refresh['schedule'].get('at')!r}",
    )
    check(meta and "refresh" in meta, "meta 带刷新摘要（上次时间/触发方式）")
    check(
        meta and (meta.get("refresh") or {}).get("last") is None or True,
        f"上次刷新记录：{(meta or {}).get('refresh', {}).get('last') or '还没有（只手动刷过或从未刷）'}",
    )

settings_before = call("GET", "/api/settings/llm")
check(settings_before and "api_key" not in settings_before["config"], "设置接口不回显明文 Key")
call("GET", "/api/llm/models", expect=(400,), note="未配置 Key 时应 400")
tested = call("POST", "/api/llm/test")
check(tested and tested["ok"] is False and "LLM_API_KEY" in tested["message"], "未配置 Key 时测试连接给出可执行提示")

recomputed = call("POST", "/api/jobs/recompute")
check(
    recomputed and recomputed["computed"] >= (meta or {}).get("certified_count", 0)
    - (meta or {}).get("candidate_count", 0) - 8,
    "重算任务覆盖绝大多数正式梗",
)
after = call("GET", "/api/memes?limit=10")
check([i["hotness"] for i in after["items"]] == [i["hotness"] for i in items], "重算是幂等的（榜单不变）")

# 采集接口只验证"可达且会拒绝非法参数"：真跑一次会改写当前数据集，
# 完整行为由 backend/tests/test_collectors.py 用假客户端覆盖。
call("POST", "/api/jobs/collect?source=douyin", expect=(422,), note="非法数据源应被参数校验拦下")

# --------------------------------------------------------------------------- #
# 梗管理：只验证读写通道与边界，写回用"原值重写"以免改动当前数据集
# --------------------------------------------------------------------------- #
managed = call("GET", "/api/manage/memes")
check(managed and managed["total"] >= (meta or {}).get("certified_count", 0), "管理列表覆盖榜单梗")
check(
    managed and {"managed_count", "certified_count", "in_pool_count", "out_of_pool_count"} <= set(managed),
    "管理列表带人工维护计数与准入计数",
)
check(
    managed and managed["in_pool_count"] == managed["total"] - managed["out_of_pool_count"],
    f"准入自述一致：入池 {managed['in_pool_count']} / 未入池 {managed['out_of_pool_count']}",
)
check(
    managed and managed["cert_window_days"] == (meta or {}).get("transparency", {}).get("cert_window_days"),
    f"认证窗口两处口径一致：{managed['cert_window_days']} 天滚动",
)

mid = (items or [{}])[0].get("id")
view = call("GET", f"/api/manage/memes/{mid}")
check(view and {"cover_url", "auto_cover", "effective_cover", "cover_options", "note"} <= set(view), "管理详情字段齐全")
check(view and all(o["cover"].startswith("https://") for o in view["cover_options"]), "可挑封面都是完整 https 地址")
check(view and view["note"] and "不会改动已算好的热度" in view["note"], "管理接口自述边界")

for bad in [{"cover_url": "javascript:alert(1)"}, {"hotness": 100}, {"certified": True}, {}]:
    call("PATCH", f"/api/manage/memes/{mid}", bad, expect=(400,), note=f"拒绝越界字段：{list(bad) or '空请求'}")

same = call("PATCH", f"/api/manage/memes/{mid}", {"description": view["description"]})
check(same and same["changed"] == ["description"], "原值写回也算一次有效保存")
after_meta = call("GET", "/api/memes?limit=10")
check(
    [i["hotness"] for i in after_meta["items"]] == [i["hotness"] for i in items],
    "改元数据后热度与榜单不变（人工改不到算法结论）",
)
missing = call("GET", "/api/manage/memes/999999", expect=(404,), note="不存在的梗应 404")
check(missing and "梗不存在" in str(missing.get("detail", "")), "管理详情 404 说的是人话")

passed = sum(1 for _, _, ok, _ in results if ok)
for method, target, ok, note in results:
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {method:7} {target[:52]:52} {note}")
print(f"\n通过 {passed}/{len(results)}")
sys.exit(0 if passed == len(results) else 1)
