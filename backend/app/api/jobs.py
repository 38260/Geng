"""任务接口：重算指标。

首页要求"数据预计算"，所以榜单/详情读的都是快照；
数据变化后由这个接口（或 CLI）重算，前端不需要等待计算过程。
"""

from __future__ import annotations

from fastapi import APIRouter

from fastapi import Query

from app.config import settings
from app.services.pipeline import collect_all, recompute_all

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/collect")
def collect(
    source: str = Query(settings.data_source, pattern="^(mock|bilibili)$"),
    limit: int | None = Query(None, ge=1, le=50, description="只采前 N 个梗"),
    meme_id: list[int] | None = Query(None, description="只采指定梗，可重复传"),
    window_days: int | None = Query(None, ge=7, le=90),
):
    """真实采集是慢操作（要逐条查 B 站），所以不进首页链路，只在这里显式触发。

    被风控挡住时返回 ok=false + 原因，并保留原有数据，不会伪造。
    """
    result = collect_all(source, meme_ids=meme_id or None, limit=limit, window_days=window_days)
    return result


@router.post("/recompute")
def recompute(window_days: int | None = None):
    result = recompute_all(window_days=window_days or settings.analysis_window_days)
    return {"ok": True, **result}
