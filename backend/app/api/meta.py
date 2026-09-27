"""健康检查与元信息（数据来源、更新时间、透明度）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.services.meme.query import meta_payload

from .deps import SessionDep

router = APIRouter(tags=["meta"])


@router.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "data_source": settings.data_source,
        "llm_configured": settings.llm_configured,
    }


@router.get("/api/meta")
def meta(session: SessionDep):
    return meta_payload(session)
