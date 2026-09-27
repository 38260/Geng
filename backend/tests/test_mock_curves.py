"""演示数据本身也要能被审计：形状多样、口径自洽、且明确标记为 mock。"""

from __future__ import annotations

from app.mock.catalogue import ALL_STAGES, MEME_CATALOGUE, spec_for
from app.mock.curves import (
    activity_curve,
    build_daily_points,
    build_sample_videos,
    stats_from_points,
)

ARCHETYPES = list(ALL_STAGES)


def test_curves_are_not_all_the_same_shape():
    """文档 §四十八：不能所有 Mock 都是 50/60/70/80/90。"""
    shapes = {a: activity_curve(a, 30, seed=1) for a in ARCHETYPES}
    tails = {a: sum(v[-7:]) / (sum(v) or 1) for a, v in shapes.items()}
    assert len(set(round(value, 3) for value in tails.values())) >= 5
    assert tails["explosive"] > tails["plateau"] > tails["receding"] > tails["obsolete"]
    assert shapes["rising"][-1] > shapes["rising"][0]
    assert shapes["receding"][-1] < max(shapes["receding"])


def test_daily_points_are_internally_consistent():
    points = build_daily_points(archetype="rising", scale=90_000, seed=3, days=30)
    assert len(points) == 30
    for point in points:
        if point.video_count == 0:
            assert point.view == 0 and point.creator_count == 0
        else:
            assert point.view > 0
            assert point.creator_count <= point.video_count
            assert point.discussion > 0


def test_obsolete_series_really_goes_quiet():
    points = build_daily_points(archetype="obsolete", scale=3_600, seed=5, days=30)
    last_two_weeks = points[-14:]
    assert sum(p.video_count for p in last_two_weeks) <= 4
    assert sum(p.view for p in last_two_weeks) < points[0].view


def test_everything_is_labelled_as_mock():
    points = build_daily_points(archetype="plateau", scale=40_000, seed=9, days=30)
    stats = stats_from_points(7, points)
    videos = build_sample_videos(
        meme_name="阿巴阿巴", aliases=("阿巴",), keywords=("拟声", "装傻"),
        points=points, scale=40_000, seed=9, count=10,
    )
    assert all(row.data_source == "mock" for row in stats)
    assert all(video.data_source == "mock" for video in videos)
    assert all(row.meme_id == 7 for row in stats)


def test_video_sample_includes_irrelevant_control():
    points = build_daily_points(archetype="rising", scale=90_000, seed=11, days=30)
    videos = build_sample_videos(
        meme_name="班味", aliases=("去班味",), keywords=("打工人", "职场"),
        points=points, scale=90_000, seed=11, count=10,
    )
    assert len(videos) == 10
    assert any("班味" not in video.title for video in videos), "需要保留无关对照样本"
    assert all(video.relevance_score == 0.0 for video in videos), "相关性必须由算法回填"


def test_catalogue_covers_all_six_stages_and_stays_certifiable():
    counts = {stage: 0 for stage in ARCHETYPES}
    for spec in MEME_CATALOGUE:
        if spec.certification == "both":
            counts[spec.archetype] += 1
    assert all(count > 0 for count in counts.values()), counts
    assert sum(counts.values()) >= 30, "第一版建议 30-50 个已认证梗"

    uncertified = [s.name for s in MEME_CATALOGUE if s.certification != "both"]
    assert uncertified, "需要保留未认证梗，才能验证双 UP 闸门"
    for name in uncertified:
        assert spec_for(name).certification in {"enc", "guide", "none"}
