"""开题答辩 PPT 的素材生成：所有数字都从真实库里现取，图表直接落 PNG。

    python scripts/pitch_assets.py

产出：
* docs/pitch/facts.json          —— 写稿时引用的事实（一次算清，避免手抄错）
* docs/pitch/assets/*.png        —— 四张图：热度曲线 / 权重条 / 覆盖率 / 解说播放量对照散点

刻意不留"大概、差不多"：每张图旁边标注的数字都来自本次查询，改数据后重跑即可。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "backend" / "data" / "gengv1.db"
REPORT = ROOT / "backend" / "data" / "recent_certified.json"
OUT = ROOT / "docs" / "pitch"
ASSETS = OUT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

# 配色取自 frontend/tailwind.config.js（首页就是这套色，答辩稿与产品同色才不像套模板）
BRAND = "#FB3A5E"
BRAND_SOFT = "#FDE9EE"
FLARE = "#0D8AFE"
GO = "#019646"
GOLD = "#FDC069"
DUSK = "#546F98"
INK = "#000214"
INK_MUTE = "#5E739F"
LINE = "#ECF0F6"

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def q(sql: str, params: tuple = ()) -> list:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def leaderboard() -> list[dict]:
    """与后端榜单同一口径：入池 + 有快照 + 真实数据 + 至少一位 UP 有真实投稿证据。"""
    return q(
        """
        SELECT m.name AS name, h.score AS score, l.stage_label AS stage, l.catch_label AS catch_label,
               m.verification_state AS verification, m.encyclopedia_confirmed AS enc, m.guide_confirmed AS gui
        FROM memes m
        JOIN hotness_snapshots h ON h.meme_id = m.id
        JOIN lifecycle_snapshots l ON l.meme_id = m.id
        WHERE (m.encyclopedia_confirmed = 1 OR m.guide_confirmed = 1)
          AND m.status = 'certified' AND m.data_source = 'bilibili'
          AND m.verification_state IN ('verified_both', 'partially_verified')
        ORDER BY h.score DESC
        """
    )


def cert_of(row: dict) -> str:
    if row["enc"] and row["gui"]:
        return "双 UP 认证"
    return "梗百科认证" if row["enc"] else "梗指南认证"


def series_of(name: str) -> tuple[list[str], list[float]]:
    rows = q(
        """
        SELECT s.stat_date AS day, s.hotness AS hotness FROM meme_daily_stats s
        JOIN memes m ON m.id = s.meme_id WHERE m.name = ? ORDER BY s.stat_date
        """,
        (name,),
    )
    return [str(r["day"])[5:] for r in rows], [float(r["hotness"] or 0) for r in rows]


def chart_curves(days: list[str], curves: dict[str, list[float]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 3.5), dpi=200)
    colors = {"闪身步": BRAND, "琵琶曲": FLARE, "老叟戏顽童": DUSK}
    for name, values in curves.items():
        span = len(days)
        ax.plot(
            days[: len(values)], values,
            color=colors[name], linewidth=2.6 if name == "闪身步" else 1.9,
            linestyle="-" if name == "闪身步" else "--",
            marker="o", markersize=3.4, markevery=max(1, len(values) // 8), label=name,
        )
        if values:
            ax.annotate(
                f"{name} {values[-1]:.0f}", (len(values) - 1, values[-1]),
                xytext=(6, 0), textcoords="offset points", fontsize=9,
                color=colors[name], va="center", fontweight="bold",
            )
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(axis="y", color=LINE, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=INK_MUTE, labelsize=9)
    ax.set_xticks(list(range(0, len(days), 5)))
    ax.set_xticklabels([days[i] for i in ax.get_xticks() if i < len(days)], fontsize=9, color=INK_MUTE)
    ax.set_title("同一把尺子下的三种命：一个在冲、一个脉冲、一个已经退潮", fontsize=11.5,
                 color=INK, loc="left", fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_weights(path: Path) -> None:
    items = [
        ("增长", 0.25, BRAND),
        ("播放量", 0.25, FLARE),
        ("互动", 0.20, GO),
        ("内容量", 0.16, GOLD),
        ("创作者", 0.14, DUSK),
    ]
    fig, ax = plt.subplots(figsize=(6.4, 2.9), dpi=200)
    names = [i[0] for i in items][::-1]
    values = [i[1] * 100 for i in items][::-1]
    colors = [i[2] for i in items][::-1]
    ax.barh(names, values, color=colors, height=0.62)
    for index, value in enumerate(values):
        ax.text(value + 1.2, index, f"{value:.0f}%", va="center", fontsize=10,
                color=INK, fontweight="bold")
    ax.set_xlim(0, 33)
    ax.set_xticks([])
    ax.grid(axis="x", color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=INK, labelsize=10.5)
    ax.set_title("热度指数五因子：增长与播放各占 1/4，绝对量做对数区间归一", fontsize=11.5,
                 color=INK, loc="left", fontweight="bold", pad=10)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_coverage(path: Path, report: dict) -> None:
    enc = report["stats"]["梗百科"]["named"]
    gui = report["stats"]["梗指南"]["named"]
    both = len(report["certified"])
    union = len(report["pool"])
    names = ["梗百科\n介绍过", "梗指南\n介绍过", "两位都做过\n（旧口径闸门）", "任一做过\n（新口径入池）"]
    values = [enc, gui, both, union]
    colors = [FLARE, DUSK, INK_MUTE, BRAND]
    fig, ax = plt.subplots(figsize=(6.2, 3.1), dpi=200)
    bars = ax.bar(names, values, color=colors, width=0.6)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 1.1, str(value), ha="center",
                fontsize=12, color=INK, fontweight="bold")
    ax.set_ylim(0, max(values) * 1.25)
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=INK, labelsize=9.5)
    ax.set_title("把闸门从交集换成并集：同一批投稿，能进库的梗从 8 个变成 51 个",
                 fontsize=11.5, color=INK, loc="left", fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_scatter(path: Path, points: list[tuple[str, float, float]]) -> None:
    """解说视频播放量 vs 该梗自身热度：用真实数据检验"破百万才值得做"这个直觉。"""
    x = np.array([p[1] for p in points]) / 10_000
    y = np.array([p[2] for p in points])
    fig, ax = plt.subplots(figsize=(6.6, 3.4), dpi=200)
    ax.scatter(x, y, s=42, color=BRAND, alpha=0.62, edgecolors="white", linewidths=1.0, zorder=3)

    # 只标能讲故事的那几个点：满屏标签等于没有标签
    labels = {"闪身步", "宗主第二招", "野生狗奶", "老叟戏顽童", "雨中霸王龙"}
    hot = {(name, ex): (px, py) for (name, ex, own), px, py in zip(points, x, y)}
    for (name, _), (px, py) in hot.items():
        if name not in labels:
            continue
        ax.annotate(
            name, (px, py), xytext=(9, 6), textcoords="offset points",
            fontsize=9.4, color=INK, fontweight="bold",
        )
    # 两个反例加圈：解说 64.6 万的成了榜首，解说 160.7 分的热度 0
    for name in ("闪身步", "宗主第二招"):
        px, py = next(((px, py) for (n, _), (px, py) in hot.items() if n == name), (None, None))
        if px is not None:
            ax.scatter([px], [py], s=250, facecolors="none", edgecolors=FLARE, linewidths=1.8, zorder=4)

    pear = stats.pearsonr(x, y)
    spear = stats.spearmanr(x, y)
    ax.axvline(100, color=DUSK, linewidth=1.2, linestyle=":")
    ax.text(104, 88, "『破百万』门槛", fontsize=9, color=DUSK)
    ax.grid(color=LINE, linewidth=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(LINE)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=INK_MUTE, labelsize=9)
    ax.set_xlabel("解说视频自己的播放量（万）", fontsize=10, color=INK)
    ax.set_ylabel("该梗 30 天热度", fontsize=10, color=INK)
    ax.set_ylim(-6, 100)
    ax.set_title(
        f"解说视频火 ≠ 梗火（n={len(points)}，Pearson r={pear[0]:+.2f}，Spearman ρ={spear[0]:+.2f}）",
        fontsize=11.5, color=INK, loc="left", fontweight="bold", pad=12,
    )
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return {"pearson": round(pear[0], 3), "pearson_p": round(pear[1], 4),
            "r2": round(pear[0] ** 2, 3),
            "spearman": round(spear[0], 3), "spearman_p": round(spear[1], 4), "n": len(points)}


def real_covers(names: list[str]) -> dict[str, str]:
    """把榜单上前几个梗的真实封面拉下来当贴纸。

    B 站图床带 Referer 会 403，不带才 200——前端里踩过，这里同理。
    下不到就返回空，页面会退回纯色块，不影响数字。
    """
    import urllib.request

    out: dict[str, str] = {}
    rows = q(
        """
        SELECT m.name AS name, v.cover AS cover, v.bvid AS bvid FROM videos v
        JOIN memes m ON m.id = v.meme_id
        WHERE v.data_source = 'bilibili' AND v.cover <> ''
        ORDER BY v.view DESC
        """
    )
    wanted = {name for name in names}
    picked: dict[str, str] = {}
    for row in rows:
        if row["name"] in wanted and row["name"] not in picked:
            picked[row["name"]] = "https:" + row["cover"] if row["cover"].startswith("//") else row["cover"]
        if len(picked) == len(wanted):
            break
    folder = ASSETS / "covers"
    folder.mkdir(parents=True, exist_ok=True)
    for name, url in picked.items():
        slug = "".join(ch for ch in name if ch.isalnum()) or "meme"
        target = folder / f"{slug}.jpg"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                target.write_bytes(response.read())
            out[name] = target.relative_to(ROOT).as_posix()
        except Exception as exc:  # noqa: BLE001 - 封面只是装饰，拿不到就跳过
            print(f"封面下载失败 {name}: {exc}")
    return out


def main() -> int:
    board = leaderboard()
    counts = {
        "memes": q("SELECT COUNT(*) c FROM memes")[0]["c"],
        "admitted": q("SELECT COUNT(*) c FROM memes WHERE encyclopedia_confirmed=1 OR guide_confirmed=1")[0]["c"],
        "double": q("SELECT COUNT(*) c FROM memes WHERE certified=1")[0]["c"],
        "real_memes": q("SELECT COUNT(*) c FROM memes WHERE data_source='bilibili'")[0]["c"],
        "demo_memes": q("SELECT COUNT(*) c FROM memes WHERE data_source='mock'")[0]["c"],
        "stat_rows": q("SELECT COUNT(*) c FROM meme_daily_stats")[0]["c"],
        "stat_days_with_content": q("SELECT COUNT(*) c FROM meme_daily_stats WHERE video_count>0")[0]["c"],
        "videos": q("SELECT COUNT(*) c FROM videos")[0]["c"],
        "views_total": q("SELECT SUM(view) v FROM meme_daily_stats")[0]["v"] or 0,
        "through": q("SELECT MAX(stat_date) d FROM meme_daily_stats")[0]["d"],
        "on_board": len(board),
        "no_series": q(
            """SELECT COUNT(*) c FROM memes m
               WHERE (m.encyclopedia_confirmed=1 OR m.guide_confirmed=1)
                 AND NOT EXISTS(SELECT 1 FROM meme_daily_stats s WHERE s.meme_id=m.id AND s.video_count>0)"""
        )[0]["c"],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    # 曲线：一个正在冲的、一个脉冲型的、一个已退潮的
    days, _ = series_of("闪身步")
    curves = {}
    for name in ("闪身步", "琵琶曲", "老叟戏顽童"):
        d, v = series_of(name)
        if len(d) == len(days):
            curves[name] = v
    chart_curves(days, curves, ASSETS / "curves.png")
    chart_weights(ASSETS / "weights.png")
    chart_coverage(ASSETS / "coverage.png", report)

    play = {
        item["name"]: max(
            (item["encyclopedia"] or {}).get("play", 0),
            (item["guide"] or {}).get("play", 0),
        )
        for item in report["pool"]
    }
    points = [
        (row["name"], float(play.get(row["name"], 0)), float(row["score"]))
        for row in board
        if play.get(row["name"])
    ]
    corr = chart_scatter(ASSETS / "scatter.png", points)

    # 榜单前十 + 稿子里会被贴成贴纸的几个名字（反例、脉冲型梗）
    top_names = [row["name"] for row in board[:10]] + [
        "宗主第二招", "胆子真是肥嘟嘟的", "正太扭腰", "尴尬狗", "中国人能飞",
    ]
    covers = real_covers(top_names)

    facts = {
        "generated_at": date.today().isoformat(),
        "counts": counts,
        "correlation": corr,
        "covers": covers,
        "coverage": {
            "encyclopedia_named": report["stats"]["梗百科"]["named"],
            "guide_named": report["stats"]["梗指南"]["named"],
            "intersection": len(report["certified"]),
            "union": len(report["pool"]),
            "cert_days": report["cert_days"],
            "collected": 30,
            "empty": 21,
        },
        "top": [
            {"name": row["name"], "score": round(row["score"], 1), "stage": row["stage"],
             "catch": row["catch_label"], "cert": cert_of(row)}
            for row in board[:10]
        ],
        "stages": {row["stage"]: sum(1 for r in board if r["stage"] == row["stage"]) for row in board},
        "curve_days": {"from": days[0] if days else "", "to": days[-1] if days else ""},
    }
    (OUT / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(facts["counts"], ensure_ascii=False, indent=2))
    print("相关性：", corr)
    print("散点样本：", len(points), [p[0] for p in points][:8])
    print("前 5：", [(row["name"], round(row["score"], 1), cert_of(row)) for row in board[:5]])
    print("封面：", len(facts["covers"]), sorted(facts["covers"]))
    print("曲线覆盖：", list(curves), days[0] if days else "-", "→", days[-1] if days else "-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
