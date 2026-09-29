"""字幕抓取脚本：清单、跳过、覆盖率报告与风控中断。

全部走假客户端，不发真实请求；共用内存会话时把脚本的 commit 降级成 flush，
免得像素脚本那样把测试数据提交进内存库（conftest 的 rollback 就失效了）。
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.collectors.bilibili import BilibiliBlocked, SubtitleResult
from app.models import Meme, MemeCertification, Video, VideoTranscript
from app.scripts import fetch_transcripts as script


class FakeSubtitleClient:
    def __init__(self, results: dict[str, SubtitleResult | Exception], *, cookie: str = "SESSDATA=x"):
        self.cookie = cookie
        self.results = results
        self.asked: list[str] = []

    def subtitle_of(self, bvid: str) -> SubtitleResult:
        self.asked.append(bvid)
        item = self.results.get(bvid)
        if isinstance(item, Exception):
            raise item
        return item or SubtitleResult(bvid=bvid, reason="假客户端没这条")


class _SharedSession:
    """把脚本自己 new 的 SessionLocal 指到测试会话上。"""

    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        if name == "commit":
            return self._session.flush
        return getattr(self._session, name)

    def close(self):  # 由 fixture 负责关
        pass


def _ok(bvid: str, *, kind: str = "cc", text: str = "这个梗出自一场直播\nUP 主把它做成了 BGM", title: str = "解说标题"):
    return SubtitleResult(bvid=bvid, cid=1, kind=kind, lang="zh-CN", text=text, title=title, logged_in=True)


def _empty(bvid: str, reason: str):
    return SubtitleResult(bvid=bvid, reason=reason, logged_in=True)


@pytest.fixture()
def wired(session, monkeypatch):
    """装好假客户端、假 ensure_schema，并让脚本复用测试会话。"""
    monkeypatch.setattr(script, "ensure_schema", lambda: None)

    def _bind(results, **kwargs):
        client = FakeSubtitleClient(results, **kwargs)
        monkeypatch.setattr(script, "get_client", lambda: client)
        monkeypatch.setattr(script, "SessionLocal", lambda: _SharedSession(session))
        return client

    return _bind


def _bilibili_meme(session, meme_factory, name: str, *, bvids: list[tuple[str, str]], views: dict[str, int] | None = None):
    """建一个真实来源的梗：两条认证解说 + 若干相关视频。"""
    meme = meme_factory(name=name, data_source="bilibili")
    for index, (bvid, role) in enumerate(bvids):
        session.add(
            MemeCertification(
                meme_id=meme.id,
                role=role,
                up_name=f"UP{index + 1}",
                up_mid=1000 + index,
                bvid=bvid,
                video_title=f"《{name}》解说 {role}",
                confirmed=True,
                data_source="bilibili",
            )
        )
    for bvid, view in (views or {}).items():
        session.add(
            Video(
                meme_id=meme.id,
                bvid=bvid,
                title=f"{name} 相关 {bvid}",
                view=view,
                publish_time=datetime(2026, 9, 1),
                data_source="bilibili",
            )
        )
    session.flush()
    return meme


def test_script_refuses_without_cookie(wired, session, meme_factory, capsys):
    """没 cookie 就白跑三轮请求，脚本必须先拦住。"""
    _bilibili_meme(session, meme_factory, "无cookie梗", bvids=[("BV1a", "encyclopedia")])
    client = wired({}, cookie="")

    assert script.main([]) == 2
    assert client.asked == []
    assert "BILI_COOKIE" in capsys.readouterr().out


def test_script_stores_cc_and_reports_coverage(wired, session, meme_factory, capsys):
    _bilibili_meme(
        session,
        meme_factory,
        "覆盖率梗",
        bvids=[("BV1cc", "encyclopedia"), ("BV1ai", "guide"), ("BV1none", "extra")],
    )
    client = wired(
        {
            "BV1cc": _ok("BV1cc"),
            "BV1ai": _ok("BV1ai", kind="ai"),
            "BV1none": _empty("BV1none", "这条视频没有字幕轨（解说区很多是把字烧在画面里的）"),
        }
    )

    code = script.main(["--sleep", "0"])
    out = capsys.readouterr().out
    assert code == 0
    # 清单按 role 字典序排（encyclopedia < extra < guide），不是按传入顺序
    assert client.asked == ["BV1cc", "BV1none", "BV1ai"]

    rows = {row.bvid: row for row in session.scalars(select(VideoTranscript))}
    assert set(rows) == {"BV1cc", "BV1ai"}, "没拿到的不该入库"
    assert rows["BV1cc"].kind == "cc" and rows["BV1ai"].kind == "ai"
    for row in rows.values():
        assert row.chars == len(row.text) and row.meme_id
        assert row.video_title == "解说标题", "入库用 view 下发的真实标题"
        assert row.logged_in is True

    # 覆盖率按档分开报，别把「没抓到」和「抓到了但没用」混成一句失败
    assert "待抓：3 条" in out
    assert "处理 3 条：有字幕 2，无字幕/失败 1" in out
    assert "人工 CC 字幕：1 条（33%）" in out
    assert "AI 识别字幕：1 条（33%）" in out
    assert "确实没字幕轨：1 条（33%）" in out


def test_dry_run_lists_without_requests(wired, session, meme_factory, capsys):
    _bilibili_meme(
        session,
        meme_factory,
        "演练梗",
        bvids=[("BV1x", "encyclopedia")],
        views={"BV1hot": 9999},
    )
    client = wired({})

    assert script.main(["--dry-run", "--top", "1"]) == 0
    out = capsys.readouterr().out
    assert client.asked == []
    assert "BV1x" in out and "BV1hot" in out, "清单要把认证视频和头部视频都列出来"
    assert session.scalars(select(VideoTranscript)).first() is None


def test_existing_bvid_skipped_unless_force(wired, session, meme_factory, capsys):
    _bilibili_meme(session, meme_factory, "去重梗", bvids=[("BV1dup", "encyclopedia")])
    wired({"BV1dup": _ok("BV1dup")})
    script.main(["--sleep", "0"])
    capsys.readouterr()

    again = wired({"BV1dup": _ok("BV1dup", text="重抓的新字幕")})
    assert script.main(["--sleep", "0"]) == 0
    assert again.asked == [], "字幕不会天天改，默认跳过"
    assert "1 条已有字幕，跳过" in capsys.readouterr().out

    forced = wired({"BV1dup": _ok("BV1dup", text="重抓的新字幕")})
    script.main(["--force", "--sleep", "0"])
    assert forced.asked == ["BV1dup"]
    row = session.scalars(select(VideoTranscript)).one()
    assert row.text == "重抓的新字幕"


def test_blocked_stops_the_run_but_keeps_earlier_wins(wired, session, meme_factory, capsys):
    _bilibili_meme(
        session,
        meme_factory,
        "风控梗",
        bvids=[("BV1good", "encyclopedia"), ("BV1bad", "extra"), ("BV1later", "guide")],
    )
    client = wired(
        {
            "BV1good": _ok("BV1good"),
            "BV1bad": BilibiliBlocked("B 站风控拦截（HTTP 412）"),
        }
    )

    code = script.main(["--sleep", "0"])
    out = capsys.readouterr().out
    assert code == 0
    assert client.asked == ["BV1good", "BV1bad"], "被风控后要停，不能继续硬打"
    assert "风控中断" in out and "被风控中断：1 条" in out
    assert [row.bvid for row in session.scalars(select(VideoTranscript))] == ["BV1good"]


def test_hot_videos_join_the_list_once(wired, session, meme_factory, capsys):
    """同一 bvid 既是认证解说又是头部视频时只抓一次（归属第一个梗）。"""
    _bilibili_meme(
        session,
        meme_factory,
        "重复梗",
        bvids=[("BV1same", "encyclopedia")],
        views={"BV1same": 5000, "BV1other": 4000},
    )
    client = wired({"BV1same": _ok("BV1same"), "BV1other": _ok("BV1other", kind="ai")})

    script.main(["--top", "5", "--sleep", "0"])
    out = capsys.readouterr().out
    assert client.asked == ["BV1same", "BV1other"]
    assert "清单：2 条视频" in out
    kinds = {row.bvid: row.kind for row in session.scalars(select(VideoTranscript))}
    assert kinds == {"BV1same": "cc", "BV1other": "ai"}
