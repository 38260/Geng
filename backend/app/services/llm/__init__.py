"""LLM 能力层：配置 / 客户端 / 业务封装。"""

from .client import LLMError, LLMNotConfiguredError, chat, list_models, test_connection
from .config import LLMConfig, load_config
from .service import (
    InsightOutput,
    generate,
    generate_catch_up_advice,
    generate_trend_explanation,
    parse_json_object,
    render_prompt,
    rule_based_trend,
)

__all__ = [
    "LLMConfig",
    "load_config",
    "LLMError",
    "LLMNotConfiguredError",
    "chat",
    "list_models",
    "test_connection",
    "InsightOutput",
    "generate",
    "generate_trend_explanation",
    "generate_catch_up_advice",
    "parse_json_object",
    "render_prompt",
    "rule_based_trend",
]
