"""数据科学流程的实况统计（供 Web 端「数据管线」页展示）。

注意与 :mod:`app.services.pipeline` 区分：那个是**指标计算管线本身**，
这里只是**把管线的实况读出来给页面看**——只读、不写库、不参与任何计算。

这个模块回答一个问题：这套数到底是怎么来的、怎么处理的、算到什么程度。
答案不靠前端写死文案，而是从库里和运行配置里现算出来，所以数字随库变动。

分成五段，对应一次完整的数据科学流程：

    acquisition  数据获取   从哪采、采什么、怎么躲风控、发了多少请求
    processing   数据处理   怎么清洗去重、怎么聚合、怎么处理缺失
    modeling     分析建模   热度指数、生命周期、赶潮判断的依据
    quality      数据质量   覆盖率、滞后、演示数据占比、观测缺失率
    ai           AI 应用     LLM 在哪一步介入、边界在哪、跑得怎么样

原则与全项目一致：**拿不到就说拿不到**。库是空的就给 0 / null，不编造好看的数。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import (
    GROWTH_SCORE_FULL,
    GROWTH_SCORE_ZERO,
    HOTNESS_REFERENCE,
    HOTNESS_WEIGHTS,
    LOW_SAMPLE_DAMPING,
    MIN_SAMPLE_VIDEOS,
    settings,
)
from app.models import (
    AIInsight,
    HotnessSnapshot,
    InsightSource,
    Meme,
    MemeDailyStats,
    Video,
)
from app.services.meme.query import meta_payload

# 热度指数同时在用的观察窗口（与算法层一致，这里只用于说明"在几个尺度上看"）
_HOTNESS_WINDOWS = (1, 3, 7, 30)

# 热度指数的基本窗口（见 app/analytics/hotness.py 的 PRIMARY_WINDOW / COMPARE_WINDOW）
_HOTNESS_PRIMARY = 7
_HOTNESS_COMPARE = 7

# 五个分量的展示名与输入口径。顺序与权重表一致，页面直接按这个顺序渲染。
_HOTNESS_TERMS = (
    ("view", "播放表现", "近 7 天播放量合计"),
    ("interaction", "互动表现", "近 7 天互动总量（当前实际=评论+弹幕）"),
    ("content", "内容规模", "近 7 天相关视频数"),
    ("creator", "参与 UP 主", "近 7 天单日去重峰值"),
    ("growth", "增长速度", "近 7 天 vs 前 7 天综合增幅"),
)

# 采集器默认每个检索词翻的页数（见 collectors/bilibili_collector.py 构造参数）
_PAGES_PER_TERM = 2
# 每条头部视频逐条补齐互动数据的上限（同上）
_ENRICH_LIMIT = 12


def _iso(value: Any) -> str | None:
    """把 date / datetime 统一成前端好渲染的 ISO 串；空值原样返回 None。"""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _day(value: Any) -> str | None:
    """只要日期部分，用于「跨了哪些天」这种展示。"""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _ratio(part: int, total: int) -> float | None:
    """比例；分母为 0 时给 None，不硬凑成 0.0——「没有数据」和「占比为零」是两回事。"""
    if not total:
        return None
    return round(part / total, 4)


def _steps(items: list[tuple[str, str, str]]) -> list[dict[str, str]]:
    return [{"key": key, "title": title, "detail": detail} for key, title, detail in items]


# --------------------------------------------------------------------------- #
# 五段各自的统计
# --------------------------------------------------------------------------- #
def _acquisition(session: Session, base: dict[str, Any]) -> dict[str, Any]:
    """数据获取：采集面、样本规模、反爬参数、请求量估算。"""
    video_total = session.scalar(select(func.count()).select_from(Video)) or 0
    video_real = (
        session.scalar(
            select(func.count()).select_from(Video).where(Video.data_source == "bilibili")
        )
        or 0
    )
    creator_total = (
        session.scalar(select(func.count(func.distinct(Video.author_mid))).select_from(Video)) or 0
    )
    pub_from, pub_to = session.execute(
        select(func.min(Video.publish_time), func.max(Video.publish_time))
    ).one()
    crawl_from, crawl_to = session.execute(
        select(func.min(Video.crawl_time), func.max(Video.crawl_time))
    ).one()

    window_days = settings.analysis_window_days
    meme_count = int(base.get("library_count") or 0)
    # 请求量估算：逐日查询是主要成本（梗 × 每天 × 每词翻页），头部视频补齐是次要成本。
    # 给的是量级而不是精确账单，所以前端文案上写「约」。
    est_daily = meme_count * window_days * _PAGES_PER_TERM
    est_enrich = meme_count * _ENRICH_LIMIT

    params = [
        {
            "label": "请求间隔",
            "value": f"{settings.collect_request_gap:.1f} 秒",
            "hint": f"约 {1 / settings.collect_request_gap:.2f} 次/秒，刻意压到接近人工搜索的速率",
        },
        {
            "label": "重试间隔",
            "value": f"{settings.collect_retry_gap:.1f} 秒",
            "hint": f"每天最多额外重试 {settings.collect_day_retries} 次；贴着打会让风控更紧",
        },
        {
            "label": "软限流冷却",
            "value": f"{settings.collect_throttle_cooldown:.0f} 秒",
            "hint": f"静默之后仍连续被吞 {settings.collect_throttle_stop_after} 天才判定等不回来",
        },
        {
            "label": "硬风控熔断",
            "value": f"{settings.collect_block_abort_after} 次",
            "hint": "连续遭遇硬风控就整批中止——继续跑既拿不到数据，又在给风控喂料",
        },
        {
            "label": "每词翻页",
            "value": f"{_PAGES_PER_TERM} 页",
            "hint": "按发布时间排序检索，避免结果被最近发布的内容占满",
        },
        {
            "label": "详情补齐",
            "value": f"前 {_ENRICH_LIMIT} 条",
            "hint": "搜索结果不含点赞/投币/收藏，需逐条查详情接口补全",
        },
    ]

    return {
        "steps": _steps(
            [
                (
                    "certified",
                    "从认证梗出发",
                    "以梗库中已通过双 UP 认证的梗为种子，取「梗名 + 别名 + 关键词」组成检索词表。"
                    "不做全站扫描，采集面由业务定义而不是由爬虫规模定义。",
                ),
                (
                    "daily",
                    "近 30 天逐日检索",
                    f"对每个检索词的最近 {window_days} 天逐日查询，且带上发布时间区间。"
                    "不带区间的搜索会被最近发布的内容占满，早期日期根本查不到，"
                    "直接聚合会算出 +23616% 这类被截断放大的假增长。",
                ),
                (
                    "filter",
                    "相关性打分过滤",
                    "候选视频与梗词表做相关性打分，低于阈值的丢弃——相关性由算法判定，不交给 LLM。",
                ),
                (
                    "enrich",
                    "头部视频补齐",
                    "搜索结果只带播放量，逐条调用视频详情接口补齐点赞/投币/收藏/评论/弹幕/时长/标签。",
                ),
                (
                    "throttle",
                    "风控兜底",
                    f"请求间隔 {settings.collect_request_gap:.1f} 秒；软限流先冷却 "
                    f"{settings.collect_throttle_cooldown:.0f} 秒；硬风控连续 "
                    f"{settings.collect_block_abort_after} 次即整批中止，不硬打。",
                ),
            ]
        ),
        "params": params,
        "video_total": video_total,
        "video_real": video_real,
        "video_demo": max(video_total - video_real, 0),
        "creator_total": creator_total,
        "publish_from": _day(pub_from),
        "publish_to": _day(pub_to),
        "crawl_from": _iso(crawl_from),
        "crawl_to": _iso(crawl_to),
        "window_days": window_days,
        "est_requests_daily": est_daily,
        "est_requests_enrich": est_enrich,
        "est_requests_total": est_daily + est_enrich,
    }


def _processing(session: Session, base: dict[str, Any]) -> dict[str, Any]:
    """数据处理：观测点规模、缺失建模、聚合与去重口径、派生指标。"""
    points_total = session.scalar(select(func.count()).select_from(MemeDailyStats)) or 0
    points_observed = (
        session.scalar(
            select(func.count())
            .select_from(MemeDailyStats)
            .where(MemeDailyStats.observed.is_(True))
        )
        or 0
    )
    points_unobserved = max(points_total - points_observed, 0)
    series_memes = (
        session.scalar(
            select(func.count(func.distinct(MemeDailyStats.meme_id))).select_from(MemeDailyStats)
        )
        or 0
    )
    stat_from, stat_to = session.execute(
        select(func.min(MemeDailyStats.stat_date), func.max(MemeDailyStats.stat_date))
    ).one()

    # 逐日序列里真实有值的是**播放量、评论、弹幕**：它们来自逐日搜索，一次查询就能拿到。
    # 点赞 / 投币 / 收藏不在搜索结果里，是补齐头部视频时落在 Video 表上的，
    # **不参与逐日聚合**（实测这三列在序列上恒为 0）。所以这里按序列的真实字段统计，
    # 不把 Video 表的口径挪过来充数——否则「互动量」会恒等于「讨论量」，
    # 看着像两套指标，其实同一套，反而误导。
    # 只对「已观测」的观测点求和：未观测的日子是「没看清」，不能当 0 计入。
    sums = session.execute(
        select(
            func.sum(MemeDailyStats.view),
            func.sum(MemeDailyStats.reply),
            func.sum(MemeDailyStats.danmaku),
        ).where(MemeDailyStats.observed.is_(True))
    ).one()
    view_total, reply, danmaku = (int(v or 0) for v in sums)
    discussion_total = reply + danmaku

    return {
        "steps": _steps(
            [
                (
                    "clean",
                    "清洗与去重",
                    "先按 bvid 去重，再按相关性打分的阈值剔除无关视频，"
                    "避免搜索结果里的无关内容把当日统计灌水。",
                ),
                (
                    "observe",
                    "观测缺失建模",
                    "B 站匿名搜索会随机返回空壳（实测命中率约 40%）。返回空壳不等于当天没人做这个梗，"
                    "所以单独用 observed 字段记状态：「未观测到」与「观测到零活动」是两种东西，"
                    "任何趋势结论都不许拿前者当 0 用。",
                ),
                (
                    "reobserve",
                    "同日取更优观测",
                    "同一天被重复采集时不相加、也不无脑覆盖，而是按「是否观测到 → 样本条数 → 合计播放量」"
                    "取更好的一次。否则一次抖动返回就能把真正观测到的那天覆盖掉，"
                    "热度会从 44.2 分掉到 0 分，看起来像崩了。",
                ),
                (
                    "incremental",
                    "增量只覆盖本次日期",
                    "增量日更只重写本次真正覆盖到的日期，历史序列不动——"
                    "跑一次「只补昨天」不会把 30 天序列砍成 1 天。",
                ),
                (
                    "derive",
                    "按日聚合与派生指标",
                    "原始量按天落成时间序列（播放量 / 评论 / 弹幕 / 视频数 / UP 主数），"
                    "讨论量 = 评论 + 弹幕。点赞、投币、收藏只落在视频样本上、不进逐日序列——"
                    "两类粒度分开记，不混算成一个「互动量」。",
                ),
            ]
        ),
        "observation_points": points_total,
        "observed_points": points_observed,
        "unobserved_points": points_unobserved,
        "unobserved_ratio": _ratio(points_unobserved, points_total),
        "meme_with_series": series_memes,
        "stat_from": _day(stat_from),
        "stat_to": _day(stat_to),
        "view_total": view_total,
        "discussion_total": discussion_total,
        "derived": [
            {"label": "播放量合计", "value": view_total, "hint": "日序列的主量，热度计算的基数之一"},
            {"label": "讨论量合计", "value": discussion_total, "hint": "评论 + 弹幕"},
        ],
    }


def _hotness_example(session: Session) -> dict[str, Any] | None:
    """取库里热度最高的那个梗，把五个分量拆开——公式的「活样本」。

    答辩时最容易被追问「权重是不是拍的」，所以摆一个能逐项对上总分的算例：
    各分量 × 权重求和，正好等于快照里那个分数。数字全部来自库，不是编的。
    """
    row = session.execute(
        select(Meme.name, HotnessSnapshot)
        .join(Meme, Meme.id == HotnessSnapshot.meme_id)
        .order_by(HotnessSnapshot.score.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    name, snapshot = row
    components = snapshot.components or {}
    if not components:
        return None

    weight_map = {
        "view": HOTNESS_WEIGHTS.view,
        "interaction": HOTNESS_WEIGHTS.interaction,
        "content": HOTNESS_WEIGHTS.content,
        "creator": HOTNESS_WEIGHTS.creator,
        "growth": HOTNESS_WEIGHTS.growth,
    }
    terms: list[dict[str, Any]] = []
    for key, label, source in _HOTNESS_TERMS:
        if key not in components:
            continue
        score = float(components[key] or 0.0)
        weight = float(weight_map[key])
        terms.append(
            {
                "key": key,
                "label": label,
                "source": source,
                "weight": weight,
                "score": round(score, 1),
                "contribution": round(weight * score, 2),
            }
        )
    if not terms:
        return None

    metrics = snapshot.metrics or {}
    return {
        "meme_name": name,
        "score": round(float(snapshot.score or 0.0), 1),
        "window_days": snapshot.window_days,
        "terms": terms,
        "sum_of_contributions": round(sum(item["contribution"] for item in terms), 2),
        "inputs": {
            "view": metrics.get("view"),
            "interaction": metrics.get("interaction"),
            "video_count": metrics.get("video_count"),
            "creator_peak": metrics.get("creator_peak"),
            "growth": metrics.get("growth"),
            "prev_view": metrics.get("prev_view"),
            "observed_days": metrics.get("observed_days"),
            "window_days_observed": metrics.get("window_days_observed"),
        },
    }


def _hotness_spec(session: Session) -> dict[str, Any]:
    """热度指数的完整口径 + 一个真实算例。

    页面上这块是重点，所以参数一律从 :mod:`app.config.algorithms` 现读，
    不在这里重写一份——阈值改了它跟着变，不会出现「页面写的和算法跑的不是一套」。
    """
    weight_map = {
        "view": HOTNESS_WEIGHTS.view,
        "interaction": HOTNESS_WEIGHTS.interaction,
        "content": HOTNESS_WEIGHTS.content,
        "creator": HOTNESS_WEIGHTS.creator,
        "growth": HOTNESS_WEIGHTS.growth,
    }

    terms: list[dict[str, Any]] = []
    for key, label, source in _HOTNESS_TERMS:
        weight = float(weight_map[key])
        floor, ceiling = HOTNESS_REFERENCE.get(key, (None, None))
        terms.append(
            {
                "key": key,
                "label": label,
                "source": source,
                "weight": weight,
                # growth 是相对量，没有绝对量区间，单独用映射函数
                "kind": "linear" if key == "growth" else "log",
                "floor": floor,
                "ceiling": ceiling,
            }
        )

    expression = " + ".join(f"{item['weight']:.2f}·S_{item['key']}" for item in terms)

    return {
        "expression": f"Hotness = {expression}",
        "weights_total": round(sum(float(weight_map[key]) for key, _, _ in _HOTNESS_TERMS), 2),
        "primary_window": _HOTNESS_PRIMARY,
        "compare_window": _HOTNESS_COMPARE,
        "terms": terms,
        "normalization": {
            "name": "对数区间归一化",
            "formula": "S = 100 × (ln x − ln floor) ÷ (ln ceiling − ln floor)",
            "below_floor": (
                "x ≤ floor 时按 S = 100 × x / floor × 5% 折算，最多给 5 分；x ≤ 0 记 0 分"
            ),
            "why": (
                "绝对量再大也不会让一条爆款视频吃掉整个榜，"
                "绝对量极小的梗也不会因为噪声上榜——两个极端都被压住。"
            ),
        },
        "growth": {
            "score_formula": "S_growth = clamp(100 × (r + 0.30) ÷ 1.50, 0, 100)",
            "rate_formula": "r = 0.35·r_播放 + 0.35·r_讨论 + 0.20·r_视频数 + 0.10·r_UP主数",
            "rate_parts": [
                {"label": "播放", "weight": 0.35},
                {"label": "讨论", "weight": 0.35},
                {"label": "视频数", "weight": 0.20},
                {"label": "UP 主数", "weight": 0.10},
            ],
            "zero_at": GROWTH_SCORE_ZERO,
            "full_at": GROWTH_SCORE_FULL,
            "no_base": (
                "前 7 天没有基数时记 50 分（不奖也不罚）；"
                "从 0 起步视为新出现，按 +100% 计。"
            ),
        },
        "damping": {
            "min_sample": MIN_SAMPLE_VIDEOS,
            "factor": LOW_SAMPLE_DAMPING,
            "rules": [
                f"近 {_HOTNESS_PRIMARY} 天相关视频不足 {MIN_SAMPLE_VIDEOS} 条 → 总分 × {LOW_SAMPLE_DAMPING}",
                f"前后两个 {_HOTNESS_PRIMARY} 天窗口都不足 {MIN_SAMPLE_VIDEOS} 条 → 增长分记 0",
            ],
            "why": (
                "样本太小时，增长率多半是噪声：考古区冒出一条视频不该被算成 +100% 增长。"
                "宁可打折，也不给一个虚高的分数。"
            ),
        },
        "notes": [
            "参与 UP 主分量用「单日去重峰值」而非周累计：采集层给的是当日去重作者数，"
            "而样本里几乎每条视频来自不同作者，逐日累加会退化成「视频数换了个名字」"
            "（实测两者相关系数 0.9997，等于把内容规模按 0.16+0.14 数了两遍）。",
            "互动分量当前实际由评论 + 弹幕构成：B 站逐日搜索只返回播放量/评论/弹幕，"
            "点赞、投币、收藏不在其中（它们落在视频样本上，不进逐日序列）。"
            "这是已知局限，页面不假装它覆盖了全部互动。",
            "所有主量与增长率都在同一条日序列上算，跨梗用同一把尺子；"
            "权重与参考区间集中在 app/config/algorithms.py，改数值只改那一处。",
        ],
        "example": _hotness_example(session),
    }


def _modeling(session: Session, base: dict[str, Any]) -> dict[str, Any]:
    """分析建模：以既有口径为准，不在这里重算一遍算法。"""
    transparency = base.get("transparency") or {}
    stages = [
        {"key": item.get("key"), "label": item.get("label")}
        for item in (base.get("lifecycle_stages") or [])
    ]
    return {
        "window_days": base.get("window_days") or settings.analysis_window_days,
        "hotness_windows": list(_HOTNESS_WINDOWS),
        # 热度公式单独成块：这是全项目的核心算法，页面上给它最大篇幅
        "hotness": _hotness_spec(session),
        "stages": stages,
        "items": [
            {
                "title": "生命周期阶段",
                "detail": transparency.get("lifecycle_algorithm")
                or "基于时间序列与阈值规则判定阶段，不由 LLM 决定。",
                "tag": "时间轴判断",
            },
            {
                "title": "准入规则",
                "detail": transparency.get("certification_rule") or "",
                "tag": "数据准入",
            },
            {
                "title": "热榜闸门",
                "detail": transparency.get("board_gate") or "",
                "tag": "榜单口径",
            },
            {
                "title": "观测闸门（拒绝给结论的边界）",
                "detail": transparency.get("coverage_rule") or "",
                "tag": "可信度",
            },
        ],
        "note": (
            "所有指标都由算法从已发生的数据算出，跨梗用同一把尺子；"
            "AI 只负责把结论说成人话，不参与任何一个数字的计算。"
        ),
    }


def _quality(session: Session, base: dict[str, Any]) -> dict[str, Any]:
    """数据质量：覆盖率、滞后、演示占比，以及几条可自查的结论。"""
    video_total = session.scalar(select(func.count()).select_from(Video)) or 0
    video_real = (
        session.scalar(
            select(func.count()).select_from(Video).where(Video.data_source == "bilibili")
        )
        or 0
    )
    points_total = session.scalar(select(func.count()).select_from(MemeDailyStats)) or 0
    points_observed = (
        session.scalar(
            select(func.count())
            .select_from(MemeDailyStats)
            .where(MemeDailyStats.observed.is_(True))
        )
        or 0
    )

    demo_video = max(video_total - video_real, 0)
    is_demo = bool(base.get("is_demo"))
    lag = base.get("data_lag_days")
    missing_ratio = _ratio(max(points_total - points_observed, 0), points_total)

    coverage_text = "—"
    if points_total:
        coverage_text = f"{points_observed / points_total * 100:.1f}%"

    checks: list[dict[str, Any]] = [
        {
            "label": "数据来源构成",
            "value": f"真实 {video_real} / 演示 {demo_video}",
            "status": "demo" if is_demo else "ok",
            "hint": "演示数据一律显式标注，不冒充真实抓取结果",
        },
        {
            "label": "观测覆盖率",
            "value": coverage_text,
            "status": "warn" if (missing_ratio or 0) > 0.2 else "ok",
            "hint": "已观测点 / 全部序列点；未观测的日子不计入零活动，也不参与趋势",
        },
        {
            "label": "数据滞后",
            "value": "—" if lag is None else f"{lag} 天",
            "status": "warn" if isinstance(lag, int) and lag > 1 else "ok",
            "hint": "采集窗口刻意不含今天：今天没过完，头部样本偏低、增幅会假跌",
        },
        {
            "label": "观测点规模",
            "value": f"{points_observed} / {points_total}",
            "status": "ok",
            "hint": "已观测点 / 全部序列点",
        },
    ]

    return {
        "data_through": base.get("data_through"),
        "data_updated_at": base.get("data_updated_at"),
        "data_lag_days": lag,
        "is_demo": is_demo,
        "demo_ratio": _ratio(demo_video, video_total),
        "missing_ratio": missing_ratio,
        "observed_ratio": _ratio(points_observed, points_total),
        "checks": checks,
    }


def _ai(session: Session, base: dict[str, Any]) -> dict[str, Any]:
    """AI 应用：LLM 在哪一步介入、边界在哪、实际跑得怎么样。"""
    total = session.scalar(select(func.count()).select_from(AIInsight)) or 0
    rows = session.execute(
        select(AIInsight.source, func.count()).group_by(AIInsight.source)
    ).all()
    by_source = {source or "unknown": int(count) for source, count in rows}
    avg_latency = session.scalar(select(func.avg(AIInsight.latency_ms)))
    # 缓存命中率最能说明「有没有在乱花额度」，所以单独给出来
    cache_hits = by_source.get(InsightSource.CACHE, 0)

    return {
        "configured": bool(settings.llm_configured),
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "insight_total": total,
        "by_source": by_source,
        "cache_hit_ratio": _ratio(cache_hits, total),
        "avg_latency_ms": int(avg_latency) if avg_latency is not None else None,
        "role": (
            "LLM 只做一件事：把算法已经算好的结论翻译成人话。"
            "它不能改任何一个数字，也不能改状态——涨/退/稳由算法决定。"
        ),
        "boundaries": [
            "不参与相关性判断：「这条视频讲不讲这个梗」由打分算法决定，不交给模型",
            "不改指标：热度、生命周期、赶潮结论全部先算好，模型只负责措辞",
            "可降级：未配置或调用失败时自动回退到纯算法生成的文案，页面标出来源，不假装是 AI 写的",
            "带缓存：按「数据版本」缓存结果，数据没变就不重复调用，避免空烧额度",
        ],
        "fallback": {
            "rule_based": bool(settings.llm_allow_rule_based_fallback),
            "cache_gap_hours": settings.ai_cache_min_data_gap_hours,
        },
    }


def data_profile_payload(session: Session) -> dict[str, Any]:
    """汇总五段统计。基础数字复用 meta 口径，保证与其它页面说到同一个数。"""
    base = meta_payload(session)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "app_name": base.get("app_name"),
        "version": base.get("version"),
        "environment": base.get("environment"),
        # 与「口径」页同源的计数，避免两个页面各报一个数
        "counts": {
            "certified": base.get("certified_count"),
            "library": base.get("library_count"),
            "gated_out": base.get("gated_out"),
            "candidate": base.get("candidate_count"),
        },
        "source": {
            "platform": "Bilibili",
            "data_source": base.get("data_source"),
            "is_demo": base.get("is_demo"),
            "configured_source": base.get("configured_source"),
        },
        "acquisition": _acquisition(session, base),
        "processing": _processing(session, base),
        "modeling": _modeling(session, base),
        "quality": _quality(session, base),
        "ai": _ai(session, base),
    }
