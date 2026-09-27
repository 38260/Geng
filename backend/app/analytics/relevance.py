"""梗匹配与相关性过滤。

B 站搜索结果不会全部真的与目标梗相关，因此进入统计前必须先过一道打分：

    relevance = 0.6 * TitleMatch + 0.2 * DescriptionMatch + 0.2 * KeywordMatch
    进入统计的条件： relevance >= 0.5

标题命中主名算强证据；别名按长度分级——4 字以上（赛博木鱼）单独命中即可，
2~3 字的别名（黄豆、老六、发疯）只是常用词，单独命中不足以判定相关，
必须再有第二个词佐证，否则"琵琶曲黄豆版"这种字面撞车会把梗的数据灌满。

阈值与权重都来自 :mod:`app.config.algorithms`，不写死在这里。
LLM 不参与这一步（文档明确要求不要让 LLM 判断全部视频）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.config import RELEVANCE_THRESHOLD, RELEVANCE_WEIGHTS, STRONG_ALIAS_LEN
from app.models import Meme, Video


@dataclass(frozen=True)
class MemeTerms:
    name: str
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    @classmethod
    def from_meme(cls, meme: Meme) -> "MemeTerms":
        return cls(
            name=meme.name,
            aliases=tuple(meme.aliases or ()),
            keywords=tuple(meme.keywords or ()),
        )

    @property
    def search_terms(self) -> list[str]:
        """梗库驱动搜索用的词表：名称 + 别名（关键词太泛，只用于打分）。"""
        terms = [self.name, *self.aliases]
        out: list[str] = []
        seen: set[str] = set()
        for term in terms:
            term = (term or "").strip()
            if term and term.lower() not in seen:
                seen.add(term.lower())
                out.append(term)
        return out


@dataclass
class RelevanceResult:
    score: float
    title_score: float
    description_score: float
    keyword_score: float
    matched_terms: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.score >= RELEVANCE_THRESHOLD


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _alias_title_score(aliases: Sequence[str], title_l: str) -> float:
    """别名命中标题能给多少分，取决于这个别名有多"专属"。

    中文里 2~3 字的别名基本就是常用词：「我不是黄豆」的别名"黄豆"会撞上
    琵琶曲黄豆版、炒黄豆、树叶做豆腐——那些视频跟这个梗毫无关系，但它们
    把梗的热度算上了榜。所以短别名只能算弱证据，必须再有别的词佐证才算相关；
    4 字以上的别名（赛博木鱼）仍然是单独命中就够。
    """
    hits = [alias for alias in aliases if alias and _norm(alias) in title_l]
    if not hits:
        return 0.0
    longest = max(len(alias) for alias in hits)
    return 0.85 if longest >= STRONG_ALIAS_LEN else 0.5


def score_text(terms: MemeTerms, title: str, description: str = "", tags: Iterable[str] = ()) -> RelevanceResult:
    title_l, desc_l = _norm(title), _norm(description)
    tags_l = _norm(" ".join(tags or []))
    blob = f"{title_l} {desc_l} {tags_l}"

    # 标题：主名 > 别名 > 关键词
    if _norm(terms.name) and _norm(terms.name) in title_l:
        title_score = 1.0
    elif (alias_score := _alias_title_score(terms.aliases, title_l)) > 0.0:
        title_score = alias_score
    elif any(k and _norm(k) in title_l for k in terms.keywords):
        title_score = 0.5
    else:
        title_score = 0.0

    # 描述
    if _norm(terms.name) and _norm(terms.name) in desc_l:
        desc_score = 1.0
    elif any(a and _norm(a) in desc_l for a in terms.aliases):
        desc_score = 0.6
    elif any(k and _norm(k) in desc_l for k in terms.keywords):
        desc_score = 0.4
    else:
        desc_score = 0.0

    # 关键词覆盖率
    if terms.keywords:
        covered = sum(1 for k in terms.keywords if _norm(k) and _norm(k) in blob)
        keyword_score = covered / len(terms.keywords)
    else:
        keyword_score = 0.0

    matched = [t for t in (terms.name, *terms.aliases, *terms.keywords) if t and _norm(t) in blob]

    score = (
        RELEVANCE_WEIGHTS.title * title_score
        + RELEVANCE_WEIGHTS.description * desc_score
        + RELEVANCE_WEIGHTS.keyword * keyword_score
    )
    return RelevanceResult(
        score=round(min(1.0, max(0.0, score)), 4),
        title_score=title_score,
        description_score=desc_score,
        keyword_score=round(keyword_score, 4),
        matched_terms=matched,
    )


def match_videos(
    terms: MemeTerms,
    videos: Sequence[Video],
    *,
    threshold: float = RELEVANCE_THRESHOLD,
) -> tuple[list[Video], list[Video]]:
    """给视频打分并回填，返回 (通过过滤的视频, 被过滤的视频)。"""
    kept: list[Video] = []
    dropped: list[Video] = []
    for video in videos:
        result = score_text(terms, video.title, video.description, video.tags)
        video.relevance_score = result.score
        video.matched_terms = result.matched_terms
        (kept if result.score >= threshold else dropped).append(video)
    return kept, dropped
