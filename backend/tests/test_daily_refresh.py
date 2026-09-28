"""每日刷新脚本：锁、报告、退出码。全部离线，不碰 B 站也不写真库。"""

from __future__ import annotations

import json

import pytest

from app.scripts import daily_refresh as dr


@pytest.fixture()
def isolated(monkeypatch, tmp_path):
    """把锁文件、状态文件、报告文件都挪到 tmp_path，别污染真实目录。"""
    monkeypatch.setattr(dr, "LOCK_FILE", tmp_path / ".refresh.lock")
    monkeypatch.setattr(dr, "STATE_FILE", tmp_path / "last_refresh.json")
    monkeypatch.setattr(dr, "REPORT_FILE", tmp_path / "refresh-report.md")
    return tmp_path


def test_lock_is_single_instance(isolated):
    assert dr.acquire_lock("手动") is True
    assert dr.acquire_lock("定时") is False, "第二次触发必须被挡住，否则同一批请求打两遍"
    dr.release_lock()
    assert dr.acquire_lock("定时") is True


def test_stale_lock_can_be_taken(isolated):
    """上次跑到一半被 kill，锁不能把后面所有刷新永久锁死。"""
    import os
    import time

    assert dr.acquire_lock("手动") is True
    old = time.time() - dr.LOCK_STALE_SECONDS - 10
    os.utime(dr.LOCK_FILE, (old, old))
    assert dr.acquire_lock("定时") is True


def test_mock_mode_refuses(isolated, monkeypatch):
    monkeypatch.setattr(dr.settings, "data_source", "mock")
    assert dr.main([]) == 2
    assert not dr.STATE_FILE.exists(), "没真跑就不该留下'上次刷新'的记录"


def test_main_writes_state_and_report(isolated, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(dr.settings, "data_source", "bilibili")
    monkeypatch.setattr(dr, "run_discovery", lambda **_: {"ok": True, "pool_size": 51, "touched": 51, "new_memes": 3, "new_names": ["甲", "乙", "丙"]})
    monkeypatch.setattr(
        dr,
        "collect_all",
        lambda *a, **k: calls.append("collect") or {
            "ok": True, "reason": "WBI 可用", "source": "bilibili", "targets": 75,
            "collected": 70, "empty": 4, "failed": 1, "videos": 900, "skipped": 0,
            "dropped": 1200, "kept_snapshots": 0, "thinned": 2, "kept_better_days": 30,
            "skipped_demo": 9, "scope": k["scope"], "scope_note": "跳过 9 个纯演示梗",
        },
    )
    monkeypatch.setattr(dr, "recompute_all", lambda **_: {"computed": 31, "skipped": 53, "total": 84})

    assert dr.main(["--trigger", "定时"]) == 1, "有梗被拒就是部分失败，退出码要能看出来"
    assert calls == ["collect"]

    state = json.loads(dr.STATE_FILE.read_text(encoding="utf-8"))
    assert state["trigger"] == "定时"
    assert state["mode"] == "incremental"
    assert state["exit_code"] == 1
    assert state["collect"]["targets"] == 75
    assert state["collect"]["skipped_demo"] == 9
    assert state["recompute"]["computed"] == 31
    assert "data_through" in state and "data_lag_days" in state

    report = dr.REPORT_FILE.read_text(encoding="utf-8")
    assert "跳过 9 个纯演示梗" in report
    assert report.startswith("# 刷新运行报告")


def test_full_mode_uses_the_whole_window(isolated, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(dr.settings, "data_source", "bilibili")
    monkeypatch.setattr(dr.settings, "analysis_window_days", 30)
    monkeypatch.setattr(dr, "run_discovery", lambda **_: {"ok": False, "error": "HTTP 412"})
    monkeypatch.setattr(
        dr,
        "collect_all",
        lambda *a, **k: seen.update(k) or {
            "ok": True, "reason": "ok", "source": "bilibili", "targets": 75, "collected": 75,
            "empty": 0, "failed": 0, "videos": 0, "skipped": 0, "dropped": 0,
            "kept_snapshots": 0, "thinned": 0, "kept_better_days": 0, "skipped_demo": 9,
            "scope": "real", "scope_note": "",
        },
    )
    monkeypatch.setattr(dr, "recompute_all", lambda **_: {"computed": 1, "skipped": 0, "total": 1})

    assert dr.main(["--full"]) == 0, "全部成功才是 0"
    assert seen["window_days"] == 30, "--full 要跑整个报告窗口"
    state = json.loads(dr.STATE_FILE.read_text(encoding="utf-8"))
    assert state["mode"] == "full"
    assert state["discovery"]["ok"] is False, "发现层失败要如实记着，但刷新本身仍算成功"


def test_report_keeps_only_recent_runs(isolated, monkeypatch):
    monkeypatch.setattr(dr.settings, "data_source", "bilibili")
    monkeypatch.setattr(dr, "run_discovery", lambda **_: {"ok": True, "pool_size": 1, "touched": 1, "new_memes": 0, "new_names": []})
    monkeypatch.setattr(
        dr, "collect_all", lambda *a, **k: {
            "ok": True, "reason": "ok", "source": "bilibili", "targets": 1, "collected": 1,
            "empty": 0, "failed": 0, "videos": 0, "skipped": 0, "dropped": 0,
            "kept_snapshots": 0, "thinned": 0, "kept_better_days": 0, "skipped_demo": 0,
            "scope": "real", "scope_note": "无",
        }
    )
    monkeypatch.setattr(dr, "recompute_all", lambda **_: {"computed": 1, "skipped": 0, "total": 1})

    for _ in range(24):
        dr.main(["--skip-discovery"])
    text = dr.REPORT_FILE.read_text(encoding="utf-8")
    assert text.count("## ") == 20, "报告只留最近 20 次，不能无限长"
