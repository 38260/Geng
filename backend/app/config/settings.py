"""Application settings.

Everything that a user may want to change lives in ``.env`` (see ``.env.example``).
Secrets (``LLM_API_KEY``, ``BILI_COOKIE``) are never hard-coded and never logged.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------ application ------------------------------ #
    app_name: str = "赶梗潮"
    app_version: str = "v1.0.0"
    environment: str = "Development"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    # ------------------------------- database -------------------------------- #
    # Default: local SQLite file. Switch to PostgreSQL by exporting
    # DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/gengv1
    database_url: str = Field(
        default=f"sqlite:///{(BACKEND_DIR / 'data' / 'gengv1.db').as_posix()}"
    )

    # ------------------------------ data source ------------------------------ #
    # "mock"     -> deterministic demo dataset (clearly labelled in the UI)
    # "bilibili" -> real collection pipeline (needs a reachable, non-blocked client)
    data_source: str = "mock"
    bili_cookie: str = ""
    bili_search_url: str = "https://api.bilibili.com/x/web-interface/wbi/search/type"
    bili_user_space_url: str = "https://api.bilibili.com/x/space/wbi/arc/search"
    bili_timeout: float = 10.0

    # --------------------------------- LLM ----------------------------------- #
    llm_provider: str = "longcat"
    llm_base_url: str = "https://api.longcat.chat/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "LongCat-2.5-Preview"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 300
    # 最坏耗时 ≈ timeout * (retries + 1) + 退避；默认控制在 21s 左右，
    # 前端 AI 卡片有"生成中"状态，不阻塞页面
    llm_timeout: float = 10.0
    llm_max_retries: int = 2
    llm_backoff_base: float = 0.8
    # When the LLM is unavailable we still answer with an algorithm-written
    # sentence so the product loop never breaks. Set to false for a strict
    # "temporarily unavailable" response.
    llm_allow_rule_based_fallback: bool = True
    # Re-generate a cached insight only when the underlying data changed.
    ai_cache_min_data_gap_hours: float = 6.0

    # ------------------------------- analytics -------------------------------- #
    analysis_window_days: int = 30
    # 双 UP 在线核验被 B 站风控挡住时（缺 BILI_COOKIE），是否仍允许
    # "人工整理但尚未在线核验"的梗参与分析。关掉后正式梗库会只剩在线核验通过的梗。
    # 无论开关如何，接口和页面都会如实标出 verification_state。
    analysis_allow_unverified: bool = True

    # 站点配置为真实数据源时，榜单/详情只收"真实采集到 + 至少一位 UP 主有真实投稿证据"的梗
    # （verification_state 为 verified_both 或 partially_verified）。演示梗库是手写的，
    # 认证记录也是自造的，让它跟真梗同榜混排等于用假数字压真热度。
    # 跑演示（DATA_SOURCE=mock）时这条不生效，否则演示产品会空掉。
    leaderboard_require_verified: bool = True
    relevance_threshold: float = 0.5

    # ------------------------------- discovery -------------------------------- #
    # 发现层认证窗口（滚动天数）。解说视频通常比梗的爆发期早 1~2 周，
    # 用报告窗口（analysis_window_days=30）当认证窗口会把还在热的梗整条排除
    # ——漏掉「老叟戏顽童」就是这么来的。所以认证窗口独立、且比报告窗口宽。
    cert_window_days: int = 90

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("data_source")
    @classmethod
    def _normalise_source(cls, value: str) -> str:
        value = (value or "mock").strip().lower()
        return value if value in {"mock", "bilibili"} else "mock"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip())

    def masked_llm_api_key(self) -> str:
        """Safe representation for the settings UI / logs."""
        key = self.llm_api_key.strip()
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:3]}{'*' * 8}{key[-4:]}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
