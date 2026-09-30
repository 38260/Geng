"""梗的分类体系：主题标签（LLM 打标）+ 算法专题（规则生成）。

两类的性质不同，所以分开放：

* **主题标签**回答「这个梗是讲什么的」——职场、抽象、萌宠……
  这是语义判断，交给 LLM 在**固定清单**里选。
* **专题**回答「这批梗凭什么聚在一起」——本月新梗、年度爆款。
  它们有完全客观的规则（时间、热度），由算法直接算，零维护、可复算。

**为什么标签集必须固定在这里，而不是让模型自己起名**：
标签的价值在于「能聚合」。一旦允许自由起名，同一个主题会裂成
「打工人」「职场」「牛马」三个标签，每个都只挂一两个梗，筛选就失去意义了。
所以模型只能从 :data:`MEME_TAGS` 里挑 key，挑了清单外的直接丢弃。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TagSpec:
    """一个主题标签。``hint`` 是给 LLM 的判定依据，不展示给用户。"""

    key: str
    label: str
    emoji: str
    hint: str


# 清单顺序 = 界面上筛选行的显示顺序（把最常见的放前面）
MEME_TAGS: tuple[TagSpec, ...] = (
    TagSpec(
        "workplace",
        "打工人 & 职场",
        "💼",
        "上班、加班、老板、同事、牛马、班味、早八、摸鱼、KPI、打卡、辞职、通勤",
    ),
    TagSpec(
        "abstract",
        "抽象整活",
        "🌀",
        "离谱、整活、抽象、沙雕、鬼畜、解压、无厘头、魔性、精神状态",
    ),
    TagSpec(
        "catchphrase",
        "流行语 & 句式",
        "💬",
        "口头禅、万能句式、谐音、玩梗回答、评论区高频语、固定搭配",
    ),
    TagSpec(
        "campus",
        "校园 & 学生",
        "🎒",
        "上课、军训、考试、开学、宿舍、同学、老师、作业、毕业、早八课",
    ),
    TagSpec(
        "daily",
        "生活日常",
        "🏠",
        "穿搭、旅游、做饭、美食、省钱、居家、生活方式、探店",
    ),
    TagSpec(
        "emotion",
        "情感 & 心理",
        "💗",
        "恋爱、单身、分手、暧昧、情绪、心理、MBTI、治愈、焦虑、社恐",
    ),
    TagSpec(
        "animal",
        "动物 & 萌宠",
        "🐾",
        "猫、狗、宠物、萌宠、野生动物、动物拟人",
    ),
    TagSpec(
        "game",
        "游戏 & 电竞",
        "🎮",
        "游戏、玩家、主播、赛事、操作、段位、开黑、版本、职业选手",
    ),
    TagSpec(
        "anime",
        "二次元",
        "🌸",
        "动漫、番剧、角色、VOCALOID、初音、cosplay、纸片人",
    ),
    TagSpec(
        "music",
        "音乐 & 舞蹈",
        "🎵",
        "BGM、翻唱、旋律、歌曲、舞蹈、卡点、编曲、乐器",
    ),
    TagSpec(
        "nostalgia",
        "古早 & 考古",
        "🗿",
        "早期梗、多年前的老梗、怀旧、已被玩坏、只剩考古向二创",
    ),
    TagSpec(
        "other",
        "其他",
        "📦",
        "确实不属于以上任何一类时才选它",
    ),
)

TAG_KEYS: tuple[str, ...] = tuple(tag.key for tag in MEME_TAGS)
TAG_LABELS: dict[str, str] = {tag.key: tag.label for tag in MEME_TAGS}
TAG_EMOJI: dict[str, str] = {tag.key: tag.emoji for tag in MEME_TAGS}
TAG_HINTS: dict[str, str] = {tag.key: tag.hint for tag in MEME_TAGS}

#: 兜底标签：模型一个都没选、或选的全是清单外的，落到它头上
FALLBACK_TAG = "other"

#: 一个梗最多挂几个标签。太多标签等于没标签——筛选就没法收敛了。
MAX_TAGS_PER_MEME = 3


@dataclass(frozen=True)
class CollectionSpec:
    """算法专题：不需要人工维护，规则写死在这里，每次现算。"""

    key: str
    label: str
    emoji: str
    template: str  # label 里若含 {month} 会被替换成"2026年9月"这类文案
    description: str


COLLECTIONS: tuple[CollectionSpec, ...] = (
    CollectionSpec(
        key="monthly",
        label="{month}新梗速递",
        emoji="🆕",
        template="{month}",
        description="本月首次通过双 UP 认证的梗——刚冒头的那批，趁还没烂大街赶紧看",
    ),
    CollectionSpec(
        key="yearly",
        label="{year}年度现象级爆梗",
        emoji="🏆",
        template="{year}",
        description="本年度热度峰值最高的梗，按峰值排序取前若干名",
    ),
)

COLLECTION_KEYS: tuple[str, ...] = tuple(item.key for item in COLLECTIONS)

#: 「年度现象级爆梗」取前几名。取 10 是因为再多名次就没什么区分度了。
YEARLY_TOP_N = 10
