"""写接口守卫：``ADMIN_TOKEN`` 留空时放行，配置后必须带 ``X-Admin-Token``。

守卫挂在 ``app/api/__init__.py`` 的 router 层（manage / jobs / settings / llm）
与 ``memes.py`` 的单条路由（POST insight）上，所以这里从 HTTP 层验证，
不直接测 ``require_admin`` —— 要防的正是"挂漏了某条路由"。

``settings`` 是模块级单例，用例用 monkeypatch 直接改其 ``admin_token`` 字段，
结束后由 pytest 自动还原，不会污染其它用例。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

TOKEN = "test-token-0123456789"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:  # lifespan 会建表并灌演示数据
        yield test_client


@pytest.fixture()
def guarded(monkeypatch):
    """临时开启令牌校验。"""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    return TOKEN


@pytest.fixture()
def open_access(monkeypatch):
    """显式回到"未配置令牌"状态，避免受宿主机 .env 影响。"""
    monkeypatch.setattr(settings, "admin_token", "")


# --------------------------------------------------------------------------- #
# 未配置令牌：完全放行（本机/内网开发体验不变）
# --------------------------------------------------------------------------- #
def test_unset_token_allows_write(client, open_access):
    assert client.get("/api/jobs/refresh").status_code == 200
    assert client.get("/api/manage/memes").status_code == 200


# --------------------------------------------------------------------------- #
# 配置令牌：缺令牌 / 错令牌 → 401
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path",
    [
        "/api/jobs/refresh",       # jobs 路由
        "/api/manage/memes",       # manage 路由
        "/api/settings/llm",       # settings 路由
        "/api/llm/config",         # llm 路由
    ],
)
def test_write_route_rejects_without_token(client, guarded, path):
    response = client.get(path)
    assert response.status_code == 401, f"{path} 未受保护"
    assert "X-Admin-Token" in response.json()["detail"]


@pytest.mark.parametrize(
    "path",
    ["/api/jobs/refresh", "/api/manage/memes", "/api/settings/llm", "/api/llm/config"],
)
def test_write_route_rejects_wrong_token(client, guarded, path):
    response = client.get(path, headers={"X-Admin-Token": "wrong-token"})
    assert response.status_code == 401, f"{path} 令牌校验被绕过"


@pytest.mark.parametrize(
    "path",
    ["/api/jobs/refresh", "/api/manage/memes", "/api/settings/llm", "/api/llm/config"],
)
def test_write_route_accepts_correct_token(client, guarded, path):
    response = client.get(path, headers={"X-Admin-Token": TOKEN})
    assert response.status_code == 200, f"{path} 带对令牌仍被拒"


def test_insight_post_is_guarded(client, guarded):
    """POST insight 会调 LLM（真金白银），必须跟写接口同等待遇。"""
    body = {"refresh": False}
    assert client.post("/api/memes/1/insight", json=body).status_code == 401
    # 带上令牌后不再是 401（梗不存在是 404，属于放行后的业务判断）
    allowed = client.post(
        "/api/memes/1/insight", json=body, headers={"X-Admin-Token": TOKEN}
    )
    assert allowed.status_code != 401


# --------------------------------------------------------------------------- #
# 只读接口始终公开：小程序端只走这几个，开不开令牌都要能读
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path",
    ["/api/health", "/api/meta", "/api/memes?limit=1"],
)
def test_read_routes_stay_public(client, guarded, path):
    assert client.get(path).status_code == 200, f"{path} 被误锁"
