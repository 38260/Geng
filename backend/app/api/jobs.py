"""任务接口：重算指标。

首页要求"数据预计算"，所以榜单/详情读的都是快照；
数据变化后由这个接口（或 CLI）重算，前端不需要等待计算过程。
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.config import settings
from app.services import refresh as refresh_service
from app.services.pipeline import collect_all, recompute_all

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/collect")
def collect(
    source: str = Query(settings.data_source, pattern="^(mock|bilibili)$"),
    limit: int | None = Query(None, ge=1, le=50, description="只采前 N 个梗"),
    offset: int | None = Query(None, ge=0, description="先跳过前 N 个梗（分批时用）"),
    meme_id: list[int] | None = Query(None, description="只采指定梗，可重复传"),
    window_days: int | None = Query(None, ge=7, le=90),
    scope: str = Query("real", pattern="^(real|all|library|board)$",
                       description="real=跳过纯演示梗（默认）| all | library | board"),
):
    """真实采集是慢操作（要逐条查 B 站），所以不进首页链路，只在这里显式触发。

    被风控挡住时返回 ok=false + 原因，并保留原有数据，不会伪造。
    """
    result = collect_all(
        source, meme_ids=meme_id or None, limit=limit, offset=offset,
        window_days=window_days, scope=scope,
    )
    return result


@router.post("/refresh")
def refresh(full: bool = Query(False, description="true=重采整个报告窗口；默认只补昨天")):
    """手动触发一次刷新（发现新梗 + 刷新老梗 + 重算），后台跑、立刻返回。

    慢操作不占请求：前端拿 202 之后轮询 ``GET /api/jobs/refresh``。
    已经在跑就 409，不排队——两次刷新同时打 B 站只会一起被风控。
    """
    result = refresh_service.run_now(full=full, trigger="手动")
    return JSONResponse(result, status_code=202 if result["ok"] else 409)


@router.get("/refresh")
def refresh_status():
    """刷新状态：在不在跑、上次什么时候跑的、结果如何、定时配置。"""
    return refresh_service.status()


@router.post("/recompute")
def recompute(window_days: int | None = None):
    result = recompute_all(window_days=window_days or settings.analysis_window_days)
    return {"ok": True, **result}
