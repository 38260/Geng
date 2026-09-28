"""刷新服务：手动触发 + 每天定点自动跑。

真正的流程（发现 → 采集 → 重算 → 写报告）在 :mod:`app.scripts.daily_refresh`，
这里只负责三件事：

1. **同一个进程内只允许一个刷新在跑**：``threading.Lock`` + 脚本自己的文件锁
   双保险，手动按钮和定时任务撞上了后到的那个直接拿 409；
2. **状态可查**：``GET /api/jobs/refresh`` 与 ``/api/meta`` 都要能说出
   "上次什么时候刷的、谁触发的、结果如何、统计截至哪天"；
3. **定时**：``REFRESH_AT=00:05`` 才开，默认关——不默认往用户机器上塞后台任务。

线程而不是进程：uvicorn 重启会丢调度，所以生产上更稳的做法是系统计划任务；
这里的定时器是给"本机自己跑着"的场景准备的，两条路共用同一把文件锁，不会打架。
"""

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from typing import Any

from app.config import get_logger, settings
from app.scripts import daily_refresh

log = get_logger(__name__)

_lock = threading.Lock()
_state: dict[str, Any] = {"running": False, "last_error": ""}


def schedule_info() -> dict[str, Any]:
    at = (settings.refresh_at or "").strip()
    return {
        "enabled": bool(at) and settings.data_source == "bilibili",
        "at": at,
        "full_weekday": settings.refresh_full_weekday,
        "discovery": settings.refresh_discovery,
        "weekday_names": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    }


def last_report() -> dict[str, Any] | None:
    """上一次刷新的报告；没有就返回 None，接口据此说"还没自动刷过"。"""
    if not daily_refresh.STATE_FILE.exists():
        return None
    try:
        return json.loads(daily_refresh.STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("读 last_refresh.json 失败：%s", exc)
        return None


def status() -> dict[str, Any]:
    return {
        "running": _state["running"] or daily_refresh.LOCK_FILE.exists(),
        "trigger": _state.get("trigger", ""),
        "started_at": _state.get("started_at", ""),
        "last": last_report(),
        "schedule": schedule_info(),
        "data_source": settings.data_source,
    }


def run_now(*, full: bool = False, trigger: str = "手动") -> dict[str, Any]:
    """后台起一次刷新。已经在跑就返回 ok=False，让界面显示"正在刷新"而不是排队。"""
    if settings.data_source != "bilibili":
        return {
            "ok": False,
            "reason": f"当前数据源是 {settings.data_source}，刷新只针对真实 B 站数据；"
                      f"演示模式请用 seed_data 重新生成。",
        }
    if not _lock.acquire(blocking=False):
        return {"ok": False, "reason": "已经有一次刷新在跑，等它结束再试。", "running": True}

    _state.update(running=True, trigger=trigger, started_at=datetime.now().isoformat(timespec="seconds"),
                  last_error="")

    def worker() -> None:
        argv = ["--trigger", trigger]
        if full:
            argv.append("--full")
        if not settings.refresh_discovery:
            argv.append("--skip-discovery")
        try:
            code = daily_refresh.main(argv)
            if code == 3:
                _state["last_error"] = "另一个刷新进程占着锁，本次没跑"
            elif code >= 1:
                _state["last_error"] = f"刷新部分失败（退出码 {code}），详见运行报告"
        except Exception as exc:  # noqa: BLE001 - 后台线程抛出来没人接，必须自己记
            log.exception("刷新线程异常")
            _state["last_error"] = f"{type(exc).__name__}: {exc}"[:200]
        finally:
            _state["running"] = False
            _lock.release()

    threading.Thread(target=worker, name="gengchao-refresh", daemon=True).start()
    return {"ok": True, "trigger": trigger, "mode": "full" if full else "incremental"}


def _next_run(at: str, now: datetime | None = None) -> datetime | None:
    """下一个 ``HH:MM`` 的时刻。时间格式不对就返回 None（调度器会退出并告警）。"""
    try:
        hour, minute = (int(part) for part in at.split(":"))
    except ValueError:
        return None
    base = (now or datetime.now()).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base if base > (now or datetime.now()) else base + timedelta(days=1)


def data_lag_days() -> int | None:
    """统计截至日距今几天；库里没数据返回 None。

    真实模式下只看 B 站来源的序列——演示数据是按"今天"生成的，
    混进来会把滞后算小，该补跑的那次就不补了。
    """
    from datetime import date

    from sqlalchemy import func, select

    from app.models import MemeDailyStats, SessionLocal

    with SessionLocal() as session:
        stmt = select(func.max(MemeDailyStats.stat_date)).where(MemeDailyStats.video_count > 0)
        if settings.data_source == "bilibili":
            stmt = stmt.where(MemeDailyStats.data_source == "bilibili")
        through = session.scalar(stmt)
    return (date.today() - through).days if through else None


def catch_up_on_start() -> dict[str, object]:
    """开机补跑：00:00 那一刻机器多半没开，错过就得等到第二天，数据一直旧着。

    只在已经启用定时刷新（REFRESH_AT 非空）时才动——没开定时说明用户想手动控制。
    """
    if not schedule_info()["enabled"] or not settings.refresh_on_start:
        return {"ok": False, "skipped": "未启用定时刷新或已关掉启动补跑"}
    lag = data_lag_days()
    if lag is None:
        return run_now(full=True, trigger="首次建库")
    if lag <= 1:
        return {"ok": False, "skipped": f"数据只滞后 {lag} 天，不用补"}
    log.info("启动补跑：统计截至已滞后 %s 天", lag)
    return run_now(full=False, trigger="补跑")


def scheduler_loop(stop: threading.Event) -> None:
    """到点跑一次增量；每周 ``REFRESH_FULL_WEEKDAY`` 那天改跑全窗口做校准。"""
    at = (settings.refresh_at or "").strip()
    if not at or settings.data_source != "bilibili":
        return
    while not stop.is_set():
        nxt = _next_run(at)
        if nxt is None:
            log.warning("REFRESH_AT=%s 不是 HH:MM，自动刷新未启动", at)
            return
        log.info("下次自动刷新：%s", nxt.isoformat(timespec="minutes"))
        # 分段睡：改配置或进程退出时不用等满一天
        while not stop.is_set() and datetime.now() < nxt:
            stop.wait(30)
        if stop.is_set():
            return
        full = settings.refresh_full_weekday >= 0 and date.today().weekday() == settings.refresh_full_weekday
        log.info("自动刷新开始（%s）", "全窗口校准" if full else "增量补 T-1")
        run_now(full=full, trigger="定时")
        # 一轮跑完再等过这个时间点，避免同一分钟内重复触发
        stop.wait(120)
