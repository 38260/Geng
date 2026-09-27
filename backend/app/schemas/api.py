"""请求体模型（响应结构见 ``frontend/src/types/api.ts``）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RefreshRequest(BaseModel):
    refresh: bool = Field(default=False, description="true 时跳过 AI 缓存重新生成")


class MemeInsightRequest(BaseModel):
    meme_id: int
    refresh: bool = False


class TrendExplanationRequest(BaseModel):
    """允许直接传数据做调试；传 meme_id 则由后端取最新快照。"""

    meme_id: int | None = None
    data: dict | None = None
    refresh: bool = False


class CatchUpAdviceRequest(TrendExplanationRequest):
    pass


class MemeMetaUpdate(BaseModel):
    """梗元数据人工维护。不传的字段保持原样；只影响展示与检索，不影响任何算法指标。"""

    cover_url: str | None = Field(
        default=None, max_length=500, description="封面图片地址；空串表示恢复自动封面"
    )
    description: str | None = Field(default=None, description="梗介绍，最长 600 字")
    aliases: list[str] | None = Field(default=None, description="别名，用于搜索与相关性判定")
    keywords: list[str] | None = Field(default=None, description="关键词，同上")


class LLMSettingsUpdate(BaseModel):
    provider: str = "longcat"
    base_url: str = "https://api.longcat.chat/openai/v1"
    model: str = "LongCat-2.5-Preview"
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_tokens: int = Field(default=300, ge=16, le=4096)
    # 留空表示保持现有 Key 不变
    api_key: str | None = None
    persist: bool = Field(default=True, description="是否写入 backend/.env")
