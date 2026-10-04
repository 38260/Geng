# -*- coding: utf-8 -*-
"""赶梗潮 · 数据获取与处理 Demo（可独立运行）

这个脚本只做三件事，对应分工里的第 4 项：采集 → 清洗 → 字段描述。
它刻意做得很小（约 300 行），但每一步的口径都和主项目 backend/ 里的一致，
方便对照。

用法：
    python demo_pipeline.py            # 用 raw/ 下的真实快照跑（离线、可重复）
    python demo_pipeline.py --live     # 现场重新采一次（需要能连 B 站，有频率控制）

产出（都写在脚本同目录的 out/ 下）：
    videos_clean.csv     清洗后的视频级数据
    daily_stats.csv      按 梗 × 日 聚合的日粒度数据
    report.md            本次运行的处理报告（丢了多少、为什么丢）

数据来源说明：
    raw/*.json 是 2026-10-05 用 B 站 wbi/search/type 接口真实抓取的原始返回体，
    未做任何加工。每份对应「一个梗名 × 一个自然日」，page_size=30。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# --------------------------------------------------------------------------
# 0. 口径常量：全部集中在这里，和 backend/app/config/algorithms.py 对齐
# --------------------------------------------------------------------------

# 相关性打分权重：标题 / 简介 / 标签
W_TITLE, W_DESC, W_TAG = 0.6, 0.2, 0.2
RELEVANCE_THRESHOLD = 0.5

# 短别名（< 4 个汉字）只算弱证据：中文 2~3 字别名基本就是常用词。
# 实测过的坑：「我不是黄豆」的别名写成"黄豆"，418 条样本里 343 条其实在讲炒黄豆。
STRONG_ALIAS_LEN = 4

# 每个梗的查询词。name 是梗名，aliases 是别名。
MEMES = {
    "闪身步": {"name": "闪身步", "aliases": []},
    "琵琶曲": {"name": "琵琶曲", "aliases": []},
}

HTML_TAG = re.compile(r"<[^>]+>")


# --------------------------------------------------------------------------
# 1. 采集层
# --------------------------------------------------------------------------

def load_raw(raw_dir: Path) -> list[dict]:
    """读 raw/ 下的原始返回体，拆成一条条视频记录（每条带它属于哪个梗、哪天）。

    这里同时演示了「两种空」的区分——这是本项目踩过的最大的坑：
      {"result": [], "numResults": 0}   -> 真的没内容（可信）
      {"v_voucher": "voucher_xxx"}      -> 被限流吞掉（不可信，不能记成 0）
    """
    rows: list[dict] = []
    files = sorted(raw_dir.glob("search_*.json"))
    if not files:
        sys.exit(f"没有找到原始数据：{raw_dir}/search_*.json")

    for fp in files:
        # 文件名约定：search_<梗名>_<YYYYMMDD>.json
        parts = fp.stem.split("_")
        meme, day = parts[1], parts[2]

        payload = json.loads(fp.read_text(encoding="utf-8"))
        data = payload.get("data") or {}

        # —— 两种空的判定，顺序不能反 ——
        if "v_voucher" in data or "v_voucher" in payload:
            print(f"[跳过] {fp.name}: 命中风控 v_voucher，这次没给数据（不等于当天没内容）")
            continue
        if not data.get("result"):
            print(f"[空窗] {fp.name}: numResults={data.get('numResults', 0)}，当天确实没内容")
            continue

        for item in data["result"]:
            item["_meme"] = meme
            item["_query_day"] = day
            item["_num_results"] = data.get("numResults", 0)
            rows.append(item)

    return rows


def fetch_live(keyword: str, day: str, page_size: int = 30) -> dict:
    """现场采集一份原始返回体（需要网络）。

    只做一次请求，不做翻页、不加 Cookie、带 2 秒间隔，属于最小必要采集。
    """
    import hashlib
    import ssl
    import urllib.parse
    import urllib.request

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }

    def get(url: str) -> dict:
        req = urllib.request.Request(url, headers=headers)
        raw = urllib.request.urlopen(req, timeout=15, context=ctx).read()
        return json.loads(raw.decode("utf-8", "ignore"))

    # WBI 签名：B 站 2023 年后对 web 接口统一加的签名（w_rid + wts）
    mixin_tab = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52,
    ]
    nav = get("https://api.bilibili.com/x/web-interface/nav")
    wbi = nav["data"]["wbi_img"]
    img = wbi["img_url"].rsplit("/", 1)[-1].split(".")[0]
    sub = wbi["sub_url"].rsplit("/", 1)[-1].split(".")[0]
    mixin = "".join((img + sub)[i] for i in mixin_tab)[:32]

    params = {
        "search_type": "video",
        "keyword": keyword,
        "order": "click",
        "page": 1,
        "page_size": page_size,
        "pubtime_begin_s": int(time.mktime(time.strptime(day, "%Y-%m-%d"))),
        "pubtime_end_s": int(
            time.mktime(time.strptime(day, "%Y-%m-%d")) + 86400
        ),
    }
    clean = {
        k: "".join(c for c in str(v) if c not in "!'()*")
        for k, v in sorted(params.items())
    }
    clean["wts"] = str(int(time.time()))
    query = urllib.parse.urlencode(clean)
    clean["w_rid"] = hashlib.md5((query + mixin).encode()).hexdigest()

    return get(
        "https://api.bilibili.com/x/web-interface/wbi/search/type?"
        + urllib.parse.urlencode(clean)
    )


# --------------------------------------------------------------------------
# 2. 清洗层
# --------------------------------------------------------------------------

def strip_html(text: str) -> str:
    """搜索结果里的命中词会被包成 <em class="keyword">，必须剥掉。"""
    return HTML_TAG.sub("", text or "").strip()


def parse_duration(value) -> int:
    """'0:38' -> 38；'1:02:03' -> 3723。搜索接口给的是字符串。"""
    if isinstance(value, (int, float)):
        return int(value)
    parts = str(value or "0").split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    seconds = 0
    for n in nums:
        seconds = seconds * 60 + n
    return seconds


def score_relevance(item: dict, meme: dict) -> tuple[float, list[str]]:
    """相关性打分，与 backend/app/analytics/relevance.py 同一套口径。

        score = 0.6 * 标题分 + 0.2 * 简介分 + 0.2 * 关键词覆盖率
        标题分：梗名命中 1.0 / 长别名(>=4字) 0.85 / 短别名 0.5 / 关键词 0.5
        简介分：梗名命中 1.0 / 别名 0.6 / 关键词 0.4
        进入统计的条件：score >= 0.5

    注意标题分与简介分是「互斥取最高档」，不是相加：所以一个视频只在简介里
    提到梗名，拿到的只是 0.2×1.0 = 0.2 分，会被过滤掉。这条规则很关键——
    它保证了进统计的样本标题里真的出现了这个梗。
    """
    name = (meme["name"] or "").strip().lower()
    aliases = [a.strip().lower() for a in meme.get("aliases", []) if a.strip()]
    keywords = [k.strip().lower() for k in meme.get("keywords", []) if k.strip()]

    title = strip_html(item.get("title", "")).lower()
    desc = strip_html(item.get("description", "")).lower()
    tag = (item.get("tag") or "").lower()
    blob = f"{title} {desc} {tag}"

    # 标题分
    if name and name in title:
        title_score = 1.0
    else:
        hit_aliases = [a for a in aliases if a in title]
        if hit_aliases:
            title_score = 0.85 if max(len(a) for a in hit_aliases) >= STRONG_ALIAS_LEN else 0.5
        elif any(k in title for k in keywords):
            title_score = 0.5
        else:
            title_score = 0.0

    # 简介分
    if name and name in desc:
        desc_score = 1.0
    elif any(a in desc for a in aliases):
        desc_score = 0.6
    elif any(k in desc for k in keywords):
        desc_score = 0.4
    else:
        desc_score = 0.0

    # 关键词覆盖率
    if keywords:
        keyword_score = sum(1 for k in keywords if k in blob) / len(keywords)
    else:
        keyword_score = 0.0

    hits = [t for t in [meme["name"], *meme.get("aliases", []), *meme.get("keywords", [])] if t and t.lower() in blob]
    score = W_TITLE * title_score + W_DESC * desc_score + W_TAG * keyword_score
    return round(min(1.0, max(0.0, score)), 4), hits


def clean(rows: list[dict]) -> tuple[list[dict], dict]:
    """把原始记录清洗成可用于聚合的规整表。"""
    stats = Counter()
    cleaned: list[dict] = []
    seen_bvid: set[str] = set()

    for item in rows:
        meme = MEMES.get(item["_meme"])
        if meme is None:
            stats["未知梗"] += 1
            continue

        # ① 日期区间校验：B 站偶尔会把区间外的视频塞进来
        pub = datetime.fromtimestamp(int(item.get("pubdate") or 0))
        day = datetime.strptime(item["_query_day"], "%Y%m%d")
        if not (day <= pub < day + timedelta(days=1)):
            stats["区间外剔除"] += 1
            continue

        # ② 去重：同一 bvid 在同一次采集里只留一条
        bvid = item.get("bvid") or ""
        if not bvid:
            stats["缺 bvid 剔除"] += 1
            continue
        if bvid in seen_bvid:
            stats["重复剔除"] += 1
            continue

        # ③ 相关性打分 + 阈值过滤
        score, hits = score_relevance(item, meme)
        if score < RELEVANCE_THRESHOLD:
            stats["相关性不足剔除"] += 1
            continue

        seen_bvid.add(bvid)
        stats["入库"] += 1
        cleaned.append(
            {
                "meme": item["_meme"],
                "stat_date": day.strftime("%Y-%m-%d"),
                "bvid": bvid,
                "title": strip_html(item.get("title", "")),
                "author": item.get("author", ""),
                "author_mid": item.get("mid", ""),
                "typename": item.get("typename", ""),
                "tags": item.get("tag", ""),
                "publish_time": pub.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": parse_duration(item.get("duration")),
                "view": int(item.get("play") or 0),
                "danmaku": int(item.get("danmaku") or item.get("video_review") or 0),
                "reply": int(item.get("review") or 0),
                "favorite": int(item.get("favorites") or 0),
                "relevance_score": score,
                "matched_terms": "|".join(hits),
                "search_total": int(item.get("_num_results") or 0),
            }
        )

    return cleaned, dict(stats)


# --------------------------------------------------------------------------
# 3. 聚合层：视频级 -> 日粒度
# --------------------------------------------------------------------------

def aggregate(cleaned: list[dict]) -> list[dict]:
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in cleaned:
        buckets[(row["meme"], row["stat_date"])].append(row)

    daily: list[dict] = []
    for (meme, day), rows in sorted(buckets.items()):
        daily.append(
            {
                "meme": meme,
                "stat_date": day,
                "video_count": len(rows),
                "creator_count": len({r["author"] for r in rows}),
                "view": sum(r["view"] for r in rows),
                "interaction": sum(r["reply"] + r["danmaku"] for r in rows),
                "favorite": sum(r["favorite"] for r in rows),
                "search_total": max(r["search_total"] for r in rows),
                "observed": 1,
            }
        )
    return daily


# --------------------------------------------------------------------------
# 4. 输出
# --------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, raw_n: int, cleaned: list[dict], stats: dict, daily: list[dict]) -> None:
    lines = [
        "# 处理报告",
        "",
        f"- 原始记录：{raw_n} 条",
        f"- 清洗后入库：{len(cleaned)} 条",
        f"- 保留率：{len(cleaned) / raw_n:.1%}" if raw_n else "- 保留率：n/a",
        "",
        "## 各环节丢弃量",
        "",
        "| 环节 | 条数 |",
        "| --- | --- |",
    ]
    for key in ["区间外剔除", "缺 bvid 剔除", "重复剔除", "相关性不足剔除"]:
        lines.append(f"| {key} | {stats.get(key, 0)} |")

    lines += ["", "## 日粒度结果", "", "| 梗 | 日期 | 视频数 | 作者数 | 播放合计 | 互动合计 | 区间内总结果数 |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in daily:
        lines.append(
            f"| {row['meme']} | {row['stat_date']} | {row['video_count']} | "
            f"{row['creator_count']} | {row['view']:,} | {row['interaction']:,} | "
            f"{row['search_total']:,} |"
        )

    lines += [
        "",
        "## 口径提醒",
        "",
        "1. 「播放合计」= 该日发布的、通过相关性过滤的头部视频合计播放量，**不是**该梗全站绝对量。",
        "2. 跨日、跨梗比较用的是同一把尺子，所以形状和排序可信，绝对值不可外推。",
        "3. 搜索接口只给 `play / danmaku / review / favorites`；`like / coin` 要另调视频详情接口逐条补齐。",
        "4. `search_total` 是 B 站返回的当日结果总数，可作为「年龄中性」的活动量参考——",
        "   因为 `view` 是老日子多攒了几天播放，天生向今天下坡。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="现场重新采集而不是读快照")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    raw_dir = here / "raw"
    out_dir = here / "out"
    out_dir.mkdir(exist_ok=True)

    if args.live:
        print("== 现场采集（最小必要：每个梗 1 次请求）==")
        for kw, day in [("闪身步", "2026-09-25"), ("琵琶曲", "2026-09-25")]:
            payload = fetch_live(kw, day)
            data = payload.get("data") or {}
            if "v_voucher" in data:
                print(f"  {kw} {day}: 命中风控，跳过")
            else:
                fp = raw_dir / f"search_{kw}_{day.replace('-', '')}.json"
                fp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  {kw} {day}: numResults={data.get('numResults')} -> {fp.name}")
            time.sleep(2.5)

    print("\n== 1/4 采集：读原始返回体 ==")
    raw_rows = load_raw(raw_dir)
    print(f"   共 {len(raw_rows)} 条原始视频记录")

    print("\n== 2/4 清洗：剥标签 / 规范化 / 相关性过滤 / 去重 ==")
    cleaned, stats = clean(raw_rows)
    for k, v in stats.items():
        print(f"   {k}: {v}")

    print("\n== 3/4 聚合：视频级 -> 日粒度 ==")
    daily = aggregate(cleaned)
    print(f"   {len(daily)} 行日粒度数据")

    print("\n== 4/4 输出 ==")
    write_csv(out_dir / "videos_clean.csv", cleaned)
    write_csv(out_dir / "daily_stats.csv", daily)
    write_report(out_dir / "report.md", len(raw_rows), cleaned, stats, daily)
    for name in ["videos_clean.csv", "daily_stats.csv", "report.md"]:
        print(f"   out/{name}")

    print("\n完成。清洗后的前 3 条：")
    for row in cleaned[:3]:
        print(f"   [{row['meme']}] {row['title'][:34]} | 播放 {row['view']:,} | 相关 {row['relevance_score']}")


if __name__ == "__main__":
    main()
