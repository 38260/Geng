"""刷新服务：手动触发、单实例、定时计算、接口形状。不碰 B 站。"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import refresh as svc
from tests.conftest import reset_db


@pytest.fixture(scope="module")
def client():
    reset_db()
    with TestClient(app) as test_client:      # 触发 lifespan：建表 + 灌演示数据
        yield test_client


def test_mock_mode_refuses_refresh(monkeypatch):
    monkeypatch.setattr(svc.settings, "data_source", "mock")
    result = svc.run_now()
    assert result["ok"] is False
    assert "演示" in result["reason"], "要告诉用户演示模式该改用 seed_data"


def test_second_trigger_does_not_queue(monkeypatch):
    """已经在跑就明确拒绝，不排队：两次刷新同时打 B 站只会一起被风控。"""
    started = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(svc.settings, "data_source", "bilibili")
    # 让状态查询不去看真实锁文件，只看线程内状态
    monkeypatch.setattr(svc.daily_refresh, "LOCK_FILE", Path("__never__.lock"))

    def fake_main(argv):
        started.set()
        release.wait(5)
        return 0

    monkeypatch.setattr(svc.daily_refresh, "main", fake_main)

    first = svc.run_now(trigger="手动")
    assert first["ok"] is True
    assert started.wait(5)
    second = svc.run_now(trigger="定时")
    assert second["ok"] is False and second.get("running") is True

    release.set()
    for _ in range(100):
        if not svc.status()["running"]:
            break
        time.sleep(0.05)
    assert svc.status()["running"] is False


def test_next_run_is_the_upcoming_slot():
    base = datetime(2026, 9, 28, 22, 30)
    assert svc._next_run("00:05", base) == datetime(2026, 9, 29, 0, 5)
    assert svc._next_run("23:00", base) == datetime(2026, 9, 28, 23, 0)
    assert svc._next_run("坏格式", base) is None


def test_scheduler_exits_when_disabled(monkeypatch):
    """没配时间、或数据源不是 B 站，都不该起后台线程，也不该阻塞。"""
    stop = threading.Event()
    monkeypatch.setattr(svc.settings, "refresh_at", "")
    monkeypatch.setattr(svc.settings, "data_source", "bilibili")
    svc.scheduler_loop(stop)
    assert not stop.is_set()

    monkeypatch.setattr(svc.settings, "refresh_at", "00:05")
    monkeypatch.setattr(svc.settings, "data_source", "mock")
    svc.scheduler_loop(stop)
    assert not stop.is_set()


def test_catch_up_only_when_scheduled(monkeypatch):
    """没开 REFRESH_AT 就不该在启动时自己打 B 站。"""
    triggered: list = []
    monkeypatch.setattr(svc.settings, "data_source", "bilibili")
    monkeypatch.setattr(svc.settings, "refresh_at", "")
    monkeypatch.setattr(svc, "run_now", lambda **kw: triggered.append(kw) or {"ok": True})
    assert svc.catch_up_on_start().get("skipped")
    assert triggered == []


def test_catch_up_skips_fresh_data_and_runs_on_stale(monkeypatch):
    triggered: list = []
    monkeypatch.setattr(svc.settings, "data_source", "bilibili")
    monkeypatch.setattr(svc.settings, "refresh_at", "00:00")
    monkeypatch.setattr(svc, "run_now", lambda **kw: triggered.append(kw) or {"ok": True})

    monkeypatch.setattr(svc, "data_lag_days", lambda: 1)
    assert svc.catch_up_on_start().get("skipped"), "只滞后一天不该补跑"
    assert triggered == []

    monkeypatch.setattr(svc, "data_lag_days", lambda: 4)
    assert svc.catch_up_on_start()["ok"] is True
    assert triggered == [{"full": False, "trigger": "补跑"}]

    triggered.clear()
    monkeypatch.setattr(svc, "data_lag_days", lambda: None)
    assert svc.catch_up_on_start()["ok"] is True
    assert triggered == [{"full": True, "trigger": "首次建库"}], "库里没数据要跑全窗口"


def test_refresh_endpoints(client, monkeypatch):
    """接口形状：POST 不阻塞、被拒要 409，GET 能说出定时配置。"""
    monkeypatch.setattr(svc.settings, "data_source", "mock")
    refused = client.post("/api/jobs/refresh")
    assert refused.status_code == 409
    assert "演示" in refused.json()["reason"]

    status = client.get("/api/jobs/refresh").json()
    assert {"running", "last", "schedule", "data_source"} <= set(status)
    assert status["schedule"]["enabled"] is False, "mock 模式下定时不该算启用"

    meta = client.get("/api/meta").json()
    assert "refresh" in meta and "schedule" in meta["refresh"]


def test_meta_reports_last_refresh(client, monkeypatch, tmp_path):
    state = tmp_path / "last_refresh.json"
    state.write_text(json.dumps({
        "finished_at": "2026-09-28T00:06:10", "trigger": "定时", "mode": "incremental",
        "exit_code": 0, "data_through": "2026-09-27",
        "collect": {"collected": 70, "targets": 75, "failed": 0, "skipped_demo": 9},
    }), encoding="utf-8")
    monkeypatch.setattr(svc.daily_refresh, "STATE_FILE", state)

    last = client.get("/api/meta").json()["refresh"]["last"]
    assert last["trigger"] == "定时" and last["mode"] == "incremental"
    assert last["collected"] == 70 and last["skipped_demo"] == 9
    assert last["exit_code"] == 0
