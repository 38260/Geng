"""给已有字幕的梗生成「AI 浓缩版介绍」，逐字校验通过才入库。

这是字幕三层路的最后一步：抓字幕（fetch_transcripts）→ 规则选段（详情页直接给）→
让模型把选段缩短。缩短不是重写——模型只能整句照抄字幕里的句子，系统逐句核对，
有一处对不上就整段丢弃，页面继续用未缩短的规则摘录（详情接口只读缓存，不现调模型）。

    python -m app.scripts.condense_intros                     # 所有有字幕的梗
    python -m app.scripts.condense_intros --ids 47 12         # 点名几个
    python -m app.scripts.condense_intros --limit 5           # 先试 5 个
    python -m app.scripts.condense_intros --force             # 已缓存的重跑（要烧额度）
    python -m app.scripts.condense_intros --dry-run           # 只报会处理谁，不调模型

字幕没重抓过时缓存命中，不再打模型；所以每日刷新后面跟着跑一次是安全的。
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import Any

from sqlalchemy import select

from app.config import get_logger, settings
from app.models import Meme, SessionLocal, VideoTranscript
from app.models.base import ensure_schema
from app.services.llm.config import load_config
from app.services.meme.intro import transcript_block
from app.services.meme.query import meme_transcripts
from app.services.meme.summary import (
    MAX_SUMMARY_CHARS,
    digest,
    generate_intro_summary,
    read_cached_summary,
)

log = get_logger("condense_intros")


def pick_for_meme(session, meme: Meme) -> tuple[VideoTranscript | None, str]:
    """挑详情页真正会展示的那条字幕：用同一个 transcript_block 规则，避免缩错了视频。"""
    rows = meme_transcripts(session, meme)
    block = transcript_block(meme, meme.certifications, rows)
    if block is None:
        return None, "字幕里没有一句在讲这个梗"
    row = next((item for item in rows if item.bvid == block["bvid"]), None)
    if row is None:
        return None, "选中的字幕查不到行"
    return row, ""


def condense_all(
    session,
    *,
    ids: list[int] | None = None,
    limit: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    budget: int = MAX_SUMMARY_CHARS,
    config=None,
    log_line=lambda *args: None,
) -> dict[str, Any]:
    """跑一轮浓缩，返回可以直接写进刷新报告的计数。

    ``log_line`` 让调用方（每日刷新）能决定每行去哪，脚本自己用 logger。
    """
    stats: Counter[str] = Counter()
    memes = list(session.scalars(select(Meme).order_by(Meme.id)))
    if ids:
        memes = [meme for meme in memes if meme.id in ids]
    if limit:
        memes = memes[:limit]

    todo: list[tuple[Meme, VideoTranscript]] = []
    for meme in memes:
        row, _reason = pick_for_meme(session, meme)
        if row is None:
            stats["no_usable_transcript"] += 1
            continue
        todo.append((meme, row))

    result: dict[str, Any] = {
        "scanned": len(memes),
        "targets": len(todo),
        "ok": 0,
        "cached": 0,
        "rejected": 0,
        "error": 0,
        "no_usable_transcript": stats["no_usable_transcript"],
        "skipped": bool(dry_run),
    }
    if dry_run:
        result["planned_calls"] = len(todo)
        return result

    config = config or load_config()
    for index, (meme, row) in enumerate(todo, start=1):
        version = digest(row.bvid, row.text)
        if not force and read_cached_summary(session, meme_id=meme.id, version=version):
            stats["cached"] += 1
            log_line("info", f"[{index}/{len(todo)}] [{meme.name}] 缓存命中，跳过")
            continue
        try:
            summary = generate_intro_summary(
                session,
                meme_id=meme.id,
                bvid=row.bvid,
                text=row.text,
                meme_name=meme.name,
                config=config,
                force_refresh=force,
                budget=budget,
            )
        except Exception as exc:  # noqa: BLE001 - 单条失败不影响整轮
            session.rollback()
            stats["error"] += 1
            log_line("warning", f"[{index}/{len(todo)}] [{meme.name}] 异常：{exc}")
            continue
        if summary is None:
            stats["rejected"] += 1
            log_line("warning", f"[{index}/{len(todo)}] [{meme.name}] 未通过逐字校验，页面继续用规则摘录")
            continue
        stats["ok"] += 1
        log_line(
            "info",
            f"[{index}/{len(todo)}] [{meme.name}] 浓缩 {summary['chars']} 字 / "
            f"{len(summary['sentences'])} 句（{summary['model']}）",
        )

    result.update({key: stats[key] for key in ("ok", "cached", "rejected", "error")})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成梗介绍的 AI 浓缩版（逐字校验）")
    parser.add_argument("--ids", type=int, nargs="*", default=None, help="只处理这些梗 id")
    parser.add_argument("--limit", type=int, default=None, help="最多处理几个梗")
    parser.add_argument("--force", action="store_true", help="忽略缓存重跑")
    parser.add_argument("--dry-run", action="store_true", help="不调模型，只报清单")
    parser.add_argument("--budget", type=int, default=MAX_SUMMARY_CHARS, help="浓缩后字数上限")
    args = parser.parse_args(argv)

    ensure_schema()
    config = load_config()
    if not config.is_configured and not args.dry_run:
        print("没配 LLM_API_KEY，浓缩这一步没有意义（规则摘录已经在页面上了）。先去系统设置配 key。")
        return 2

    session = SessionLocal()
    try:
        def emit(level: str, message: str) -> None:
            getattr(log, level)(message)

        result = condense_all(
            session,
            ids=args.ids,
            limit=args.limit,
            force=args.force,
            dry_run=args.dry_run,
            budget=args.budget,
            config=config,
            log_line=emit,
        )
        print(
            f"库里 {result['scanned']} 个梗，有可用字幕的 {result['targets']} 个"
            f"（{result['no_usable_transcript']} 个字幕里没一句在讲这个梗）"
        )
        if args.dry_run:
            print(f"预计 {result['planned_calls']} 次模型调用，每条约 {config.timeout:.0f}s 超时上限")
            return 0
        print("")
        print(
            f"成功 {result['ok']}，缓存命中 {result['cached']}，逐字校验不过 {result['rejected']}，"
            f"异常 {result['error']}"
        )
        if result["rejected"]:
            print(
                "校验不过是预期行为：模型改写了句子就该退回原文摘录，"
                "详情页第②档仍在，只是没缩短。"
            )
        if settings.data_source != "bilibili":
            print("提醒：当前 DATA_SOURCE 不是 bilibili，详情页展示的仍是演示数据。")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
