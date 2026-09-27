"""系统设置接口（LLM 配置）。

API Key 只写不读：GET 永远返回掩码，PUT 时留空表示保持原值。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.schemas.api import LLMSettingsUpdate
from app.services.llm.config import load_config
from app.services.settings_store import update_env_file

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/llm")
def get_llm_settings():
    config = load_config()
    return {
        "config": config.masked(),
        "data_source": settings.data_source,
        "environment": settings.environment,
        "version": settings.app_version,
        "allow_rule_fallback": settings.llm_allow_rule_based_fallback,
        "env_file": "backend/.env",
    }


@router.put("/llm")
def update_llm_settings(body: LLMSettingsUpdate):
    updates = {
        "LLM_PROVIDER": body.provider,
        "LLM_BASE_URL": body.base_url,
        "LLM_MODEL": body.model,
        "LLM_TEMPERATURE": str(body.temperature),
        "LLM_MAX_TOKENS": str(body.max_tokens),
    }
    if body.api_key:  # 空字符串 = 保持原 Key 不变
        updates["LLM_API_KEY"] = body.api_key

    settings.llm_provider = body.provider
    settings.llm_base_url = body.base_url
    settings.llm_model = body.model
    settings.llm_temperature = body.temperature
    settings.llm_max_tokens = body.max_tokens
    if body.api_key:
        settings.llm_api_key = body.api_key

    written = update_env_file(updates) if body.persist else []
    return {
        "saved": True,
        "persisted": bool(written),
        "written_keys": [key for key in written if key != "LLM_API_KEY"],
        "api_key_updated": bool(body.api_key),
        "config": load_config().masked(),
    }
