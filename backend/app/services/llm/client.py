"""OpenAI 兼容 Chat Completions 客户端（默认对接 LongCat）。

约束：
* 429 / 5xx / 超时会重试，但**次数有限**（``LLM_MAX_RETRIES``），指数退避；
* 任何异常都不允许冒到业务层去把页面搞崩，统一转成 :class:`LLMError`；
* 日志与异常信息里永远不出现 API Key。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_logger

from .config import LLMConfig

log = get_logger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    """LLM 调用失败的统一异常，message 已脱敏。"""

    def __init__(self, message: str, *, kind: str = "error", status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status


class LLMNotConfiguredError(LLMError):
    def __init__(self) -> None:
        super().__init__("LLM 未配置：请在 backend/.env 填写 LLM_API_KEY", kind="not_configured")


@dataclass
class ChatResult:
    text: str
    model: str
    latency_ms: int
    usage: dict[str, Any]
    # content 为空、只能退回 ``reasoning_content`` 时为 True：这时 text 拿到的是
    # 模型的**思考过程**而不是答案。调用方必须自己决定怎么办——
    # 趋势解释那类"短输出"照旧兜底显示即可，而介绍那类需要归纳的任务必须当失败重试，
    # 否则就会出现"把英文推理当成中文介绍"的情况（实测踩过）。
    reasoning_only: bool = False


def _headers(config: LLMConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }


def chat(
    config: LLMConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatResult:
    """一次对话补全，带有限次指数退避重试。"""
    if not config.is_configured:
        raise LLMNotConfiguredError()

    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature if temperature is None else temperature,
        "max_tokens": config.max_tokens if max_tokens is None else max_tokens,
        "stream": False,
    }

    started = time.perf_counter()
    last_error: LLMError | None = None
    attempts = max(1, config.max_retries + 1)

    for attempt in range(attempts):
        try:
            with httpx.Client(timeout=config.timeout) as client:
                response = client.post(config.chat_completions_url, headers=_headers(config), json=payload)

            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise LLMError("模型返回为空", kind="empty", status=200)
                fell_back_to_reasoning = False
                message = choices[0].get("message") or {}
                finish = choices[0].get("finish_reason")
                text = (message.get("content") or "").strip()
                if not text:
                    # 带思考段的模型会把正文放在 reasoning_content，content 留空；
                    # 另外 max_tokens 被思考吃光时 finish_reason=length 且 content 也是空的。
                    # 不接住这两种情况，界面就永远只显示"AI 不可用"，而日志里看不出为什么。
                    reasoning = (message.get("reasoning_content") or "").strip()
                    text = reasoning
                    fell_back_to_reasoning = True
                    log.warning(
                        "LLM content 为空（finish_reason=%s, usage=%s），改用 reasoning_content %d 字",
                        finish, (data.get("usage") or {}).get("completion_tokens", "?"), len(reasoning),
                    )
                latency = int((time.perf_counter() - started) * 1000)
                log.info(
                    "LLM 调用成功 model=%s attempt=%s latency=%sms tokens=%s",
                    data.get("model", config.model), attempt + 1, latency,
                    (data.get("usage") or {}).get("total_tokens", "?"),
                )
                return ChatResult(
                    text=text.strip(),
                    model=data.get("model", config.model),
                    latency_ms=latency,
                    usage=data.get("usage") or {},
                    reasoning_only=fell_back_to_reasoning,
                )

            last_error = _error_from_response(response)
            if last_error.status not in RETRYABLE_STATUS:
                log.warning("LLM 调用失败（不可重试）：%s", last_error)
                raise last_error

        except httpx.TimeoutException:
            last_error = LLMError(f"LLM 请求超时（{config.timeout}s）", kind="timeout")
        except httpx.HTTPError as exc:
            last_error = LLMError(f"LLM 网络错误：{exc.__class__.__name__}", kind="network")

        if attempt < attempts - 1:
            delay = config.backoff_base * (2**attempt)
            log.warning(
                "LLM 调用失败（%s），%.1fs 后第 %s 次重试", last_error.kind if last_error else "?",
                delay, attempt + 2,
            )
            time.sleep(delay)

    raise last_error or LLMError("LLM 调用失败", kind="unknown")


def _error_from_response(response: httpx.Response) -> LLMError:
    detail = ""
    try:
        body = response.json()
        detail = str(body.get("error") or body.get("message") or body)[:200]
    except Exception:  # noqa: BLE001 - 响应不是 JSON 时按纯文本处理
        detail = response.text[:200]
    return LLMError(
        f"LLM 返回 {response.status_code}：{detail}",
        kind="rate_limited" if response.status_code == 429 else "http",
        status=response.status_code,
    )


def list_models(config: LLMConfig) -> list[str]:
    """GET /models，用于配置页自检。"""
    if not config.is_configured:
        raise LLMNotConfiguredError()
    try:
        with httpx.Client(timeout=config.timeout) as client:
            response = client.get(f"{config.models_url}/models", headers=_headers(config))
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"获取模型列表失败：{exc.__class__.__name__}", kind="network") from exc

    items = data.get("data") if isinstance(data, dict) else data
    models: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            models.append(item)
        elif isinstance(item, dict):
            model_id = item.get("id") or item.get("model") or item.get("name")
            if model_id:
                models.append(str(model_id))
    return sorted(set(models))


def test_connection(config: LLMConfig) -> ChatResult:
    """最小往返，验证 Key / BaseURL / Model 是否可用。"""
    return chat(
        config,
        [{"role": "user", "content": "回复两个字：可用"}],
        temperature=0.0,
        max_tokens=16,
    )
