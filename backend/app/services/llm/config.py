"""LLM 运行配置。

全部来自环境变量（见 ``backend/.env.example``），代码里不写死 Key / Model。
业务层只依赖这个 dataclass，将来换任何 OpenAI 兼容厂商都不用改业务代码。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    temperature: float
    max_tokens: int
    timeout: float
    max_retries: int
    backoff_base: float

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip() and self.base_url.strip())

    @property
    def chat_completions_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    @property
    def models_url(self) -> str:
        base = self.base_url.rstrip("/")
        return base[: -len("/chat/completions")] if base.endswith("/chat/completions") else base

    def masked(self) -> dict[str, object]:
        """给前端/日志用的安全视图，永远不包含明文 Key。"""
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_ms": int(self.timeout * 1000),
            "max_retries": self.max_retries,
            "api_key_set": bool(self.api_key.strip()),
            "api_key_masked": _mask(self.api_key),
        }


def _mask(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:3]}{'*' * 10}{key[-4:]}"


def load_config() -> LLMConfig:
    return LLMConfig(
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        backoff_base=settings.llm_backoff_base,
    )
