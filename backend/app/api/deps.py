"""FastAPI 依赖。"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import get_session

SessionDep = Annotated[Session, Depends(get_session)]


def require_admin(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    """写接口守卫：校验请求头 ``X-Admin-Token``。

    - ``ADMIN_TOKEN`` 未配置（默认）→ **直接放行**，保持本机/内网开发体验不变，
      也避免把"没配令牌"变成一上线就 401 的坑。
    - 配置后 → 必须带上完全一致的令牌，否则 401。

    只挂在写接口（manage / jobs / settings / llm，以及 POST insight）上；
    只读接口不挂，小程序端的只读能力因此不受影响。

    用 ``secrets.compare_digest`` 做定长比较，避免逐字符比较泄漏令牌长度与前缀。
    """
    expected = settings.admin_token.strip()
    if not expected:
        return
    provided = (x_admin_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要管理员令牌：请在请求头带上 X-Admin-Token",
            headers={"WWW-Authenticate": "X-Admin-Token"},
        )


AdminDep = Annotated[None, Depends(require_admin)]
