"""路由汇总。"""

from fastapi import APIRouter

from . import jobs, llm, manage, memes, meta, settings as settings_api

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(memes.router)
api_router.include_router(llm.router)
api_router.include_router(settings_api.router)
api_router.include_router(jobs.router)
api_router.include_router(manage.router)

__all__ = ["api_router"]
