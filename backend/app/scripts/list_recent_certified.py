"""发现层清单：最近这段时间，两位 UP 主（**并集**）介绍过的梗。

    python -m app.scripts.list_recent_certified                 # 报告窗口 30 天
    python -m app.scripts.list_recent_certified --days 14 --pages 10
    python -m app.scripts.list_recent_certified --ingest         # 并集入池 + 采集 + 重算

三个概念分开，混一次就会漏梗：

1. **认证窗口**（``--cert-days``，默认 90 天滚动）：某位 UP 主"介绍过没有"看这么远。
   解说视频往往比梗的爆发期早 1~2 周，用它当报告窗口没问题，但当准入窗口就会
   把还在热的梗整条排除——之前漏掉「老叟戏顽童」就是把两个窗口当成了同一个。
2. **报告窗口**（``--days``，默认 30 天）：这份清单/这轮选题覆盖哪段时间。
3. **准入规则（并集）**：任一 UP 主在认证窗口内真实介绍过 → 入池。
   梗百科是主来源（日更、覆盖广），梗指南补充；两位都做过的叫「双 UP 认证」，
   是可信度标签，不再是准入门槛。标题写法不同但显然是同一个梗的（如
   「胆子肥嘟嘟的」/「胆子真是肥嘟嘟的」）会合并成一条并把两种写法都记成别名，
   合并动作逐条打日志，方便人工抽查。

输出：终端表格 + docs/data/recent-certified.md + backend/data/recent_certified.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from app.collectors.bilibili import BiliClient
from app.config import PROJECT_DIR, get_logger, settings
from app.services.meme.certification import ENCYCLOPEDIA, GUIDE, UpAuthor
from app.services.meme.discovery import (
    UpVideo,
    extract_meme_name,
    fetch_up_index,
    index_by_meme,
    merge_pool,
)
from app.services.meme.manage import _unique_slug

log = get_logger("list-certified")


def _window(videos: list[UpVideo], days: int) -> list[UpVideo]:
    floor = datetime.now() - timedelta(days=days)
    return [video for video in videos if video.pubdate and video.pubdate >= floor]


def _pull(client: BiliClient, author: UpAuthor, pages: int, gap: float, *, not_before=None) -> tuple[list[UpVideo], int, int]:
    videos, pages_ok, blocked = fetch_up_index(
        client, author, max_pages=pages, gap=gap, not_before=not_before
    )
    log.info(
        "%s：拉到 %s 条投稿（%s 页成功 / %s 次被风控），最早一条 %s",
        author.name, len(videos), pages_ok, blocked,
        min((v.pubdate for v in videos if v.pubdate), default=datetime.min).strftime("%Y-%m-%d"),
    )
    return videos, pages_ok, blocked


def _pull_with_retry(author: UpAuthor, pages: int, gap: float, *, not_before=None):
    """空间投稿接口按会话风控，连打几次就被 -352；换一个匿名指纹重试成功率高得多。"""
    videos: list[UpVideo] = []
    pages_ok = blocked = 0
    error = ""
    for attempt in range(4):
        try:
            got, ok, bad = _pull(BiliClient(), author, pages, gap, not_before=not_before)
            pages_ok, blocked = max(pages_ok, ok), blocked + bad
            if got:
                return got, pages_ok, blocked, ""
            error = "拿到 0 条投稿"
        except Exception as exc:  # noqa: BLE001 - 单个 UP 失败要如实报告，不能假装成功
            error = str(exc)[:120]
            log.warning("%s 第 %s 次取投稿失败：%s", author.name, attempt + 1, error)
            time.sleep(3.0 * (attempt + 1))
    return videos, pages_ok, blocked, error


def build(client: BiliClient, *, days: int, cert_days: int, pages: int, gap: float) -> dict:
    raw: dict[str, list[UpVideo]] = {}
    stats: dict[str, dict] = {}
    cert_floor = datetime.now() - timedelta(days=cert_days)   # 认证窗口（更宽）
    for author in (ENCYCLOPEDIA, GUIDE):
        videos, pages_ok, blocked, error = _pull_with_retry(
            author, pages, gap, not_before=cert_floor
        )
        raw[author.name] = videos
        recent = _window(videos, cert_days)
        raw[author.name + "_recent"] = recent
        raw[author.name + "_reported"] = _window(videos, days)
        stats[author.name] = {
            "fetched": len(videos),
            "pages_ok": pages_ok,
            "blocked": blocked,
            "in_window": len(recent),
            "named": len(index_by_meme(recent)),
        }
        if not videos:
            stats[author.name]["error"] = error
            log.error("%s 投稿取不到：%s", author.name, error or "未知原因")
        log.info("%s：拉到 %s 条投稿，认证窗口内 %s 条 / 报告窗口内 %s 条",
                 author.name, len(videos), len(recent), len(raw[author.name + "_reported"]))

    enc = index_by_meme(raw[ENCYCLOPEDIA.name + "_recent"])
    gui = index_by_meme(raw[GUIDE.name + "_recent"])
    enc_rep = index_by_meme(raw[ENCYCLOPEDIA.name + "_reported"])
    gui_rep = index_by_meme(raw[GUIDE.name + "_reported"])

    pool, merged = merge_pool(enc, gui)

    def flatten(index: dict[str, UpVideo]) -> list[dict]:
        return sorted(
            (
                {
                    "meme": video.title.strip(),
                    "name": key,
                    "date": video.pubdate.strftime("%Y-%m-%d"),
                    "play": video.play,
                    "bvid": video.bvid,
                }
                for key, video in index.items()
            ),
            key=lambda item: item["date"],
            reverse=True,
        )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rule": "并集准入：任一 UP 主在认证窗口内介绍过即入池；双 UP 只是标签",
        "recent": {ENCYCLOPEDIA.name: flatten(enc_rep), GUIDE.name: flatten(gui_rep)},
        "days": days,
        "cert_days": cert_days,
        "reported_only": sorted(set(enc_rep) & set(gui_rep)),
        "since": (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
        "stats": stats,
        "pool": [
            {
                "name": entry.key,
                "certified_by": entry.certified_by,
                "cert_label": entry.cert_label,
                "encyclopedia": _evidence(entry.encyclopedia),
                "guide": _evidence(entry.guide),
            }
            for entry in pool
        ],
        "merged_writings": [{"keep": keep, "absorbed": gone} for keep, gone in merged],
        "certified": [
            {
                "meme": entry.encyclopedia.title if entry.encyclopedia else entry.key,
                "name": entry.key,
                "encyclopedia": entry.encyclopedia.__dict__
                | {"pubdate": entry.encyclopedia.pubdate.isoformat(timespec="minutes")},
                "guide": entry.guide.__dict__
                | {"pubdate": entry.guide.pubdate.isoformat(timespec="minutes")},
            }
            for entry in pool
            if entry.both and entry.encyclopedia and entry.guide
        ],
        "only_encyclopedia": [entry.key for entry in pool if entry.encyclopedia and not entry.guide],
        "only_guide": [entry.key for entry in pool if entry.guide and not entry.encyclopedia],
        # 只在内存里用（写 JSON 前会 pop 掉）：入库时要的是原始 UpVideo 对象
        "_pool": pool,
    }


def _evidence(video: UpVideo | None) -> dict | None:
    if video is None:
        return None
    return {
        "bvid": video.bvid,
        "title": video.title,
        "pubdate": video.pubdate.isoformat(timespec="minutes"),
        "play": video.play,
    }


def ingest(session, report: dict) -> list[int]:
    """把并集候选池真实入库：证据就是 UP 主的真实投稿（真 BV、真日期、真发布时间）。

    名字取抽取出来的梗名（不是整条标题），别名带上各位 UP 的写法，
    这样后续搜索与相关性判定都认得它。认证状态由 ``recompute_certification``
    按证据算：两位都有 → verified_both，只有一位 → partially_verified。
    """
    from sqlalchemy import func as sa_func

    from app.models import Meme, MemeStatus
    from app.services.meme.certification import record_certification

    ids: list[int] = []
    for entry in report.get("_pool", []):
        name = entry.key.strip()[:20]
        meme = session.query(Meme).filter(sa_func.lower(Meme.name) == name.lower()).one_or_none()
        if meme is None:
            meme = Meme(
                name=name,
                slug=_unique_slug(session, name),
                status=MemeStatus.CANDIDATE,
                certified=False,
                verification_state="unverified",
                data_source="",
                keywords=[name],
            )
            session.add(meme)
            session.flush()
            log.info("新建梗「%s」（%s）", name, entry.cert_label)
        aliases = list(meme.aliases or [])
        for video in (entry.encyclopedia, entry.guide):
            if video is None:
                continue
            for candidate in (extract_meme_name(video.title), video.title):
                cleaned = (candidate or "").replace("【梗百科】", "").replace("【梗指南】", "").strip()
                if cleaned and cleaned.lower() != name.lower() and cleaned not in aliases:
                    aliases.append(cleaned[:20])
        meme.aliases = aliases[:12]

        for role, video in (("encyclopedia", entry.encyclopedia), ("guide", entry.guide)):
            if video is None:
                continue
            record_certification(
                session, meme, role, bvid=video.bvid, video_title=video.title[:200],
                published_at=video.pubdate, data_source="bilibili",
            )
        # 证据就是从 UP 主的空间投稿列表里直接读到的，这就是在线核验本身
        log.info("入池「%s」：%s（%s）", meme.name, entry.cert_label, "/".join(
            video.bvid for video in (entry.encyclopedia, entry.guide) if video
        ))
        ids.append(meme.id)
    session.commit()
    return ids


def to_markdown(report: dict) -> str:
    enc_stats, gui_stats = report["stats"][ENCYCLOPEDIA.name], report["stats"][GUIDE.name]
    pool = report["pool"]
    lines = [
        f"# 最近 {report['days']} 天入选梗库的梗（发现层并集）",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 准入规则：{report['rule']}",
        f"- 报告窗口：{report['since']} 起（{report['days']} 天）；"
        f"**认证窗口 {report['cert_days']} 天滚动**——解说视频通常比梗的爆发期早 1~2 周",
        f"- 入池 {len(pool)} 个：双 UP 认证 {len(report['certified'])} 个 / "
        f"仅梗百科 {len(report['only_encyclopedia'])} 个 / 仅梗指南 {len(report['only_guide'])} 个",
        f"- 报告窗口内两位都做过：{len(report['reported_only'])} 个："
        + ("、".join(report["reported_only"]) or "无"),
        f"- 梗百科：拉取 {enc_stats['fetched']} 条投稿，"
        f"{enc_stats['in_window']} 条在认证窗口内，识别出 {enc_stats['named']} 个梗名",
        f"- 梗指南：拉取 {gui_stats['fetched']} 条投稿，"
        f"{gui_stats['in_window']} 条在认证窗口内，识别出 {gui_stats['named']} 个梗名",
        f"- 被风控页：梗百科 {enc_stats['blocked']} 次 / 梗指南 {gui_stats['blocked']} 次",
        "",
        "## 候选池（按主来源排序：梗百科在前，再补梗指南独有的）",
        "",
        "| 梗名 | 认证 | 梗百科 | 梗指南 |",
        "| --- | --- | --- | --- |",
    ]
    if not pool:
        lines.append("| （空）| | | |")
    for item in pool:
        enc, gui = item["encyclopedia"], item["guide"]
        lines.append(
            f"| {item['name']} | {item['cert_label']} | "
            f"{_cell(enc)} | {_cell(gui)} |"
        )
    lines.append("")

    if report["merged_writings"]:
        lines += [
            f"## 写法合并（{len(report['merged_writings'])} 组：同一梗、两位 UP 标题写法不同）",
            "",
            "| 保留的名字 | 并进去的写法 |",
            "| --- | --- |",
        ]
        lines += [
            f"| {m['keep']} | {m['absorbed']} |" for m in report["merged_writings"]
        ]
        lines.append("")

    for author in (ENCYCLOPEDIA.name, GUIDE.name):
        rows = report["recent"][author]
        lines += [f"## {author}：最近 {report['days']} 天介绍的梗（{len(rows)} 个）", "",
                  "| 梗名（取自标题） | 发布 | 播放 | BV |", "| --- | --- | --- | --- |"]
        lines += [f"| {r['meme'][:40]} | {r['date']} | {r['play']:,} | [{r['bvid']}]"
                  f"(https://www.bilibili.com/video/{r['bvid']}) |" for r in rows]
        lines.append("")

    if any(report["stats"][author].get("error") for author in (ENCYCLOPEDIA.name, GUIDE.name)):
        lines += [
            "## 缺口（如实记录）",
            "",
            *[
                f"- {author}：{report['stats'][author]['error']}"
                for author in (ENCYCLOPEDIA.name, GUIDE.name)
                if report["stats"][author].get("error")
            ],
            "",
            "单边取不到不影响另一边的梗入池（准入是并集），但这一轮池子会相应偏窄。",
            "",
        ]
    return "\n".join(lines)


def _cell(evidence: dict | None) -> str:
    if not evidence:
        return "—"
    return (
        f"{evidence['pubdate'][:10]}，{evidence['play']:,} 播放，"
        f"[{evidence['bvid']}](https://www.bilibili.com/video/{evidence['bvid']})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 发现层并集清单")
    parser.add_argument("--days", type=int, default=30, help="报告窗口：列这段时间内的选题")
    parser.add_argument(
        "--cert-days",
        type=int,
        default=settings.cert_window_days,
        help=f"认证窗口：任一 UP 主介绍过没有，看这么远（默认 {settings.cert_window_days}）",
    )
    parser.add_argument("--ingest", action="store_true", help="把并集候选池入库（带真实证据）并采集计算")
    parser.add_argument("--pages", type=int, default=8, help="每位 UP 翻几页（每页 50 条）")
    parser.add_argument("--gap", type=float, default=1.2)
    args = parser.parse_args(argv)

    client = BiliClient()
    ok, reason = client.probe()
    print(f"接口探测：{'可用' if ok else '不可用'} — {reason}")
    if not ok:
        return 2

    report = build(client, days=args.days, cert_days=args.cert_days, pages=args.pages, gap=args.gap)
    pool = report.pop("_pool", [])

    out_json = Path("data") / "recent_certified.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = to_markdown(report)
    md_path = PROJECT_DIR / "docs" / "data" / "recent-certified.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")

    print(md)
    print(f"已写出：{out_json} 与 {md_path}")

    if args.ingest:
        from app.models import SessionLocal
        from app.services.pipeline import collect_all, recompute_all

        report["_pool"] = pool
        session = SessionLocal()
        try:
            ids = ingest(session, report)
        finally:
            session.close()
        print(f"入库 {len(ids)} 个梗，开始逐日采集真实序列…")
        result = collect_all("bilibili", meme_ids=ids or None, window_days=args.days)
        print("采集：", {k: v for k, v in result.items() if isinstance(v, int)})
        print("重算：", recompute_all(window_days=args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
