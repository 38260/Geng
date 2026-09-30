"""测试隔离：内存 SQLite + 干净的表结构。

必须在导入任何 app 模块之前设置环境变量，因为配置是模块级单例。
"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DATA_SOURCE"] = "mock"
os.environ["LLM_API_KEY"] = ""
os.environ["APP_ENVIRONMENT"] = "Test"
# 逐日采集的空返回重试是真 sleep（生产要躲风控），测试里绝不能睡：
# 一个 30 天窗口的用例会因此多花 100 秒以上。重试次数保留，间隔归零。
os.environ["COLLECT_RETRY_GAP"] = "0"
# 命中限流后的"会话冷却"默认 180 秒，测试里同样必须归零——
# 否则任何触发限流的用例都会真睡三分钟。需要验证冷却时长的用例
# 用 monkeypatch 单独把 collect_throttle_cooldown 调回来。
os.environ["COLLECT_THROTTLE_COOLDOWN"] = "0"

from datetime import date, datetime, timedelta  # noqa: E402

import pytest  # noqa: E402

from app.models import (  # noqa: E402
    Meme,
    MemeDailyStats,
    SessionLocal,
    Video,
    reset_db,
)


@pytest.fixture(scope="session", autouse=True)
def _database():
    reset_db()
    yield


@pytest.fixture()
def session():
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


_MEME_SEQ = {"n": 0}


@pytest.fixture()
def meme_factory(session):
    """部分用例会 commit（AI 缓存路径），所以序号用模块级计数器避免 slug 撞车。"""

    def _make(name: str | None = None, **kwargs) -> Meme:
        _MEME_SEQ["n"] += 1
        index = _MEME_SEQ["n"]
        name = name or f"测试梗{index}"
        meme = Meme(
            name=name,
            slug=kwargs.pop("slug", f"test-{index}"),
            aliases=kwargs.pop("aliases", [f"{name}别名"]),
            keywords=kwargs.pop("keywords", ["测试"]),
            description=kwargs.pop("description", "单元测试用梗"),
            **kwargs,
        )
        session.add(meme)
        session.flush()
        return meme

    return _make


def make_stats(meme_id: int, values: list[int], *, end: date | None = None) -> list[MemeDailyStats]:
    """按"每日播放量"列表生成连续日统计，互动量按固定比例派生。"""
    end = end or date.today()
    rows: list[MemeDailyStats] = []
    n = len(values)
    for index, view in enumerate(values):
        rows.append(
            MemeDailyStats(
                meme_id=meme_id,
                stat_date=end - timedelta(days=n - 1 - index),
                video_count=max(0, int(view / 20_000)) if view else 0,
                creator_count=max(0, int(view / 25_000)) if view else 0,
                view=view,
                like=int(view * 0.06),
                coin=int(view * 0.02),
                favorite=int(view * 0.03),
                reply=int(view * 0.012),
                danmaku=int(view * 0.035),
                data_source="mock",
            )
        )
    return rows


def make_video(bvid: str, title: str, *, day: date | None = None, **kwargs) -> Video:
    day = day or date.today()
    return Video(
        bvid=bvid,
        title=title,
        description=kwargs.pop("description", ""),
        author=kwargs.pop("author", "测试UP"),
        publish_time=datetime(day.year, day.month, day.day, 12, 0),
        data_source=kwargs.pop("data_source", "mock"),
        **kwargs
    )
