"""梗榜 / 梗详情接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import HOME_FILTER_LABELS, settings
from app.schemas.api import RefreshRequest
from app.services.meme import query as q
from app.services.meme.certification import ENCYCLOPEDIA, GUIDE, admitted

from .deps import SessionDep

router = APIRouter(prefix="/api/memes", tags=["memes"])

SORTS = {"hotness", "growth", "discussion", "name"}


def _require_certified(meme_id: int, session):
    """读侧闸门 = 发现层准入：任一 UP 主介绍过就能看；两位都没做过的不给指标页。"""
    meme = q.get_meme_or_none(session, meme_id)
    if meme is None:
        raise HTTPException(status_code=404, detail="梗不存在")
    if not admitted(meme):
        raise HTTPException(
            status_code=409,
            detail=(
                f"梗「{meme.name}」还没有任何一位梗解释 UP 主（{ENCYCLOPEDIA.name} / {GUIDE.name}）"
                f"介绍过，未通过发现层准入，不进入榜单"
            ),
        )
    return meme


@router.get("")
def list_memes(
    session: SessionDep,
    filter: str = Query("all", description="all | hot | taking_off | receding"),
    search: str = Query("", max_length=60),
    sort: str = Query("hotness"),
    limit: int | None = Query(None, ge=1, le=100),
    offset: int = Query(0, ge=0),
    scope: str = Query("board", description="board=热榜（过气与死梗不进）| all=完整梗库"),
    ids: str = Query("", max_length=600, description="只取这些 id，逗号分隔；给本机收藏列表用"),
):
    if filter not in HOME_FILTER_LABELS:
        raise HTTPException(status_code=400, detail=f"未知筛选：{filter}")
    if sort not in SORTS:
        raise HTTPException(status_code=400, detail=f"未知排序：{sort}")
    if scope not in {"board", "all"}:
        raise HTTPException(status_code=400, detail="scope 只支持 board | all")

    payload = q.list_memes(
        session, filter_key=filter, search=search, sort=sort, limit=limit,
        offset=offset, scope=scope, ids=q.parse_ids(ids),
    )
    return {
        **payload,
        "data_source": settings.data_source,
        "is_demo": settings.data_source == "mock",
        "window_days": settings.analysis_window_days,
    }


@router.get("/{meme_id}")
def meme_detail(meme_id: int, session: SessionDep):
    meme = _require_certified(meme_id, session)
    payload = q.detail_payload(session, meme)
    if payload is None:
        raise HTTPException(status_code=409, detail="该梗还没有可用的指标数据，请先执行采集与计算")
    return payload


@router.get("/{meme_id}/trend")
def meme_trend(
    meme_id: int,
    session: SessionDep,
    window: int = Query(settings.analysis_window_days, description="7 | 30"),
):
    _require_certified(meme_id, session)
    if window not in (7, 30, settings.analysis_window_days):
        raise HTTPException(status_code=400, detail="window 只支持 7 或 30 天")
    return q.trend_payload(session, meme_id, window)


@router.get("/{meme_id}/videos")
def meme_videos(
    meme_id: int,
    session: SessionDep,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    sort: str = Query("rank", pattern="^(rank|view)$"),
):
    """相关视频（已过相关性筛），支持翻页与两种排法。

    ``sort=rank`` 是 B 站搜这个梗的默认（综合）顺序，``sort=view`` 是播放量。
    库里一条名次都没抓到时，``sort_applied`` 会如实退回 ``view`` 并在 note 里说明。
    """
    meme = _require_certified(meme_id, session)
    return q.video_page(session, meme, limit=limit, offset=offset, sort=sort)


@router.post("/{meme_id}/insight")
def meme_insight(meme_id: int, session: SessionDep, body: RefreshRequest):
    """重新判断：AI 失败后前端点这个按钮重试。"""
    meme = _require_certified(meme_id, session)
    hotness = _require_snapshots(meme_id, session)
    payload = q.insights_payload(session, meme, *hotness, refresh=body.refresh)
    session.commit()
    return payload


def _require_snapshots(meme_id: int, session):
    from app.models import HotnessSnapshot, LifecycleSnapshot

    hotness = session.get(HotnessSnapshot, meme_id)
    lifecycle = session.get(LifecycleSnapshot, meme_id)
    if hotness is None or lifecycle is None:
        raise HTTPException(status_code=409, detail="该梗还没有指标快照")
    return hotness, lifecycle
