"""演示梗库（Mock catalogue）。

说明：
* 这里的梗名称/别名是真实存在于 B 站梗文化中的说法，但**所有数值都是演示数据**，
  由 :mod:`app.mock.curves` 按生命周期原型生成，页面上会明确标注「演示数据」。
* ``certification`` 决定该梗能否进入正式梗库：
    both    -> 梗百科 + 梗指南 都介绍过（certified=True）
    enc     -> 只有梗百科介绍过（candidate，禁止进入分析）
    guide   -> 只有梗指南介绍过（candidate，禁止进入分析）
    none    -> 用户/运营提交但尚未认证（candidate）
* ``scale`` 是"日均播放量级"，用来控制该梗的量级大小；``archetype`` 决定曲线形状。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemeSpec:
    name: str
    archetype: str                 # sprouting / rising / explosive / plateau / receding / obsolete
    scale: float                   # 日均播放量级
    description: str
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    certification: str = "both"    # both / enc / guide / none
    emoji: str = "🎬"
    color: str = "#FFE9E4"


# 目标：首页热榜前五与参考图一致（电子木鱼 / 狗都不谈恋爱 / 我是大学生 / 阿巴阿巴 / 啊对对对）
MEME_CATALOGUE: tuple[MemeSpec, ...] = (
    # ---------------------------- 🔥 爆发期 ---------------------------- #
    MemeSpec("电子木鱼", "explosive", 260_000, "敲电子木鱼、赛博积功德的解压玩法，衍生出大量整活视频与小游戏。",
             ("赛博木鱼", "电子功德"), ("木鱼", "功德", "赛博"), emoji="🪵", color="#FFE9D6"),
    MemeSpec("我不是黄豆", "explosive", 190_000, "用变黄表情包自嘲「我不是黄豆」的二次创作潮，常配魔性 BGM。",
             ("黄豆", "变黄了"), ("黄豆", "表情包"), emoji="🫘", color="#FFF3C4"),
    MemeSpec("哈基米", "rising", 175_000, "源自猫咪视频的洗脑旋律，被大量剪辑成萌宠与整活混剪。",
             ("哈基米你呀", "hajimi"), ("哈基米", "猫", "洗脑"), emoji="🐱", color="#FFE4EF"),
    MemeSpec("泼天的富贵", "rising", 150_000, "形容突然降临的流量与好运，常用于品牌与素人爆火叙事。",
             ("接住泼天富贵", "泼天富贵"), ("富贵", "流量"), emoji="💰", color="#FFF0BF"),
    MemeSpec("这很难评", "plateau", 132_000, "面对离谱内容时的万能回应句式，衍生出大量反应向视频。",
             ("我祝他成功吧",), ("难评",), emoji="🤔", color="#E7EEFF"),
    MemeSpec("无敌是多么寂寞", "rising", 121_000, "配合夸张战绩的卡点梗，游戏区与舞蹈区同时使用。",
             ("无敌",), ("寂寞", "卡点"), emoji="🕺", color="#E4F6FF"),

    # ---------------------------- 📈 上升期 ---------------------------- #
    MemeSpec("狗都不谈恋爱", "rising", 96_000, "单身向自嘲句式，「狗都不谈恋爱，我要谈」的反转结构正在扩散。",
             ("狗都不谈",), ("单身", "自嘲"), emoji="🐶", color="#FFE2D1"),
    MemeSpec("我是大学生", "rising", 82_000, "以「我是大学生」开头的身份反转叙事，用于解释各种离谱行为。",
             ("大学生", "学姐好"), ("大学生", "校园"), emoji="🎓", color="#E6F0FF"),
    MemeSpec("军训好热", "rising", 70_000, "开学季军训吐槽合集，配合晒伤与拉歌场景的二创。",
             ("军训", "教官", "拉歌"), ("军训", "开学"), emoji="☀️", color="#FFF1CC"),
    MemeSpec("这也太刑了", "rising", 61_000, "「太行了」的谐音变形，用来形容擦边到违法边缘的离谱操作。",
             ("太刑了", "刑不刑"), ("刑", "谐音"), emoji="⚖️", color="#EDE7FF"),
    MemeSpec("班味", "rising", 55_000, "打工人身上洗不掉疲惫气质的统称，衍生出「去班味」穿搭与生活方式内容。",
             ("去班味", "一身班味"), ("打工人", "职场"), emoji="💼", color="#E8F1EC"),
    MemeSpec("质疑理解成为", "rising", 48_000, "「质疑他、理解他、成为他」三段式句式，用于描述成长的回旋镖。",
             ("质疑他理解他成为他",), ("回旋镖", "成长"), emoji="🔄", color="#E9F6FF"),
    MemeSpec("情绪价值", "rising", 44_000, "从情感博主术语泛化为对任何让人舒服的人事物的评价标准。",
             ("提供情绪价值",), ("情绪", "价值"), emoji="💗", color="#FFE7F0"),
    MemeSpec("i人e人", "rising", 41_000, "MBTI 内外向缩写被彻底梗化，用于给一切行为分类。",
             ("i人", "e人", "MBTI"), ("MBTI", "社恐"), emoji="🫂", color="#EAF7EE"),

    # ---------------------------- 🌱 萌芽期 ---------------------------- #
    MemeSpec("工位搭子", "sprouting", 12_000, "指同一层办公室互相带饭的同事关系，刚从小范围生活区冒头。",
             ("搭子", "饭搭子"), ("职场", "生活"), emoji="🍱", color="#FFF4E0"),
    MemeSpec("反向旅游", "sprouting", 9_500, "刻意避开热门城市的小城旅行内容，刚出现集中投稿迹象。",
             ("小城旅行",), ("旅游", "小众"), emoji="🧭", color="#E7F6F1"),
    MemeSpec("早八人", "sprouting", 8_200, "对早上八点上课/上班人群的自称，配合痛苦起床镜头。",
             ("早八",), ("校园", "作息"), emoji="⏰", color="#EEF0FF"),
    MemeSpec("松弛感家长", "sprouting", 6_800, "从「松弛感」派生的育儿向表达，样本量还很小。",
             ("松弛感",), ("育儿",), emoji="🌿", color="#EAF7EC"),

    # ---------------------------- 🌊 平稳期 ---------------------------- #
    MemeSpec("阿巴阿巴", "plateau", 39_000, "装傻失语的拟声表达，长期稳定出现在鬼畜与萌宠区。",
             ("阿巴",), ("拟声", "装傻"), emoji="🗿", color="#EDEDED"),
    MemeSpec("夏天的风", "plateau", 33_000, "老歌翻唱与夏日氛围混剪的固定 BGM，热度稳定。",
             ("夏天的风 翻唱",), ("夏日", "音乐"), emoji="🍃", color="#E3F5EA"),
    MemeSpec("发疯文学", "plateau", 30_000, "以夸张崩溃语气表达诉求的文体，已成语境通用工具。",
             ("发疯",), ("文学", "情绪"), emoji="🌀", color="#F3E8FF"),
    MemeSpec("松弛感", "plateau", 27_000, "形容不费力却好看的状态，穿搭与生活方式区常驻标签。",
             ("很松弛",), ("穿搭", "生活"), emoji="🌊", color="#E5F3FF"),
    MemeSpec("神人", "plateau", 24_000, "对离谱行为者的中性称呼，评论区高频。",
             ("神人", "太神了"), ("离谱",), emoji="🙇", color="#FFF6DE"),
    MemeSpec("纯爱战士", "plateau", 21_000, "宣言只接受纯粹爱情表达的自称，常与 NTR 剧情对立使用。",
             ("纯爱",), ("恋爱", "宣言"), emoji="🛡️", color="#FFE9EE"),

    # ---------------------------- 📉 退潮期 ---------------------------- #
    MemeSpec("啊对对对", "receding", 18_000, "敷衍式认同的万能回复，热度已从峰值明显回落。",
             ("对对对",), ("敷衍", "口头禅"), emoji="🙄", color="#E9E9E9"),
    MemeSpec("你个老6", "receding", 16_000, "游戏区衍生出的「老六」骂梗，二创量持续下滑。",
             ("老六",), ("游戏", "阴人"), emoji="🎮", color="#EAEAEA"),
    MemeSpec("遥遥领先", "receding", 15_000, "发布会口头禅出圈后进入长尾，新增内容增速转负。",
             ("领先",), ("发布会", "数码"), emoji="📱", color="#EFEFEF"),
    MemeSpec("公主请上车", "receding", 12_500, "霸总式接人短句，季节性热度已退。",
             ("王子请下车",), ("霸总", "恋爱"), emoji="🚗", color="#F2F2F2"),
    MemeSpec("多巴胺穿搭", "receding", 11_000, "高饱和配色穿搭潮，已过峰值进入退潮。",
             ("多巴胺",), ("穿搭", "配色"), emoji="🌈", color="#F0F0F0"),
    MemeSpec("你这背景太假了", "receding", 9_800, "景区实拍与修图反差吐槽句式，热度回落明显。",
             ("背景太假",), ("修图", "景区"), emoji="🏞️", color="#F1F1F1"),

    # ---------------------------- 🪦 过气 ---------------------------- #
    MemeSpec("挖呀挖", "obsolete", 4_200, "儿歌手势舞全网刷屏后的长尾，几乎无新增内容。",
             ("在小小的花园里面",), ("儿歌", "手势舞"), emoji="🌱", color="#EDEDED"),
    MemeSpec("鸡你太美", "obsolete", 3_600, "早期篮球舞蹈梗，只剩考古向二创。",
             ("只因", "唱跳rap篮球"), ("考古",), emoji="🏀", color="#EDEDED"),
    MemeSpec("你干嘛哎哟", "obsolete", 3_100, "鬼畜音频梗，已退出日常表达。",
             ("你干嘛",), ("鬼畜",), emoji="🎤", color="#EDEDED"),
    MemeSpec("听我说谢谢你", "obsolete", 2_600, "手势舞感恩梗，已被玩坏并归档。",
             ("谢谢你",), ("手势舞",), emoji="🙏", color="#EDEDED"),
    MemeSpec("泰裤辣", "obsolete", 2_100, "「太酷啦」谐音梗，热度完全消散。",
             ("太酷啦",), ("谐音",), emoji="😎", color="#EDEDED"),
    MemeSpec("特种兵式旅游", "obsolete", 1_800, "极限打卡式旅行叙事，已归于平静。",
             ("特种兵旅游",), ("旅行", "打卡"), emoji="🥾", color="#EDEDED"),

    # ------------------- 未通过双 UP 认证（不得进入分析） ------------------- #
    MemeSpec("新梗观察A", "rising", 20_000, "只有梗百科介绍过，等待梗指南认证，因此不得进入正式梗库。",
             ("观察A",), ("测试",), certification="enc", emoji="🧪", color="#E8F5E9"),
    MemeSpec("新梗观察B", "plateau", 15_000, "只有梗指南介绍过，属于候选梗。",
             ("观察B",), ("测试",), certification="guide", emoji="🧪", color="#E3F2FD"),
    MemeSpec("网友投稿梗", "explosive", 40_000, "尚无任何 UP 认证，仅有投稿记录。",
             ("投稿",), ("待审",), certification="none", emoji="📮", color="#FFF3E0"),
)

# 参考图首页热榜前五，用于视觉验收时对齐排序
REFERENCE_TOP5 = ["电子木鱼", "狗都不谈恋爱", "我是大学生", "阿巴阿巴", "啊对对对"]
REFERENCE_FEATURED = ["我不是黄豆", "军训好热", "这也太刑了", "夏天的风"]

ALL_STAGES = ("sprouting", "rising", "explosive", "plateau", "receding", "obsolete")


def stage_counts() -> dict[str, int]:
    counts: dict[str, int] = {stage: 0 for stage in ALL_STAGES}
    for spec in MEME_CATALOGUE:
        if spec.certification == "both":
            counts[spec.archetype] = counts.get(spec.archetype, 0) + 1
    return counts


def catalogue() -> list[MemeSpec]:
    return list(MEME_CATALOGUE)


_SPEC_INDEX: dict[str, MemeSpec] = {spec.name: spec for spec in MEME_CATALOGUE}


def spec_for(name: str) -> MemeSpec | None:
    return _SPEC_INDEX.get(name)
