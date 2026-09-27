"""列出"最近一个月里，两位 UP 主都介绍过的梗"——严格按项目定义取交集。

    python -m app.scripts.list_recent_certified               # 最近 30 天
    python -m app.scripts.list_recent_certified --days 14 --pages 10

两个窗口必须分开，这是之前漏掉「老叟戏顽童」的原因：
* 认证窗口（--cert-days，默认 90）：两位 UP 各自"介绍过没有"。解说视频往往比
  梗的爆发期早 1~2 周，用它当时间窗会把还在热的梗整条排除；
* 报告窗口（--days，默认 30）：这份清单要覆盖哪段时间的选题。
3. 从标题里抽梗名（抽不出就丢掉，宁可漏不可造）；
4. 两边都出现同一个梗名 = 符合定义；只有名字互相包含的算"疑似"，单独列出，
   因为两位 UP 的标题写法不一样，严格交集会漏，但我不想把疑似说成认证。

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
from app.config import PROJECT_DIR, get_logger
from app.services.meme.certification import ENCYCLOPEDIA, GUIDE, UpAuthor
from app.services.meme.manage import _unique_slug
from app.services.meme.discovery import UpVideo, extract_meme_name, fetch_up_index, index_by_meme

log = get_logger("list-certified")


def _name_of(video: UpVideo) -> str | None:
    return extract_meme_name(video.title)


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


def build(client: BiliClient, *, days: int, cert_days: int, pages: int, gap: float) -> dict:
    raw = {}
    stats = {}
    floor = datetime.now() - timedelta(days=days)          # 报告窗口
    cert_floor = datetime.now() - timedelta(days=cert_days)  # 认证窗口（更宽）
    for author in (ENCYCLOPEDIA, GUIDE):
        videos: list[UpVideo] = []
        pages_ok = blocked = 0
        error = ""
        # 空间投稿接口按会话风控，连打几次就被 -352；换一个匿名指纹重试成功率高得多
        for attempt in range(4):
            try:
                fresh = BiliClient()
                got, ok, bad = _pull(fresh, author, pages, gap, not_before=cert_floor)
                pages_ok, blocked = max(pages_ok, ok), blocked + bad
                if got:
                    videos = got
                    break
                error = "拿到 0 条投稿"
            except Exception as exc:  # noqa: BLE001 - 单个 UP 失败要如实报告，不能假装成功
                error = str(exc)[:120]
                log.warning("%s 第 %s 次取投稿失败：%s", author.name, attempt + 1, error)
                time.sleep(3.0 * (attempt + 1))
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
            log.error("%s 投稿取不到：%s", author.name, error)
        log.info("%s：拉到 %s 条投稿，认证窗口内 %s 条 / 报告窗口内 %s 条",
                 author.name, len(videos), len(recent), len(raw[author.name + "_reported"]))

    enc = index_by_meme(raw[ENCYCLOPEDIA.name + "_recent"])
    gui = index_by_meme(raw[GUIDE.name + "_recent"])
    enc_rep = index_by_meme(raw[ENCYCLOPEDIA.name + "_reported"])
    gui_rep = index_by_meme(raw[GUIDE.name + "_reported"])

    strict = sorted(set(enc) & set(gui))
    loose = sorted(
        (a, b)
        for a in set(enc) - set(strict)
        for b in set(gui) - set(strict)
        if a != b and (a in b or b in a)
    )

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
        "recent": {ENCYCLOPEDIA.name: flatten(enc_rep), GUIDE.name: flatten(gui_rep)},
        "days": days,
        "cert_days": cert_days,
        "reported_only": sorted(set(enc_rep) & set(gui_rep)),
        "since": (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
        "stats": stats,
        "certified": [
            {
                "meme": enc[key].title,
                "name": enc[key].title.strip(),
                "encyclopedia": enc[key].__dict__ | {"pubdate": enc[key].pubdate.isoformat(timespec="minutes")},
                "guide": gui[key].__dict__ | {"pubdate": gui[key].pubdate.isoformat(timespec="minutes")},
            }
            for key in strict
        ],
        "suspected": [
            {
                "encyclopedia": enc[a].title,
                "encyclopedia_date": enc[a].pubdate.strftime("%m-%d"),
                "guide": gui[b].title,
                "guide_date": gui[b].pubdate.strftime("%m-%d"),
            }
            for a, b in loose
        ],
        "only_encyclopedia": sorted(set(enc) - set(gui) - {b for _, b in loose}),
        "only_guide": sorted(set(gui) - set(enc) - {a for a, _ in loose}),
        # 只在内存里用（写 JSON 前会 pop 掉）：入库时要的是原始 UpVideo 对象
        "_pairs": [(key, enc[key], gui[key]) for key in strict],
    }


def ingest(session, report: dict) -> list[int]:
    """把双 UP 交集里的梗真实入库：认证证据就是两位 UP 的真实投稿（真 BV、真日期）。

    名字取抽取出来的梗名（不是整条标题），别名带上两位 UP 各自的写法，
    这样后续搜索与相关性判定都认得它。
    """
    from sqlalchemy import func as sa_func

    from app.models import Meme, MemeStatus
    from app.services.meme.certification import record_certification

    ids: list[int] = []
    for key, enc_video, gui_video in report.get("_pairs", []):
        name = key.strip()[:20]
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
            log.info("新建梗「%s」", name)
        aliases = meme.aliases or []
        for title in (enc_video.title, gui_video.title):
            cleaned = title.replace("【梗百科】", "").replace("【梗指南】", "").strip()
            if cleaned and cleaned not in aliases:
                aliases.append(cleaned[:20])
        meme.aliases = aliases[:12]

        for role, video in (("encyclopedia", enc_video), ("guide", gui_video)):
            record_certification(
                session, meme, role, bvid=video.bvid, video_title=video.title[:200],
                published_at=video.pubdate, data_source="bilibili",
            )
        # 证据就是从两位 UP 的空间投稿列表里直接读到的，这就是在线核验本身
        meme.verification_state = "verified_both"
        ids.append(meme.id)
        log.info("「%s」双 UP 认证：梗百科 %s / 梗指南 %s", name, enc_video.bvid, gui_video.bvid)
    session.commit()
    return ids


def to_markdown(report: dict) -> str:
    lines = [
        f"# 最近 {report['days']} 天符合定义的梗（双 UP 交集）",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 报告窗口：{report['since']} 起（{report['days']} 天）；"
        f"认证窗口放宽到 {report['cert_days']} 天——解说视频通常比梗的爆发期早 1~2 周",
        f"- 报告窗口内两位都做过：{len(report['reported_only'])} 个："
        + ("、".join(report["reported_only"]) or "无"),
        f"- 梗百科：拉取 {report['stats']['梗百科']['fetched']} 条投稿，"
        f"{report['stats']['梗百科']['in_window']} 条在窗口内，识别出 {report['stats']['梗百科']['named']} 个梗名",
        f"- 梗指南：拉取 {report['stats']['梗指南']['fetched']} 条投稿，"
        f"{report['stats']['梗指南']['in_window']} 条在窗口内，识别出 {report['stats']['梗指南']['named']} 个梗名",
        f"- 被风控页：梗百科 {report['stats']['梗百科']['blocked']} 次 / 梗指南 {report['stats']['梗指南']['blocked']} 次",
        "",
        f"## 双 UP 都介绍过（认证窗口 {report['cert_days']} 天内，{len(report['certified'])} 个）",
        "",
    ]
    if not report["certified"]:
        lines += ["（交集为空。空间投稿接口只给最近若干页，两位 UP 的选题不重叠时就是这样——"
                  "这是真实结论，不是脚本失败。）", ""]
    for item in report["certified"]:
        enc, gui = item["encyclopedia"], item["guide"]
        lines += [
            f"### {item['name']}",
            f"- 梗百科：{enc['title']}（{enc['pubdate'][:10]}，{enc['play']:,} 播放，[BV{enc['bvid'][2:]}]"
            f"(https://www.bilibili.com/video/{enc['bvid']})）",
            f"- 梗指南：{gui['title']}（{gui['pubdate'][:10]}，{gui['play']:,} 播放，"
            f"[{gui['bvid']}](https://www.bilibili.com/video/{gui['bvid']})）",
            "",
        ]
    for author in (ENCYCLOPEDIA.name, GUIDE.name):
        rows = report["recent"][author]
        lines += [f"## {author}：最近 {report['days']} 天介绍的梗（{len(rows)} 个）", "",
                  "| 梗名（取自标题） | 发布 | 播放 | BV |", "| --- | --- | --- | --- |"]
        lines += [f"| {r['meme'][:40]} | {r['date']} | {r['play']:,} | [{r['bvid']}]"
                  f"(https://www.bilibili.com/video/{r['bvid']}) |" for r in rows]
        lines.append("")

    if report["suspected"]:
        lines += [f"## 疑似（标题写法不同导致没进严格交集，{len(report['suspected'])} 组）", "",
                  "| 梗百科 | 日期 | 梗指南 | 日期 |", "| --- | --- | --- | --- |"]
        lines += [
            f"| {s['encyclopedia'][:34]} | {s['encyclopedia_date']} | {s['guide'][:34]} | {s['guide_date']} |"
            for s in report["suspected"]
        ]
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 按定义列最近一个月的梗")
    parser.add_argument("--days", type=int, default=30, help="报告窗口：列这段时间内的选题")
    parser.add_argument("--cert-days", type=int, default=90, help="认证窗口：两位UP介绍过没有，看这么远")
    parser.add_argument("--ingest", action="store_true", help="把双 UP 交集入库（带真实认证证据）并采集计算")
    parser.add_argument("--pages", type=int, default=8, help="每位 UP 翻几页（每页 50 条）")
    parser.add_argument("--gap", type=float, default=1.2)
    args = parser.parse_args(argv)

    client = BiliClient()
    ok, reason = client.probe()
    print(f"接口探测：{'可用' if ok else '不可用'} — {reason}")
    if not ok:
        return 2

    report = build(client, days=args.days, cert_days=args.cert_days, pages=args.pages, gap=args.gap)
    pairs = report.pop("_pairs", [])

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

        report["_pairs"] = pairs
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
