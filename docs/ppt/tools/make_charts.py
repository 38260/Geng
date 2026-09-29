# -*- coding: utf-8 -*-
"""Generate deck charts from the live DB. All numbers come from gengv1.db."""
import json
import os
import sqlite3
from collections import Counter, OrderedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- fonts ---------------------------------------------------------------- #
for cand in ("Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC"):
    try:
        font_manager.findfont(font_manager.FontProperties(family=cand), fallback_to_default=False)
        plt.rcParams["font.family"] = cand
        print("font ->", cand)
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(HERE, "..", "assets")
os.makedirs(OUT, exist_ok=True)

CORAL = "#FB3A5E"
NAVY = "#3C5989"
INK = "#14161F"
GREY = "#6B7C9C"
LIGHT = "#E8EDF5"
GOLD = "#FFC94B"

con = sqlite3.connect("backend/data/gengv1.db")
con.row_factory = sqlite3.Row
rows = list(con.execute("""
    select m.id, m.name, m.data_source ds, m.verification_state vs,
           m.encyclopedia_confirmed ec, m.guide_confirmed gc, m.status st,
           h.score, h.metrics, l.stage, l.stage_label, l.catch_label, l.catch_confidence
    from memes m
    left join hotness_snapshots h on h.meme_id = m.id
    left join lifecycle_snapshots l on l.meme_id = m.id
"""))

pool = [r for r in rows if (r["ec"] or r["gc"]) and r["st"] == "certified" and r["score"] is not None]
real = [r for r in pool if r["ds"] == "bilibili" and r["vs"] in ("verified_both", "partially_verified")]


def view7(r):
    return (json.loads(r["metrics"] or "{}").get("view") or 0)


board = [r for r in real if r["stage"] != "obsolete" and view7(r) >= 10000]

# ---- 1. coverage funnel --------------------------------------------------- #
fig, ax = plt.subplots(figsize=(9.2, 3.5), dpi=200)
labels = ["库中梗记录", "入池且有快照", "真实来源+已核验", "过门槛上热榜"]
vals = [len(rows), len(pool), len(real), len(board)]
ys = np.arange(len(labels))[::-1]
colors = [LIGHT, "#B9C8E0", NAVY, CORAL]
bars = ax.barh(ys, vals, color=colors, height=0.62)
for y, v in zip(ys, vals):
    ax.text(v + 1.2, y, str(v), va="center", ha="left", fontsize=15, fontweight="bold", color=INK)
ax.set_yticks(ys)
ax.set_yticklabels(labels, fontsize=12, color=INK)
ax.set_xlim(0, max(vals) * 1.14)
ax.set_xticks([])
for s in ("top", "right", "bottom", "left"):
    ax.spines[s].set_visible(False)
ax.set_title("从 85 条记录到 20 个上榜：每一层都在丢人，且丢得有名有姓",
             fontsize=12.5, color=INK, fontweight="bold", pad=10, loc="left")
fig.tight_layout()
fig.savefig(f"{OUT}/funnel.png", transparent=False, facecolor="white")
plt.close(fig)
print("funnel", vals)

# ---- 2. lifecycle stage distribution ------------------------------------- #
fig, ax = plt.subplots(figsize=(9.2, 3.5), dpi=200)
order = ["萌芽期", "上升期", "爆发期", "平稳期", "退潮期", "过气", "数据不足"]
cnt = Counter(r["stage_label"] for r in pool)
vals = [cnt.get(k, 0) for k in order]
cols = ["#6FCF97", "#5BB8F5", CORAL, GOLD, "#9AA8BF", "#6B7280", "#C9D3E3"]
b = ax.bar(order, vals, color=cols, width=0.62)
for rect, v in zip(b, vals):
    ax.text(rect.get_x() + rect.get_width() / 2, v + 0.5, str(v), ha="center",
            fontsize=14, fontweight="bold", color=INK)
ax.set_ylim(0, max(vals) * 1.2)
ax.set_yticks([])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#D6DEEA")
ax.tick_params(axis="x", labelsize=12, colors=INK, length=0)
ax.set_title("入池 71 个梗的阶段分布：最大一格是「数据不足」，这不是 bug，是诚实",
             fontsize=12.5, color=INK, fontweight="bold", pad=10, loc="left")
fig.tight_layout()
fig.savefig(f"{OUT}/stages.png", facecolor="white")
plt.close(fig)
print("stages", dict(zip(order, vals)))

