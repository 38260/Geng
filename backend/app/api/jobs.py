"""任务接口：重算指标。

首页要求"数据预计算"，所以榜单/详情读的都是快照；
数据变化后由这个接口（或 CLI）重算，前端不需要等待计算过程。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.services.pipeline import recompute_all

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/recompute")
def recompute(window_days: int | None = None):
    result = recompute_all(window_days=window_days or settings.analysis_window_days)
    return {"ok": True, **result}
