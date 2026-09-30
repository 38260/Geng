"""数据科学流程的实况统计（Web 端「数据管线」页用）。

**只读接口**：不加 ``require_admin``，和 ``/api/meta`` 同组——它不暴露任何敏感信息
（凭据、Key、内网地址一律不出现在 payload 里），也不执行任何写操作。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.services.data_profile import data_profile_payload

from .deps import SessionDep

router = APIRouter(tags=["pipeline"])


@router.get("/api/pipeline")
def pipeline(session: SessionDep):
    """返回数据获取 / 处理 / 建模 / 质量 / AI 五段实况统计。"""
    return data_profile_payload(session)
