"""演示数据曲线生成。

目标不是"随便造点数字"，而是让每个梗的时间序列**形状**符合它声明的生命周期原型，
这样算法层才能从原始数据里真的把 萌芽/上升/爆发/平稳/退潮/过气 判出来。
（参考文档 §四十八：不要让所有 Mock 都是 50/60/70/80/90。）

所有随机数使用固定 seed，重复执行 seed 脚本得到完全相同的数据。
"""

from __future__ import annotations


import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.models import MemeDailyStats, Video

DEFAULT_DAYS = 30


# --------------------------------------------------------------------------- #
# 曲线原型：返回长度 days 的"日活跃度倍数"，索引 0 = 最早一天，-1 = 今天
# --------------------------------------------------------------------------- #
def _geom(days: int, start: float, end: float) -> list[float]:
    """几何插值，start/end 为绝对倍数。"""
    if days <= 1:
        return [end]
    ratio = (end / start) ** (1 / (days - 1))
    return [start * (ratio**i) for i in range(days)]


def _rise_then_flat(days: int, peak_idx: int, peak: float, floor: float, decay: float) -> list[float]:
    out: list[float] = []
    for i in range(days):
        if i <= peak_idx:
            out.append(_geom(peak_idx + 1, floor, peak)[i] if peak_idx > 0 else peak)
        else:
            out.append(max(0.02, peak * (decay ** (i - peak_idx))))
    return out


def activity_curve(archetype: str, days: int = DEFAULT_DAYS, seed: int = 0) -> list[float]:
    rng = random.Random(seed)
    if archetype == "sprouting":
        # 长期沉寂 -> 最近一周才冒头，绝对量很小
        head = [0.05] * (days - 9)
        return head + _geom(9, 0.08, 0.55)

    if archetype == "rising":
        return _geom(days, 0.18, 2.4)

    if archetype == "explosive":
        # 短时间快速增长并逼近峰值
        return _geom(days, 0.10, 5.2)

    if archetype == "plateau":
        # 用独立小噪声而不是正弦：正弦会在窗口尾部留下系统性下滑，
        # 让"平稳期"被误判成"退潮期"。
        return [1.0 * rng.uniform(0.94, 1.06) for _ in range(days)]

    if archetype == "receding":
        # 高位 -> 持续下滑
        return _rise_then_flat(days, peak_idx=8, peak=2.6, floor=0.9, decay=0.945)

    if archetype == "obsolete":
        # 早期有一点量，最近两周几乎归零：偶尔冒出一条考古向二创，但成不了气候
        head = _geom(10, 1.4, 0.35)
        tail = [0.55 if i % 5 == 4 else 0.0 for i in range(days - 10)]
        return head + tail

    raise ValueError(f"unknown archetype: {archetype}")


# --------------------------------------------------------------------------- #
# 由活跃度推导每日各项指标
# --------------------------------------------------------------------------- #
_INTERACTION_RATIOS = {
    "like": (0.055, 0.075),
    "coin": (0.016, 0.028),
    "favorite": (0.022, 0.036),
    "reply": (0.010, 0.017),
    "danmaku": (0.026, 0.046),
}


@dataclass
class DailyPoint:
    stat_date: date
    video_count: int
    creator_count: int
    view: int
    like: int
    coin: int
    favorite: int
    reply: int
    danmaku: int

    @property
    def interaction(self) -> int:
        return self.like + self.coin + self.favorite + self.reply + self.danmaku

    @property
    def discussion(self) -> int:
        return self.reply + self.danmaku


def build_daily_points(
    *,
    archetype: str,
    scale: float,
    seed: int,
    days: int = DEFAULT_DAYS,
    end_day: date | None = None,
) -> list[DailyPoint]:
    """scale = 该梗"基准日"的日均播放量级。"""
    rng = random.Random(seed)
    curve = activity_curve(archetype, days, seed)
    end_day = end_day or date.today()
    base_videos = max(2, int(round(scale / 25_000)))
    # 单条视频的单日播放量：保证「当日播放量 = 当日视频数 × 单条播放量」自洽，
    # 过气梗活跃度归零时播放量也归零，而不是出现 0 视频却有播放量的矛盾数据。
    views_per_video = scale / base_videos

    points: list[DailyPoint] = []
    for offset, mult in enumerate(curve):
        stat_day = end_day - timedelta(days=days - 1 - offset)
        video_count = max(0, int(round(base_videos * mult * rng.uniform(0.8, 1.25))))
        if video_count == 0:
            points.append(
                DailyPoint(
                    stat_date=stat_day, video_count=0, creator_count=0,
                    view=0, like=0, coin=0, favorite=0, reply=0, danmaku=0,
                )
            )
            continue

        creator_count = max(1, int(round(video_count * rng.uniform(0.72, 0.95))))
        view = int(video_count * views_per_video * rng.uniform(0.75, 1.25))

        metrics = {"view": view}
        for key, (lo, hi) in _INTERACTION_RATIOS.items():
            metrics[key] = int(view * rng.uniform(lo, hi))

        points.append(
            DailyPoint(
                stat_date=stat_day,
                video_count=video_count,
                creator_count=creator_count,
                **metrics,
            )
        )
    return points


