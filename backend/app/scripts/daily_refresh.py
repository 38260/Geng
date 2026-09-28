"""每日刷新：发现新梗 + 刷新老梗数据 + 重算指标，并留一份可审计的运行报告。

    python -m app.scripts.daily_refresh              # 增量：只补昨天那一天
    python -m app.scripts.daily_refresh --full       # 全窗口：重看 30 天（建议每周一次）
    python -m app.scripts.daily_refresh --skip-discovery

为什么默认只补 T-1：B 站搜索接口对同一个词两次返回的头部 20 条差别可以很大，
每天把 30 天全重采一遍 = 75 个梗 × 30 次请求 ≈ 两千多次，纯烧风控额度；
而"昨天"这个窗口只需要每个梗一次请求。老日子的播放量会随时间涨，
所以留一个 ``--full`` 做周校准——同日只保留更好的一次观测，不会越跑越薄。

跑完写两份东西：
* ``docs/data/refresh-report.md``   人看的运行报告（跟着仓库走，便于回溯哪天翻车了）
* ``backend/data/last_refresh.json`` 接口读的：上次刷新时间/来源/结果/统计截至日

退出码：0 正常；1 部分失败（有梗被拒或一个没采到）；2 数据源不可用；3 已有刷新在跑。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.config import PROJECT_DIR, settings
from app.models import MemeDailyStats, SessionLocal
from app.services.pipeline import collect_all, recompute_all

BACKEND_DIR = Path(__file__).resolve().parents[2]
LOCK_FILE = BACKEND_DIR / "data" / ".refresh.lock"
STATE_FILE = BACKEND_DIR / "data" / "last_refresh.json"
REPORT_FILE = PROJECT_DIR / "docs" / "data" / "refresh-report.md"
LOCK_STALE_SECONDS = 3 * 3600     # 超过 3 小时的锁视为上次崩了没清，可以抢


def _data_through(session) -> date | None:
    return session.scalar(select(MemeDailyStats.stat_date).order_by(MemeDailyStats.stat_date.desc()))


def acquire_lock(source: str) -> bool:
    """单实例：定时任务和手动按钮可能同时触发，撞车会把同一批请求打两遍。"""
    if LOCK_FILE.exists():
        try:
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age < LOCK_STALE_SECONDS:
                return False
        except OSError:
            return False
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(f"{os.getpid()} {source} {datetime.now().isoformat()}", encoding="utf-8")
    return True


def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def run_discovery(*, pages: int, gap: float) -> dict:
    """发现层：把两位 UP 主最近 ``cert_window_days`` 天介绍过的梗并进候选池。

    这一步最容易被风控（UP 主投稿列表接口是重灾区），失败就记下来继续采集，
    不能因为"没发现到新梗"把老梗的更新也一起废掉。
    """
    from app.collectors.bilibili import get_client
    from app.scripts.list_recent_certified import build, ingest

    session = SessionLocal()
    try:
        report = build(
            get_client(),
            days=settings.analysis_window_days,
            cert_days=settings.cert_window_days,
            pages=pages,
            gap=gap,
        )
        ids = ingest(session, report)
        session.commit()
        pool = report.get("_pool") or report.get("pool") or []
        return {
            "ok": True,
            "pool_size": len(pool),
            "ingested": len(ids),
            "new_titles": sorted({str(item.get("name")) for item in report.get("merged_writings", [])})[:20],
        }
    except Exception as exc:  # noqa: BLE001 - 发现失败不该拖垮刷新
        session.rollback()
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    finally:
        session.close()


def write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(state: dict) -> None:
    """报告跟着仓库走，方便回看"哪天刷新翻车了、当时是什么数"。只留最近 20 次。"""
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    collect = state["collect"]
    discovery = state["discovery"]
    discovery_line = (
        f"候选池 {discovery.get('pool_size')} 个，入库 {discovery.get('ingested')} 个"
        if discovery.get("ok")
        else f"失败（已跳过，不影响老梗更新）：{discovery.get('error')}"
    )
    NL = chr(10)          # 用 chr(10) 拼，免得转义在工具链里被吃掉
    block = NL.join([
        f"## {state['started_at']} · {state['trigger']} · {state['mode']}",
        "",
        f"- 耗时 {state['seconds']} 秒，退出码 {state['exit_code']}，统计截至 "
        f"{state['data_through'] or '未知'}（滞后 {state['data_lag_days']} 天）",
        f"- 采集（scope={state['scope']}）：目标 {collect.get('targets')} / 成功 {collect.get('collected')}"
        f" / 空窗 {collect.get('empty')} / 被拒 {collect.get('failed')}"
        f" / 跳过纯演示 {collect.get('skipped_demo', 0)}",
        f"- 同日沿用更好观测 {collect.get('kept_better_days', 0)} 天；本次更薄的梗 {collect.get('thinned', 0)} 个",
        f"- 指标重算 {state['recompute'].get('computed')} 个梗（跳过 {state['recompute'].get('skipped')}）",
        f"- 发现层：{discovery_line}",
        f"- 范围说明：{collect.get('scope_note', '—')}；探测：{collect.get('reason', '—')}",
        "",
    ])
    head = (
        "# 刷新运行报告" + NL + NL
        + "最近 20 次运行，新的在上。由 `python -m app.scripts.daily_refresh` 写入。" + NL + NL
    )
    divider = NL + "---" + NL + NL
    history = ""
    if REPORT_FILE.exists():
        old = REPORT_FILE.read_text(encoding="utf-8")
        start = old.find(NL + "## ")
        history = old[start + 1:] if start >= 0 else ""
    body = head + block + (divider + history if history else "")
    # 只留 20 段，避免文件无限长
    parts = body.split(divider)
    REPORT_FILE.write_text(divider.join(parts[:20]) + NL, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="赶梗潮 · 每日刷新（发现新梗 + 刷新老梗 + 重算）")
    parser.add_argument("--full", action="store_true", help="重采整个报告窗口（默认只补昨天）")
    parser.add_argument("--skip-discovery", action="store_true", help="不跑发现层，只刷新已有梗")
    parser.add_argument("--trigger", default="手动", help="写进报告的触发方式：手动 / 定时")
    parser.add_argument("--pages", type=int, default=4, help="发现层每位 UP 翻几页")
    parser.add_argument("--gap", type=float, default=1.2, help="发现层翻页间隔秒")
    parser.add_argument("--scope", choices=["real", "all", "library", "board"], default="real")
    args = parser.parse_args(argv)

    if settings.data_source != "bilibili":
        print(f"当前数据源是 {settings.data_source}，刷新只针对真实 B 站数据；"
              f"演示模式请跑 python -m app.scripts.seed_data。")
        return 2

    if not acquire_lock(args.trigger):
        print("已有一个刷新在跑（backend/data/.refresh.lock），本次退出。")
        return 3

    started = datetime.now()
    window = settings.analysis_window_days if args.full else 1
    discovery = {"ok": True, "skipped": True, "pool_size": 0, "ingested": 0, "new_titles": []}
    exit_code = 0
    try:
        if not args.skip_discovery:
            print("· 发现层：翻两位 UP 主的近期投稿…")
            discovery = run_discovery(pages=args.pages, gap=args.gap)
            if discovery.get("ok"):
                print(f"  → 候选池 {discovery.get('pool_size')} 个，入库 {discovery.get('ingested')} 个")
            else:
                print(f"  → 失败：{discovery.get('error')}（继续刷新已有梗）")

        print(f"· 采集：scope={args.scope} 窗口={window} 天（{'全窗口重采' if args.full else '只补 T-1'}）…")
        collected = collect_all(
            "bilibili", window_days=window, scope=args.scope, purge_when_empty=False,
        )
        print(f"  → 目标 {collected.get('targets')}，成功 {collected['collected']}，"
              f"空窗 {collected['empty']}，被拒 {collected['failed']}，"
              f"跳过演示 {collected.get('skipped_demo', 0)}")

        print("· 重算指标（热度 / 生命周期 / 赶梗判断）…")
        recomputed = recompute_all(window_days=settings.analysis_window_days)
        print(f"  → 算了 {recomputed['computed']} 个梗，跳过 {recomputed['skipped']} 个")

        if not collected["ok"]:
            exit_code = 2
        elif collected["failed"] or collected["collected"] == 0:
            exit_code = 1

        session = SessionLocal()
        try:
            through = _data_through(session)
        finally:
            session.close()

        state = {
            "started_at": started.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "seconds": round((datetime.now() - started).total_seconds(), 1),
            "trigger": args.trigger,
            "mode": "full" if args.full else "incremental",
            "scope": args.scope,
            "exit_code": exit_code,
            "discovery": discovery,
            "collect": {
                key: collected.get(key)
                for key in (
                    "ok", "reason", "source", "targets", "collected", "empty", "failed",
                    "videos", "skipped", "dropped", "kept_snapshots", "thinned",
                    "kept_better_days", "skipped_demo", "scope", "scope_note",
                )
            },
            "recompute": recomputed,
            "data_through": through.isoformat() if through else None,
            "data_lag_days": (date.today() - through).days if through else None,
        }
        write_state(state)
        write_markdown(state)
        print(f"报告：{REPORT_FILE}")
        return exit_code
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
