"""给梗库批量打主题标签（LLM 在固定清单里挑，挑不中归「其他」）。

    python -m app.scripts.tag_memes                    # 只标还没标过的
    python -m app.scripts.tag_memes --ids 47 12        # 点名几个
    python -m app.scripts.tag_memes --limit 5          # 先试 5 个
    python -m app.scripts.tag_memes --force            # 全部重标（要烧额度）
    python -m app.scripts.tag_memes --dry-run          # 只报会处理谁，不调模型

打标结果按「输入摘要」缓存：梗的介绍或引用视频没变就不会重复调模型，
所以跟在每日刷新后面跑是安全的。

标签只存 key 数组，展示文案在 app/config/taxonomy.py——改文案不用重标。
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from sqlalchemy import select

from app.config import TAG_LABELS, get_logger
from app.models import HotnessSnapshot, Meme, SessionLocal
from app.models.base import ensure_schema
from app.services.llm.config import load_config
from app.services.meme.tagging import tag_meme

log = get_logger("tag_memes")

_LogLine = Callable[[str, str], None]


def run_tagging(
    session,
    *,
    ids: list[int] | None = None,
    limit: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    config=None,
    log_line: _LogLine = lambda *args: None,
) -> dict[str, Any]:
    """跑一轮打标，返回可直接写进报告/打印的计数。

    ``log_line`` 让调用方（每日刷新）决定每行去哪，脚本自己用 logger。
    """
    memes = list(session.scalars(select(Meme).order_by(Meme.id)))
    if ids:
        wanted = set(ids)
        memes = [meme for meme in memes if meme.id in wanted]
    # 有指标快照的梗（= 梗库里真正会展示的那些）排在最前面。
    # 否则 --limit N 会全花在库里另一批「有演示数据、但页面上根本看不到」的梗身上——
    # 打完发现筛选行还是空的，因为打的和展示的不是同一批。实测踩过。
    with_snapshot = {row[0] for row in session.execute(select(HotnessSnapshot.meme_id))}
    memes.sort(key=lambda meme: (0 if meme.id in with_snapshot else 1, meme.id))
    if limit:
        memes = memes[: int(limit)]

    # 默认只补没标过的：已有标签的梗不该被无意义地重打一遍
    todo = memes if force else [meme for meme in memes if not (meme.tags or [])]

    result: dict[str, Any] = {
        "scanned": len(memes),
        "targets": len(todo),
        "ok": 0,
        "cached": 0,
        "failed": 0,
        "by_tag": {},
        "failures": [],
        "skipped": bool(dry_run),
    }
    if dry_run:
        result["planned_calls"] = len(todo)
        return result

    config = config or load_config()
    for index, meme in enumerate(todo, start=1):
        try:
            outcome = tag_meme(session, meme, config=config, force=force)
        except Exception as exc:  # noqa: BLE001 - 单条失败不该中断整轮
            session.rollback()
            result["failed"] += 1
            result["failures"].append({"id": meme.id, "name": meme.name, "reason": str(exc)})
            log_line("warning", f"[{index}/{len(todo)}] [{meme.name}] 异常：{exc}")
            continue

        if not outcome["ok"]:
            result["failed"] += 1
            result["failures"].append(
                {"id": meme.id, "name": meme.name, "reason": outcome["reason"]}
            )
            log_line("warning", f"[{index}/{len(todo)}] [{meme.name}] 打标失败：{outcome['reason']}")
            continue

        result["ok"] += 1
        if outcome["skipped"] == "cached":
            result["cached"] += 1
        for tag in outcome["tags"]:
            result["by_tag"][tag] = int(result["by_tag"].get(tag, 0)) + 1
        labels = " / ".join(TAG_LABELS.get(tag, tag) for tag in outcome["tags"])
        note = "（缓存）" if outcome["skipped"] == "cached" else ""
        log_line("info", f"[{index}/{len(todo)}] [{meme.name}] → {labels}{note}")

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="批量给梗打主题标签（LLM 打标）")
    parser.add_argument("--ids", type=int, nargs="*", default=None, help="只处理这些梗 id")
    parser.add_argument("--limit", type=int, default=None, help="最多处理几个梗")
    parser.add_argument("--force", action="store_true", help="忽略已有标签与缓存，全部重标")
    parser.add_argument("--dry-run", action="store_true", help="不调模型，只报会处理谁")
    args = parser.parse_args(argv)

    # 新列（tags / tags_source / tags_updated_at）靠这一步补进老库
    added = ensure_schema()
    if added:
        print(f"已补齐数据库列：{', '.join(added)}")

    config = load_config()
    if not config.is_configured and not args.dry_run:
        print("没配 LLM_API_KEY，打标需要用模型判断主题。先去系统设置配 key，或改回人工标签方案。")
        return 2

    session = SessionLocal()
    try:
        def emit(level: str, message: str) -> None:
            getattr(log, level)(message)

        result = run_tagging(
            session,
            ids=args.ids,
            limit=args.limit,
            force=args.force,
            dry_run=args.dry_run,
            config=config,
            log_line=emit,
        )
        print(f"库里 {result['scanned']} 个梗，本轮待打标 {result['targets']} 个")
        if args.dry_run:
            print(f"预计 {result['planned_calls']} 次模型调用（每条几十 token）")
            return 0
        print("")
        print(f"成功 {result['ok']}（其中缓存命中 {result['cached']}），失败 {result['failed']}")
        if result["by_tag"]:
            print("标签分布：")
            for key, count in sorted(result["by_tag"].items(), key=lambda item: -item[1]):
                print(f"  {TAG_LABELS.get(key, key):<14} {count}")
        if result["failures"]:
            print("失败明细（这些梗保持「未标」，下次重跑会补）：")
            for item in result["failures"][:10]:
                print(f"  #{item['id']} {item['name']}：{item['reason']}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
