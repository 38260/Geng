"""LLM 接口：连接自检 + 两个业务能力。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models import HotnessSnapshot, LifecycleSnapshot
from app.schemas.api import CatchUpAdviceRequest, TrendExplanationRequest
from app.services.llm import LLMError, list_models, load_config, test_connection
from app.services.llm.service import (
    generate_catch_up_advice,
    generate_trend_explanation,
    rule_based_trend,
)
from app.services.meme.query import _insight_data

from .deps import SessionDep

router = APIRouter(prefix="/api/llm", tags=["llm"])


def _payload_for(meme_id: int, session):
    from app.models import Meme

    meme = session.get(Meme, meme_id)
    if meme is None:
        raise HTTPException(status_code=404, detail="梗不存在")
    hotness = session.get(HotnessSnapshot, meme_id)
    lifecycle = session.get(LifecycleSnapshot, meme_id)
    if hotness is None or lifecycle is None:
        raise HTTPException(status_code=409, detail="该梗还没有指标快照")
    return _insight_data(meme, hotness, lifecycle), (meme.data_version or hotness.data_version)


@router.post("/test")
def llm_test():
    config = load_config()
    if not config.is_configured:
        return {
            "ok": False,
            "configured": False,
            "message": "未配置 LLM_API_KEY，AI 文案将使用算法兜底，其余功能不受影响",
            "config": config.masked(),
        }
    try:
        result = test_connection(config)
    except LLMError as exc:
        return {
            "ok": False,
            "configured": True,
            "message": str(exc),
            "kind": exc.kind,
            "config": config.masked(),
        }
    return {
        "ok": True,
        "configured": True,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "echo": result.text[:60],
        "message": "连接正常",
        "config": config.masked(),
    }


@router.get("/models")
def llm_models():
    config = load_config()
    if not config.is_configured:
        raise HTTPException(status_code=400, detail="未配置 LLM_API_KEY，无法获取模型列表")
    try:
        return {"models": list_models(config)}
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/trend-explanation")
def trend_explanation(body: TrendExplanationRequest, session: SessionDep):
    if body.meme_id is not None:
        data, version = _payload_for(body.meme_id, session)
        output = generate_trend_explanation(
            session, meme_id=body.meme_id, data=data, data_version=version,
            force_refresh=body.refresh,
        )
        session.commit()
        return output.to_dict()

    if not body.data:
        raise HTTPException(status_code=400, detail="需要 meme_id 或 data")
    text = rule_based_trend(body.data)
    return {
        "kind": "trend_explanation",
        "status": "ok",
        "source": "rule",
        "data_version": "adhoc",
        "text": text,
        "note": "直接传 data 时只走算法兜底，不调用 LLM",
    }


@router.post("/catch-up-advice")
def catch_up_advice(body: CatchUpAdviceRequest, session: SessionDep):
    if body.meme_id is None:
        raise HTTPException(status_code=400, detail="赶梗建议必须基于真实快照，请传 meme_id")
    data, version = _payload_for(body.meme_id, session)
    output = generate_catch_up_advice(
        session, meme_id=body.meme_id, data=data, data_version=version,
        force_refresh=body.refresh,
    )
    session.commit()
    return output.to_dict()


@router.get("/config")
def llm_config_view():
    return {"config": load_config().masked(), "allow_rule_fallback": settings.llm_allow_rule_based_fallback}
