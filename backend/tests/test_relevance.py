"""相关性过滤：0.6 标题 + 0.2 描述 + 0.2 关键词，阈值 0.5。"""

from __future__ import annotations

import pytest

from app.analytics import MemeTerms, match_videos, score_text
from app.config import RELEVANCE_THRESHOLD, RELEVANCE_WEIGHTS

from .conftest import make_video

TERMS = MemeTerms(name="电子木鱼", aliases=("赛博木鱼",), keywords=("木鱼", "功德"))


def test_weights_sum_to_one():
    total = RELEVANCE_WEIGHTS.title + RELEVANCE_WEIGHTS.description + RELEVANCE_WEIGHTS.keyword
    assert total == pytest.approx(1.0)


def test_exact_name_in_title_and_description_is_full_score():
    result = score_text(TERMS, "电子木鱼是什么梗", "电子木鱼｜木鱼、功德 相关二创", [])
    assert result.title_score == 1.0
    assert result.description_score == 1.0
    assert result.score == pytest.approx(1.0)
    assert result.accepted


def test_alias_only_in_title_is_still_relevant():
    """只命中别名（没命中主名）也算相关：0.6*0.85 已经跨过 0.5 阈值。"""
    result = score_text(TERMS, "赛博木鱼？我一开始也没看懂", "只命中别名、不含关键词", [])
    assert result.title_score == 0.85
    assert result.score >= RELEVANCE_THRESHOLD
    assert result.accepted


def test_generic_keyword_alone_is_not_enough():
    """只蹭到一个泛关键词（"功德"）不足以判定相关，必须被过滤掉。"""
    result = score_text(TERMS, "在寺庙敲功德的一天", "随手记录", [])
    assert result.title_score == 0.5
    assert result.score < RELEVANCE_THRESHOLD
    assert result.accepted is False


def test_unrelated_video_is_filtered_out():
    result = score_text(TERMS, "生活区 vlog｜周末去了趟郊外", "完全无关", [])
    assert result.score == 0.0
    assert result.accepted is False


def test_keyword_coverage_counts():
    with_keywords = score_text(TERMS, "随便一个标题", "木鱼 功德 都提到了", [])
    without = score_text(TERMS, "随便一个标题", "什么都没提", [])
    assert with_keywords.keyword_score == 1.0
    assert without.keyword_score == 0.0
    assert with_keywords.score > without.score


def test_match_videos_partitions_and_backfills():
    videos = [
        make_video("BV1a", "全网都在玩电子木鱼，我悟了", description="电子木鱼｜木鱼、功德"),
        make_video("BV1b", "生活区 vlog｜周末去了趟郊外", description="无关"),
        make_video("BV1c", "电子木鱼教程", description="木鱼、功德 相关", tags=["木鱼", "功德"]),
    ]
    kept, dropped = match_videos(TERMS, videos, threshold=RELEVANCE_THRESHOLD)

    assert [v.bvid for v in dropped] == ["BV1b"]
    assert {v.bvid for v in kept} == {"BV1a", "BV1c"}
    for video in kept:
        assert video.relevance_score >= RELEVANCE_THRESHOLD
        assert video.matched_terms
    assert videos[1].relevance_score == 0.0


SOYBEAN = MemeTerms(name="我不是黄豆", aliases=("黄豆",), keywords=("黄豆", "表情包"))


def test_short_alias_hit_alone_is_not_enough():
    """「琵琶曲黄豆版」撞的是别名"黄豆"这个常用词，不是这个梗本身。"""
    result = score_text(SOYBEAN, "琵琶曲黄豆版", "一首曲子换个乐器弹", [])
    assert result.title_score == 0.5, "短别名只能算弱证据"
    assert result.accepted is False


def test_short_alias_needs_a_second_signal():
    """短别名 + 描述/关键词佐证，才算真的在讲这个梗。"""
    result = score_text(SOYBEAN, "黄豆这个表情到底什么来头", "满屏都是黄豆流汗表情包", [])
    assert result.accepted is True


def test_meme_name_in_title_always_wins():
    assert score_text(SOYBEAN, "我不是黄豆是什么梗", "", []).accepted is True
