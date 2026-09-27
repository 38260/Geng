"""赶梗潮 API 入口。

启动即完成：建表 → 空库自动灌演示数据 → 预计算热度/生命周期。
这样 `uvicorn app.main:app` 之后前端立刻能拿到完整榜单。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api import api_router
from app.config import configure_logging, get_logger, settings
from app.models import Meme, SessionLocal, init_db

log = get_logger(__name__)

VERSION = "1.0.0"


def ensure_seed() -> None:
    """空库时自动灌一次演示数据，并把指标算好（仅 mock 模式）。"""
    session = SessionLocal()
    try:
        existing = session.scalar(select(Meme.id).limit(1))
        if existing is not None:
            return
        log.info("检测到空库，自动写入演示数据并计算指标…")
    finally:
        session.close()

    from app.scripts.seed_data import seed
    from app.services.pipeline import recompute_all

    summary = seed(days=settings.analysis_window_days, do_reset=False)
    result = recompute_all(window_days=settings.analysis_window_days)
    log.info("自动初始化完成：梗 %s 个 / 指标 %s 个", summary["certified"], result["computed"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    try:
        ensure_seed()
    except Exception:  # noqa: BLE001 - 初始化失败不应该让服务起不来
        log.exception("自动初始化失败，请手动执行 python -m app.scripts.seed_data")
    log.info(
        "%s %s 已就绪 | 数据源=%s | LLM=%s",
        settings.app_name, VERSION, settings.data_source,
        "已配置" if settings.llm_configured else "未配置(降级为算法文案)",
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        description="B 站网络梗热度与生命周期分析 —— 数据负责证明，算法负责判断，LongCat 负责解释。",
        version=VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """任何未处理异常都返回结构化错误，绝不让前端拿到半截 JSON。"""
        log.exception("接口异常 %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": "服务器内部错误，请稍后重试"},
        )

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "app": settings.app_name,
            "tagline": "今天，赶什么梗？",
            "version": VERSION,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