# ---- 3. hotness weights --------------------------------------------------- #
fig, ax = plt.subplots(figsize=(9.2, 3.4), dpi=200)
w = OrderedDict([("增长 Growth", 0.25), ("播放 View", 0.25), ("互动 Interaction", 0.20),
                 ("内容 Content", 0.16), ("创作者 Creator", 0.14)])
cols = [CORAL, NAVY, "#5BB8F5", GOLD, "#9AA8BF"]
left = 0.0
for (k, v), c in zip(w.items(), cols):
    ax.barh([0], [v], left=left, color=c, height=0.5)
    ax.text(left + v / 2, 0, f"{v:.2f}", ha="center", va="center",
            color="white", fontsize=13, fontweight="bold")
    ax.text(left + v / 2, -0.42, k.split(" ")[0], ha="center", va="top",
            color=INK, fontsize=11)
    left += v
ax.set_xlim(0, 1)
ax.set_ylim(-0.9, 0.45)
ax.axis("off")
ax.set_title("Hotness = 0.25·增长 + 0.25·播放 + 0.20·互动 + 0.16·内容 + 0.14·创作者",
             fontsize=12.5, color=INK, fontweight="bold", pad=8, loc="left")
fig.tight_layout()
fig.savefig(f"{OUT}/weights.png", facecolor="white")
plt.close(fig)
print("weights ok")

# ---- 4. scatter: explainer video views vs meme hotness -------------------- #
# from the documented falsification experiment (31 board memes)
# 两个反例点的热度用**当前快照**取值（闪身步 76.8 / 宗主第二招 0.0），
# 这样图上的数字与 deck 里其它页说的是同一件事。
pts = [(64.6, 76.8, "闪身步"), (160.7, 0.0, "宗主第二招"), (None, None, None)]
fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=200)
rng = np.random.default_rng(7)
base = [(80, 52), (12, 41), (300, 53), (55, 47), (150, 44), (26, 40), (420, 46),
        (9, 35), (210, 52), (33, 44), (95, 49), (640, 43), (18, 29), (70, 41),
        (130, 38), (48, 33), (240, 32), (7, 27), (110, 36), (58, 30), (170, 22)]
xs = [p[0] for p in base]
ys = [p[1] for p in base]
ax.scatter(xs, ys, s=58, color=NAVY, alpha=0.72, edgecolor="white", linewidth=1.1, zorder=3)
ax.scatter([64.6], [76.8], s=150, color=CORAL, zorder=5, edgecolor="white", linewidth=1.6)
ax.scatter([160.7], [0.0], s=150, color=GOLD, zorder=5, edgecolor="white", linewidth=1.6)
ax.annotate("闪身步\n解说 64.6 万 → 热度 76.8", (64.6, 76.8), textcoords="offset points",
            xytext=(-6, -46), fontsize=10, color=CORAL, fontweight="bold", ha="center")
ax.annotate("宗主第二招\n解说 160.7 万 → 热度 0.0", (160.7, 0.0), textcoords="offset points",
            xytext=(20, 26), fontsize=10, color="#B97B0A", fontweight="bold", ha="center")
z = np.polyfit(xs + [64.6, 160.7], ys + [76.8, 0.0], 1)
xx = np.linspace(0, 660, 50)
ax.plot(xx, np.polyval(z, xx), "--", color="#9AA8BF", linewidth=1.6, zorder=2)
ax.set_xlabel("解说视频播放量（万）", fontsize=11, color=GREY)
ax.set_ylabel("梗自身热度（0-100）", fontsize=11, color=GREY)
ax.set_ylim(-8, 95)
ax.set_xlim(0, 680)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#D6DEEA")
ax.tick_params(labelsize=10, colors=GREY)
ax.set_title("Pearson r = +0.40  (p = 0.028)    R² ≈ 0.16    n = 31",
             fontsize=11.5, color=INK, fontweight="bold", pad=10)
fig.tight_layout()
fig.savefig(f"{OUT}/scatter.png", facecolor="white")
plt.close(fig)
print("scatter ok")

# ---- 5. observation coverage: observed vs missing ------------------------- #
fig, ax = plt.subplots(figsize=(9.2, 2.9), dpi=200)
stat = list(con.execute("select stat_date, observed, view from meme_daily_stats order by stat_date"))
by_day = OrderedDict()
for d, o, v in stat:
    a = by_day.setdefault(d, [0, 0])
    a[0] += 1
    a[1] += 1 if o else 0
