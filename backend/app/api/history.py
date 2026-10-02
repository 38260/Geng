"""梗史馆接口：近 N 天入池的梗 + 历史周期画像。

只读、公开，和 `/api/meta`、`GET /api/memes*` 同一组：小程序端将来要复用
不必带 `X-Admin-Token`，也不在里面暴露任何凭据。

与既有两条读侧口径的关系：

* `/api/memes`（scope=board）——今天玩什么（过气与残值不进）；
* `/api/memes`（scope=all）——完整梗库（当前态）；
* **`/api/history`——复盘：把一个梗怎么走到今天摊开**（逐日热度 + 阶段轨迹 + 周期画像）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import LIFECYCLE_STAGES, settings
from app.services.meme.history import (
    CYCLE_LABELS,
    HISTORY_DAYS,
    SORTS,
    history_payload,
)

from .deps import SessionDep

router = APIRouter(prefix="/api/history", tags=["history"])

CERT_SCOPES = {"", "double", "single"}


@router.get("")
def list_history(
    session: SessionDep,
    days: int = Query(HISTORY_DAYS, ge=7, le=365, description="入池窗口：这段里有真实解说证据就算"),
    window: int = Query(0, ge=0, le=365, description="观测窗天数；0 = 用满库里已有的逐日序列"),
    cycle: str = Query("", description="周期类型：rising | pulse | long_tail | no_data"),
    stage: str = Query("", description="当前生命周期阶段"),
    cert: str = Query("", description="double = 只看双 UP 认证；single = 只看单 UP"),
    sort: str = Query("recent", description="recent | peak | hotness | off_peak | name"),
):
    # 参数写错一律 400，不静默返回空列表——静默返回空会被读成
    # "这个筛选下确实没有梗"，而真相是参数拼错了。
    if cycle and cycle not in CYCLE_LABELS:
        raise HTTPException(status_code=400, detail=f"未知周期类型：{cycle}")
    if stage and stage not in LIFECYCLE_STAGES:
        raise HTTPException(status_code=400, detail=f"未知阶段：{stage}")
    if cert not in CERT_SCOPES:
        raise HTTPException(status_code=400, detail=f"未知认证口径：{cert}")
    if sort not in SORTS:
        raise HTTPException(status_code=400, detail=f"未知排序：{sort}")

    payload = history_payload(
        session,
        days=days,
        window_days=window or None,
        cycle=cycle,
        stage=stage,
        cert=cert,
        sort=sort,
    )
    return {
        **payload,
        "data_source": settings.data_source,
        "is_demo": settings.data_source == "mock",
    }
