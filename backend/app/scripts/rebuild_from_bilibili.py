"""用真实 B 站数据重建整个产品数据集。

    python -m app.scripts.rebuild_from_bilibili                # 核验 + 全量采集
    python -m app.scripts.rebuild_from_bilibili --pages 6      # 认证索引多翻几页
    python -m app.scripts.rebuild_from_bilibili --skip-collect # 只跑在线核验

做三件事，且只做能真实做到的：
1. 拉两位 UP 主的真实投稿建索引 → 逐个梗做双 UP 在线核验，验到才写真实 bvid；
2. 对库内每个梗做定向搜索 + 逐条补齐指标，**替换**掉演示数据；
3. 重算热度 / 生命周期 / 赶梗判断。

窗口内搜不到相关视频的梗会被清空（不保留演示值），报告里如实列出。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from app.collectors.bilibili import BiliClient
from app.config import BACKEND_DIR, get_logger, settings
from app.models import Meme, SessionLocal, ensure_schema
from app.services.meme.certification import analysis_allowed
from app.services.meme.verification import apply_outcome, load_or_build_index, verify_meme
from app.services.pipeline import collect_all, recompute_all

log = get_logger("rebuild")


def verify_all(client: BiliClient, *, pages: int, gap: float, refresh_index: bool) -> dict:
    indexes, note = load_or_build_index(client, max_pages=pages, gap=gap, refresh=refresh_index)
    log.info("核验索引：%s", note)

    session = SessionLocal()
    report = {"index_note": note, "counts": {}, "verified_both": [], "unverified": []}
    try:
        memes = list(session.query(Meme).filter(Meme.status == "certified").order_by(Meme.id))
        for meme in memes:
            outcome = verify_meme(meme, indexes)
            apply_outcome(session, meme, outcome)
            report["counts"][outcome.state] = report["counts"].get(outcome.state, 0) + 1
            if outcome.both_verified:
                report["verified_both"].append(meme.name)
            else:
                report["unverified"].append(meme.name)
            if meme.name in report["verified_both"]:
                enc = outcome.roles["encyclopedia"]
                gui = outcome.roles["guide"]
                log.info("双UP核验通过：%s（百科 %s / 指南 %s）", meme.name, enc.bvid, gui.bvid)
        session.commit()
    finally:
        session.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 用真实 B 站数据重建")
    parser.add_argument("--pages", type=int, default=4, help="每位 UP 投稿索引翻几页")
    parser.add_argument("--gap", type=float, default=1.4, help="请求间隔秒数（防风控）")
    parser.add_argument("--days", type=int, default=settings.analysis_window_days)
    parser.add_argument("--limit", type=int, default=None, help="只采前 N 个梗")
    parser.add_argument("--refresh-index", action="store_true", help="忽略索引缓存重新拉")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--skip-collect", action="store_true")
    args = parser.parse_args(argv)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    ensure_schema()

    client = BiliClient(cookie=settings.bili_cookie, timeout=settings.bili_timeout)
    if not client.bootstrap_fingerprint() and not settings.bili_cookie:
        log.warning("拿不到设备指纹也没配 BILI_COOKIE，接口大概率会被风控")

    result: dict[str, object] = {"started_at": datetime.now().isoformat()}

    if not args.skip_verify:
        result["verification"] = verify_all(
            client, pages=args.pages, gap=args.gap, refresh_index=args.refresh_index
        )
        log.info("核验结果：%s", result["verification"]["counts"])

    if not args.skip_collect:
        collected = collect_all(
            "bilibili", limit=args.limit, window_days=args.days, purge_when_empty=True
        )
        result["collection"] = collected
        log.info("采集结果：%s", collected)
        if collected.get("aborted"):
            # 熔断之后这一轮不是"完整重建"：库里只有一半梗拿到新数据。
            # 重算照做（纯本地计算、不再打接口），但必须把"这是半轮"写在报告和终端上，
            # 否则人会拿着一份残缺窗口去读指标。
            result["partial_rebuild"] = True
            log.error("采集中止：%s", collected.get("abort_reason"))
            log.error("这一轮是**半轮重建**，指标只反映已经采到的那部分；"
                      "按提示换小号 Cookie 或把间隔调大后重跑。")

    result["recompute"] = recompute_all(window_days=args.days)
    log.info("指标重算：%s", result["recompute"])

    session = SessionLocal()
    try:
        with_data = [
            meme.name
            for meme in session.query(Meme).filter(Meme.status == "certified")
            if analysis_allowed(meme) and meme.data_source == "bilibili"
        ]
        result["memes_with_real_data"] = len(with_data)
    finally:
        session.close()

    out = BACKEND_DIR / "data" / "rebuild_report.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    verification = result.get("verification") or {}
    print("\n================ 重建结果 ================")
    print(f"认证在线核验：{verification.get('counts', {}) if verification else '跳过'}")
    if verification:
        print(f"  双 UP 通过：{len(verification.get('verified_both', []))} 个"
              f" → {', '.join(verification.get('verified_both', [])[:12]) or '（无）'}")
    collection = result.get("collection") or {}
    if collection:
        print(f"真实采集：成功 {collection.get('collected')} 个梗 / "
              f"窗口内无结果 {collection.get('empty')} 个 / 被拒 {collection.get('failed')} 个 / "
              f"剔除无关视频 {collection.get('dropped')} 条")
    print(f"写入真实视频的梗：{result.get('memes_with_real_data')} 个")
    print(f"指标重算：{result.get('recompute')}")
    print(f"报告：{out}")
    if result.get("partial_rebuild"):
        print("⚠ 本轮为**半轮重建**：" + str(collection.get("abort_reason", "采集中途被硬风控中止"))
              + " 指标只覆盖已采到的部分，建议调慢间隔或换小号 Cookie 后重跑。")
        return 4   # 4 = 硬风控熔断（与 collect_data / daily_refresh 同义）
    return 0


if __name__ == "__main__":
    sys.exit(main())