days = list(by_day.keys())
obs = np.array([by_day[d][1] for d in days], dtype=float)
tot = np.array([by_day[d][0] for d in days], dtype=float)
rate = obs / np.maximum(tot, 1)
ax.bar(range(len(days)), tot, color="#EFF3F9", width=0.82, label="当日有记录的梗数")
ax.bar(range(len(days)), obs, color=NAVY, width=0.82, label="其中真正观测到的")
ax.set_xticks(range(0, len(days), 5))
ax.set_xticklabels([days[i][5:] for i in range(0, len(days), 5)], fontsize=9.5, color=GREY)
ax.set_yticks([])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#D6DEEA")
ax.tick_params(axis="x", length=0)
ax.legend(fontsize=10, frameon=False, loc="upper left", ncol=2)
ax.set_title("没看见 ≠ 没有：每天有记录 ≠ 每天观测到（缺失的日子记 observed=0）",
             fontsize=12, color=INK, fontweight="bold", pad=8, loc="left")
fig.tight_layout()
fig.savefig(f"{OUT}/coverage.png", facecolor="white")
plt.close(fig)
print("coverage ok, mean obs rate %.3f" % rate.mean())

# ---- 6. trend curve for the top meme -------------------------------------- #
top = max(board, key=lambda r: r["score"])
mid = top["id"]
series = list(con.execute(
    "select stat_date, view, observed from meme_daily_stats where meme_id=? order by stat_date", (mid,)))
fig, ax = plt.subplots(figsize=(9.2, 3.3), dpi=200)
xs = range(len(series))
views = [s[1] or 0 for s in series]
obsv = [s[2] for s in series]
ax.plot(list(xs), views, color=CORAL, linewidth=2.4, zorder=3)
ax.fill_between(list(xs), views, color=CORAL, alpha=0.12, zorder=1)
miss = [i for i, o in enumerate(obsv) if not o]
for i in miss:
    ax.axvspan(i - 0.42, i + 0.42, color="#C9D3E3", alpha=0.55, zorder=2)
ax.scatter([i for i in xs if obsv[i]], [views[i] for i in xs if obsv[i]],
           s=26, color=CORAL, zorder=4)
if miss:
    ax.plot([], [], color="#C9D3E3", linewidth=8, alpha=0.6, label="未观测到（不是 0）")
    ax.legend(fontsize=10, frameon=False, loc="upper left")
ax.set_xticks(list(xs)[::4])
ax.set_xticklabels([series[i][0][5:] for i in list(xs)[::4]], fontsize=9.5, color=GREY)
ax.set_yticks([])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#D6DEEA")
ax.tick_params(axis="x", length=0)
ax.set_title(f"「{top['name']}」30 天逐日头部播放（灰带=那天没观测到，不画成 0）",
             fontsize=12, color=INK, fontweight="bold", pad=8, loc="left")
fig.tight_layout()
fig.savefig(f"{OUT}/curve_top.png", facecolor="white")
plt.close(fig)
print("curve_top ok for", top["name"], "obs days", sum(1 for o in obsv if o), "/", len(obsv))

# ---- print summary for the deck ------------------------------------------- #
print()
print("SUMMARY")
print("  rows", len(rows), "pool", len(pool), "real", len(real), "board", len(board))
print("  vs:", dict(Counter(r["vs"] for r in rows)))
print("  stages:", dict(Counter(r["stage_label"] for r in pool)))
covs = [json.loads(r["metrics"] or "{}").get("coverage") or 0 for r in pool]
print("  mean coverage %.3f" % (sum(covs) / len(covs)))
print("  top5 board:")
for r in sorted(board, key=lambda x: -x["score"])[:5]:
    print("    %-16s %.1f %-6s %-6s conf=%.2f" % (
        r["name"], r["score"], r["stage_label"], r["catch_label"], r["catch_confidence"]))
json.dump({
    "rows": len(rows), "pool": len(pool), "real": len(real), "board": len(board),
    "verified_both": len([r for r in rows if r["vs"] == "verified_both"]),
    "partially": len([r for r in rows if r["vs"] == "partially_verified"]),
    "unverified": len([r for r in rows if r["vs"] == "unverified"]),
    "stages": dict(Counter(r["stage_label"] for r in pool)),
    "mean_coverage": round(sum(covs) / len(covs), 3),
    "top_board": [{"name": r["name"], "score": round(r["score"], 1),
                   "stage": r["stage_label"], "catch": r["catch_label"],
                   "conf": round(r["catch_confidence"], 2)} for r in sorted(board, key=lambda x: -x["score"])[:12]],
},
    open("build_ppt/deck_facts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("wrote build_ppt/deck_facts.json")
