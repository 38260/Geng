"""梗管理接口（本地运营入口）。

V1 不做登录体系，所以这些接口**没有鉴权**：写操作只影响展示与检索字段
（封面 / 介绍 / 别名 / 关键词），改不到热度、生命周期与赶梗结论。
真要部署到公网，必须先在这一层前面加访问控制。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.models import HotnessSnapshot, Meme, MemeStatus
from app.schemas.api import MemeCreate, MemeMetaUpdate
from app.services.meme import manage
from app.services.meme.query import covers_by_meme, thumbnail_for

from .deps import SessionDep

router = APIRouter(prefix="/api/manage", tags=["manage"])


def _get_or_404(session, meme_id: int) -> Meme:
    meme = session.get(Meme, meme_id)
    if meme is None:
        raise HTTPException(status_code=404, detail="梗不存在")
    return meme


@router.get("/memes")
def list_for_manage(
    session: SessionDep,
    search: str = Query("", max_length=60),
    status: str = Query("all", description="all | certified | candidate"),
):
    """管理列表：正式梗与候选梗都要能进来改介绍和封面。"""
    if status not in {"all", MemeStatus.CERTIFIED, MemeStatus.CANDIDATE}:
        raise HTTPException(status_code=400, detail="status 只支持 all | certified | candidate")

    rows = list(session.scalars(select(Meme).order_by(Meme.name)))
    if status != "all":
        rows = [meme for meme in rows if meme.status == status]
    needle = search.strip().lower()
    if needle:
        rows = [
            meme
            for meme in rows
            if needle in meme.name.lower()
            or any(needle in alias.lower() for alias in (meme.aliases or []))
            or any(needle in keyword.lower() for keyword in (meme.keywords or []))
        ]

    covers = covers_by_meme(session)
    items = []
    for meme in rows:
        hotness = session.get(HotnessSnapshot, meme.id)
        items.append(
            {
                "id": meme.id,
                "name": meme.name,
                "description": meme.description or "",
                "status": meme.status,
                "certified": bool(meme.certified),
                "data_source": meme.data_source or "mock",
                "verification_state": meme.verification_state or "unverified",
                "hotness": round(hotness.score, 1) if hotness else None,
                "has_manual_cover": bool((meme.cover_url or "").strip()),
                "thumbnail": thumbnail_for(meme, covers.get(meme.id, "")),
            }
        )
    return {
        "total": len(items),
        "managed_count": sum(1 for item in items if item["has_manual_cover"]),
        "certified_count": sum(1 for meme in rows if meme.certified),
        "candidate_count": sum(1 for meme in rows if not meme.certified),
        "items": items,
    }


@router.post("/memes", status_code=201)
def create_meme(body: MemeCreate, session: SessionDep):
    """站内自发跑起来的梗（两位 UP 没做过的）也要能进库被度量。"""
    return manage.create_meme(session, body.model_dump())


@router.get("/memes/{meme_id}")
def read_meme(meme_id: int, session: SessionDep):
    return manage.meme_view(session, _get_or_404(session, meme_id))


@router.patch("/memes/{meme_id}")
def write_meme(meme_id: int, body: MemeMetaUpdate, session: SessionDep):
    payload = body.model_dump(exclude_unset=True)
    return manage.update_meta(session, _get_or_404(session, meme_id), payload)