# --------------------------------------------------------------------------- #
# 相关视频样本（详情页"相关视频"与采集器去重/相关性演示）
# --------------------------------------------------------------------------- #
_TITLE_TEMPLATES = [
    "{meme}，这也太上头了",
    "当{alias}遇上鬼畜，完整版{meme}",
    "{meme}是什么梗？一句话讲明白",
    "全网都在玩{meme}，我悟了",
    "{alias}合集：{meme}名场面",
    "第一次看{meme}的人：啊？",
    "{meme}教程，三步学会",
    "盘点那些{meme}的神级二创",
    "{alias}？{meme}？一次说清",
    "{meme}原视频出处来了",
    "室友每天都在{meme}",
    "{meme}×{meme}，双倍快乐",
    "为什么{alias}突然火了",
    "{meme}reaction：笑到停不下来",
    "把{meme}唱成歌会怎样",
    "{alias}挑战，坚持一天不玩梗",
    "深夜emo版{meme}",
    "{meme}，但很治愈",
    "老师讲{alias}，全班绷不住",
    "{meme}的100种用法",
]

_NOISE_AUTHORS = [
    "一只咸鱼干", "熬夜冠军小周", "鬼畜区在逃UP", "阿瓜不吃瓜", "山有木兮",
    "今天也想摸鱼", "电子咸鱼王", "橘子汽水铺", "深夜剪辑室", "小陈不废话",
    "摸鱼研究所", "嗑瓜子的猫", "不正经研究所", "老张的录像带", "气泡水加冰",
]


def _bvid(rng: random.Random, idx: int) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    body = "".join(rng.choice(alphabet) for _ in range(9))
    return f"BV1{body}{idx % 10}"


def build_sample_videos(
    *,
    meme_name: str,
    aliases: tuple[str, ...],
    keywords: tuple[str, ...],
    points: list[DailyPoint],
    scale: float,
    seed: int,
    count: int = 12,
) -> list[Video]:
    """生成"搜索结果样本"：多数强相关，少量擦边/无关，用于验证相关性过滤。

    发布日期只在「当日有视频产出」的那些天里按当日视频数加权抽样，
    保证视频样本与每日聚合数据不互相矛盾。
    """
    rng = random.Random(seed + 7)
    active = [p for p in points if p.video_count > 0]
    if not active:
        return []
    weights = [p.video_count for p in active]
    total = sum(weights) or 1.0
    alias = (aliases or (meme_name,))[0]

    videos: list[Video] = []
    for i in range(count):
        # 三类样本：强相关 / 只命中别名（边界样本）/ 完全无关。
        # 注意：这里**不预先写死 relevance_score**，相关性一律由匹配算法算出来，
        # 这样演示数据同样会经过真实的过滤逻辑。
        kind = i % 10
        if kind == 9:
            title = rng.choice(
                [
                    "本周热门视频合集，看看有没有你认识的",
                    "随机挑战：一天不说网络用语",
                    "游戏实况第 12 期：这关有点难",
                    "生活区 vlog｜周末去了趟郊外",
                ]
            )
            description = "演示数据：与梗无关的对照样本，用于验证相关性过滤"
            matched: list[str] = []
        elif kind in (3, 7) and len(alias) > 1:
            title = f"{alias}？我一开始也没看懂"
            description = "演示数据：只命中别名、不含关键词的边界样本"
            matched = [alias]
        else:
            template = _TITLE_TEMPLATES[i % len(_TITLE_TEMPLATES)]
            title = template.format(meme=meme_name, alias=alias)
            description = f"{meme_name}｜{'、'.join(keywords) or 'B站梗'} 相关二创内容（演示数据）"
            matched = [meme_name]

        pick = rng.random() * total
        acc = 0.0
        chosen = active[-1]
        for point, weight in zip(active, weights):
            acc += weight
            if pick <= acc:
                chosen = point
                break

        pub_dt = datetime(
            chosen.stat_date.year, chosen.stat_date.month, chosen.stat_date.day,
            rng.randint(8, 23), rng.choice([0, 7, 15, 23, 36, 48]),
        )
        per_video = (chosen.view / chosen.video_count) if chosen.video_count else scale / 10
        views = max(120, int(per_video * rng.uniform(0.15, 0.85)))
        videos.append(
            Video(
                bvid=_bvid(rng, i),
                title=title,
                description=description,
                author=rng.choice(_NOISE_AUTHORS),
                publish_time=pub_dt,
                crawl_time=datetime.now(),
                duration_seconds=rng.randint(18, 620),
                view=views,
                like=int(views * rng.uniform(0.05, 0.08)),
                coin=int(views * rng.uniform(0.012, 0.03)),
                favorite=int(views * rng.uniform(0.015, 0.035)),
                reply=int(views * rng.uniform(0.008, 0.016)),
                danmaku=int(views * rng.uniform(0.02, 0.05)),
                relevance_score=0.0,  # 由 app.analytics.relevance 计算后回填
                matched_terms=matched,
                data_source="mock",
            )
        )
    return videos


def stats_from_points(meme_id: int, points: list[DailyPoint]) -> list[MemeDailyStats]:
    return [
        MemeDailyStats(
            meme_id=meme_id,
            stat_date=p.stat_date,
            video_count=p.video_count,
            creator_count=p.creator_count,
            view=p.view,
            like=p.like,
            coin=p.coin,
            favorite=p.favorite,
            reply=p.reply,
            danmaku=p.danmaku,
            data_source="mock",
        )
        for p in points
    ]
