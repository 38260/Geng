"""Application settings.

Everything that a user may want to change lives in ``.env`` (see ``.env.example``).
Secrets (``LLM_API_KEY``, ``BILI_COOKIE``) are never hard-coded and never logged.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
    # NoDecode：告诉 pydantic-settings 别先把环境变量按 JSON 解析。
    # 不加它，`CORS_ORIGINS=a,b` 会在 JSON 预解析阶段就抛
    # SettingsError，下面那个"逗号分隔"的 validator 根本轮不到执行。
    cors_origins: Annotated[list[str], NoDecode] = Field(
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
    # LongCat-2.5-Preview 是带思考段的模型：300 token 会被 reasoning 吃光，
    # 实测 content 返回空串、usage.total_tokens=330，界面就只能退回算法文案。
    # 给到 900，正文才真的落在 content 里。
    llm_max_tokens: int = 900
    # 最坏耗时 ≈ timeout * (retries + 1) + 退避。10s 是照着"非思考模型"定的：
    # 实测同一次调用 10s 内两次超时、第 3 次 32.2s 才回，等于白白重试两次再失败。
    # LongCat 冷启动排队时会超过 45s（实测三次尝试合计 77s 才拿到一次成功），
    # 所以给到 60s。前端 AI 卡片有"生成中"状态，不阻塞页面。
    llm_timeout: float = 60.0
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
    # 热榜还要过"活着"门槛（过气不出榜 + 有内容天数或近 7 天头部播放达标）。
    # 关掉后首页会把考古区的梗也排进来，只建议在排查数据时临时打开。
    leaderboard_gate: bool = True
    relevance_threshold: float = 0.5

    # --------------------------- 采集抖动兜底 -------------------------------- #
    # B 站搜索接口有三种"没有结果"的返回，其中两种长得很不一样：
    #   真的没内容 : {"result": [], "numResults": 0, ...}      ← 可信
    #   被限流吞掉 : {"v_voucher": "voucher_xxx"}              ← 没有 numResults
    # 后者是风控应答（HTTP 200、无错误码），搜「动画」这种绝对有内容的词也会被吞，
    # 所以它**不代表当天没有内容**。它会随持续请求累积：
    # 冷启动命中率 ~98%，连续打几百次后掉到 0~30%，停手静默约 5 分钟恢复。
    # 旧实现把两者混成 rows==[]，于是"被限流"在库里和"当天没人做这个梗"长得一样。
    #
    # 这里是"首次之外的额外重试次数"，设 0 等于退回旧行为。
    collect_day_retries: int = 2
    # 重试间隔（秒），乘上次数递增。贴着打会让风控更紧。
    collect_retry_gap: float = 1.2
    # 命中限流（v_voucher）时退避的倍率：限流是会话级状态，
    # 快打只会加深处罚，所以退避要给得比普通异常长得多。
    collect_throttle_backoff_factor: float = 8.0
    # 连续被限流的梗达到这个数量就提前收工：说明整条会话已经进了限流状态，
    # 再打下去只会把恢复时间拖得更长（实测静默约 5 分钟复位）。
    collect_throttle_stop_after: int = 5
    # "7 天窗口里至少观测到几天才允许谈趋势"这条闸门阈值在
    # app/config/algorithms.py 的 LifecycleThresholds.min_observed_days，
    # 跟其它算法阈值放一起，别在这里再写一份。

    # ------------------------------- 自动刷新 --------------------------------- #
    # 每天几点跑一次增量刷新（HH:MM）。留空 = 不自动，只手动触发——
    # 不默认往别人机器上塞后台任务。
    refresh_at: str = ""
    # 每周哪天改跑一次全窗口重采（0=周一 … 6=周日，-1=不做周校准）。
    # 老日子的头部播放量会随时间涨，只增量会让旧日子停在刚过完那天的偏低值。
    refresh_full_weekday: int = 0
    # 定时刷新要不要顺带翻两位 UP 主的投稿列表发现新梗（这一步最容易被风控）
    refresh_discovery: bool = True
    # 启动时若"统计截至"已滞后超过一天，补跑一次增量。
    # 00:00 那一刻笔记本多半在睡，不补就要等到第二天；只有开了 REFRESH_AT 才生效。
    refresh_on_start: bool = True

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
