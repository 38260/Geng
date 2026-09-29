# =========================================================================== #
# 12 — falsification experiment
# =========================================================================== #
s = add()
header(s, "证伪实验", "我先立了一个判据，然后拿 31 个真实样本把它推翻了",
       sub="如果一页 PPT 只能留一页，我留这页。")
card(s, MARGIN, BODY_TOP, 6.05, 1.30, fill=NAVY_SOFT, line=None)
blk(s, MARGIN + 0.30, BODY_TOP + 0.18, 5.45, 0.96, [
    dict(text="被检验的假设（也是我一开始的想法）", size=11, color=NAVY,
         bold=True),
    dict(text="「解说视频播放量破百万的梗，才值得花成本去做。」",
         size=14.5, color=INK, bold=True, font=DISPLAY, space_before=5),
], warn="s12-h")
if os.path.exists(os.path.join(ASSET, "scatter.png")):
    pic(s, os.path.join(ASSET, "scatter.png"), MARGIN, BODY_TOP + 1.48, w=5.60)
blk(s, 6.94, BODY_TOP, 5.55, 3.06, [
    dict(text="检验结果", size=11.5, color=CORAL, bold=True),
    dict(text="Pearson r = +0.40（p = 0.028）", size=16, color=INK, bold=True,
         font=MONO, space_before=6),
    dict(text="Spearman ρ = +0.29（p = 0.12，不显著）", size=13, color=GREY,
         font=MONO, space_before=3),
    dict(text="R² ≈ 0.16，n = 31", size=12, color=GREY, font=MONO,
         space_before=3),
    dict(text="结论：解说播放量只能解释热度方差的约 16%。",
         size=12.5, color=INK, bold=True, space_before=10, line_spacing=1.3),
    dict(text="反例同时存在，而且方向完全相反：", size=11.5, color=INK,
         space_before=10),
    dict(text="· 「闪身步」解说 64.6 万 → 该梗热度 76.8，全站第一", size=11,
         color=CORAL, space_before=5, line_spacing=1.3),
    dict(text="· 「宗主第二招」解说 160.7 万 → 该梗热度 0.0", size=11,
         color=GOLD_DEEP, space_before=3, line_spacing=1.3),
    dict(text="所以这个指标可以用来做采集成本的预算筛，不能当准入判据。",
         size=11.5, color=INK, bold=True, space_before=10, line_spacing=1.3),
], warn="s12-r")
band(s, BODY_TOP + 3.26, 1.24,
     "解说播放量衡量的是那个账号自己的粉丝盘，而且是发布那一刻的存量——不是梗的热度。",
     fill=CORAL_SOFT, size=12.5,
     extra="这件事教会我一件事：先立一个能被数据推翻的判据，再去检验它。"
           "被推翻不丢人，拿一个没检验过的直觉当设计依据才丢人。")
fin(s)
notes(s, "这页要讲出「我自己推翻了自己」的口气，不要念数字。\n"
         "重点说反例：解说只有 64.6 万的梗热度第一，解说 160.7 万的梗热度是 0。\n"
         "如果老师问「那不显著为什么不干脆说没关系」：Pearson 显著、Spearman 不显著，"
         "说明有弱的单调关系但被离群点拉扯，所以结论是「能当成本筛、不能当准入门槛」。\n"
         "被追问样本量：n = 31 是当时上热榜的梗数，确实偏小，这一点写在局限里。")

# =========================================================================== #
# 13 — innovation
# =========================================================================== #
s = add()
header(s, "创新点", "三件事我做得跟别人不一样",
       sub="不是「用了什么新技术」，是「换了什么研究对象、换了什么口径、多给了什么输出」。")
items = [
    ("01", "对象创新", CORAL, CORAL_SOFT,
     "把「梗」从单条内容，提升成跨创作者聚合的时间序列实体。",
     ["一条视频的热度是它的播放量；一个梗的热度要跨几十上百条视频聚合",
      "聚合之后才谈得上「它现在走到哪一段」——单条内容没有生命周期，只有发布曲线"]),
    ("02", "准入创新", NAVY, NAVY_SOFT,
     "用两位解说 UP 主的真实投稿作存在性证明，并集准入 + 认证降级为标签。",
     ["覆盖率提升 6.4 倍（交集 8 → 并集 51），可审计性没损失：每条证据都是真 BV 号",
      "「双 UP 认证」从闸门变成卡片上的可信度标签，信息不丢、门槛不误杀"]),
    ("03", "输出创新", GOLD_DEEP, RGBColor(0xFF, 0xF7, 0xE3),
     "不止报热度，还给带置信度的赶梗时机判断，并把口径印在产品上。",
     ["抽样口径、统计滞后、认证强度、观测覆盖度，全部显示在界面上，可被质疑与复算",
      "算法定状态、大模型只翻译——AI 是单点故障时，产品闭环不会断"]),
]
y = BODY_TOP
for num, title, ac, bg, lead, subs in items:
    card(s, MARGIN, y, 12.09, 1.34, fill=WHITE, line=LINE)
    rect(s, MARGIN, y, 0.055, 1.34, fill=ac)
    blk(s, MARGIN + 0.32, y + 0.20, 0.60, 0.90, [
        dict(text=num, size=22, color=ac, bold=True, font=MONO)], warn="s13-num")
    blk(s, MARGIN + 1.02, y + 0.16, 3.40, 1.04, [
        dict(text=title, size=13.5, color=INK, bold=True),
        dict(text=lead, size=10.5, color=GREY, space_before=5, line_spacing=1.26),
    ], warn="s13-lead")
    blk(s, MARGIN + 4.62, y + 0.16, 7.20, 1.04,
        [dict(text="· " + t, size=10.5, color=INK, space_before=5 if i else 0,
              line_spacing=1.26) for i, t in enumerate(subs)], warn="s13-sub")
    y += 1.34 + 0.12
band(s, y + 0.02, 0.74,
     "还有一件不算创新、但我认为同样重要的事：把「不知道」做成一个合法输出。",
     fill=NAVY_SOFT, color=NAVY, size=12, exsize=0)
fin(s)
notes(s, "每条创新都用「跟谁比、差了多远」来讲，不要空说创新。\n"
         "对象创新是根：没有跨创作者聚合，后面两个都无从谈起。\n"
         "最后那句「把不知道做成合法输出」是本课题的态度，也是跟一堆"
         "「AI 什么都敢说」的课程作业最大的区别。")

# =========================================================================== #
# 14 — limits & risks
# =========================================================================== #
s = add()
header(s, "局限与风险", "我知道它哪里不准，而且写下来了",
       sub="主动交代局限不是减分项——藏着才会在答辩现场被拆。")
rows = [
    ("脉冲型梗会被误判", "琵琶曲 30 天只有 4 天有内容，却播了 3,976 万，规则容易判成过气",
     "上榜层已用「近 7 天头部播放下限」兜底；后续为脉冲型单独建模", CORAL),
    ("残值会被误判成萌芽", "「omg你吓到了我」近 7 天只剩 3,770 次播放，却落在萌芽期",
     "给萌芽期补最低活跃度约束（已列入下一步）", GOLD_DEEP),
    ("上游接口受风控", "匿名只能稳定取到账号最近约 150~400 条投稿，深翻页被 -352 / 412 挡住",
     "退避重试 + 索引缓存 + 缺口如实报告；可选 Cookie 增强核验", NAVY),
    ("抽样口径的天花板", "当日头部 20 条合计，不是全站绝对量；一个全靠小爆款堆起来的梗会被低估",
     "界面与论文都写明口径；计划做 20 → 10 / 50 的敏感性分析", NAVY),
    ("已知未修的口径偏差", "view 是「该日发布 cohort 的累计播放」，老日子多攒了十几天，序列天生向今天下坡",
     "年龄中性的替代量是 search_total；改这个要重排全部榜单，先修可信度、暂不动公式", GREY),
]
y = BODY_TOP
for title, prob, plan, ac in rows:
    card(s, MARGIN, y, 12.09, 0.94, fill=WHITE, line=LINE)
    rect(s, MARGIN, y, 0.055, 0.94, fill=ac)
    blk(s, MARGIN + 0.32, y + 0.13, 2.70, 0.68, [
        dict(text=title, size=11.5, color=ac, bold=True, line_spacing=1.24)],
        warn="s14-t")
    blk(s, MARGIN + 3.15, y + 0.13, 4.30, 0.68, [
        dict(text=prob, size=10, color=INK, line_spacing=1.24)], warn="s14-p")
    blk(s, MARGIN + 7.62, y + 0.13, 4.20, 0.68, [
        dict(text="→ " + plan, size=10, color=GREY, line_spacing=1.24)],
        warn="s14-pl")
    y += 0.94 + 0.075
band(s, y + 0.03, 0.72,
     "伦理与合规：只取公开元数据（标题、播放、点赞、弹幕数、封面链接），不登录、不绕登录墙、"
     "不存用户隐私；图片引用外链而非转存，频控单梗一轮约 30 次查询。",
     fill=NAVY_SOFT, color=NAVY, size=10.5, exsize=0)
fin(s)
notes(s, "这一页的作用是「先自己拆一遍」，让老师没有可拆的地方。\n"
         "第 5 条要主动说：这是一个已知的口径偏差，没修，原因是改它会重排全部榜单与赶梗结论，"
         "我选择先把可信度修好。老师会尊重这个取舍。\n"
         "顺手可以提一个实测细节：B 站图床带 Referer 会 403，不带才 200，"
         "所以前端 img 必须 no-referrer——这种细节比形容词有用。")

# =========================================================================== #
# 15 — schedule
# =========================================================================== #
s = add()
header(s, "进度安排", "接下来六周，每周都有一个能被检查的交付物",
       sub="不写「继续完善」这种话——每一周都能问「东西在哪」。")
weeks = [
    ("第 1-2 周", "口径收尾", ["脉冲型梗单独建模", "萌芽期补最低活跃度约束",
                            "上榜层回归测试"], CORAL),
    ("第 3 周", "数据与调度", ["增量刷新 + 系统计划任务", "17 个采空梗用别名兜底再采一轮",
                            "每日自动更新的数据集"], NAVY),
    ("第 4 周", "用户实验", ["20 人对照：看热搜 vs 看本系统", "选题准确率 + 主观有用性",
                          "实验数据与分析"], GOLD_DEEP),
    ("第 5 周", "一致性检验", ["阶段判定混淆矩阵", "热度与人工标注的 Spearman 相关",
                            "门槛消融实验"], NAVY),
    ("第 6 周", "成稿", ["论文撰写", "代码与可复现说明", "数据集整理"], GREY),
]
x = MARGIN
NCOL = 5
CW = (CONTENT_W - (NCOL - 1) * 0.16) / NCOL
for wk, title, subs, ac in weeks:
    card(s, x, BODY_TOP, CW, 2.86, fill=WHITE, line=LINE)
    rect(s, x, BODY_TOP, CW, 0.075, fill=ac)
    blk(s, x + 0.22, BODY_TOP + 0.26, CW - 0.44, 2.44, [
        dict(text=wk, size=12, color=ac, bold=True),
        dict(text=title, size=14, color=INK, bold=True, space_before=6),
    ] + [dict(text="· " + t, size=10, color=GREY, space_before=8,
              line_spacing=1.26) for t in subs], warn="s15-%s" % wk)
    x += CW + 0.16
band(s, BODY_TOP + 3.04, 1.52,
     "第 4、5 周这两块，是把「我觉得准」换成「我能证明它准」的关键。",
     fill=CORAL_SOFT, size=13,
     extra="诚实说明当前状态：用户实验、混淆矩阵、权重消融、门槛消融这四项都还没跑，"
           "所以本阶段我给不出「系统有多准」的结论，只能给出「系统是怎么算的」。"
           "这也是开题该有的样子——如果现在什么都做完了，开题就没有意义了。")
fin(s)
notes(s, "进度表的作用是让老师知道后面会发生什么、什么时候能检查。\n"
         "主动说清楚：一致性检验和用户实验还没做，所以现在没有「准确率」这种数字。\n"
         "如果老师建议调整顺序，记下来当场回应——这是开题，本来就是来收意见的。")

# =========================================================================== #
# 16 — anticipated questions
# =========================================================================== #
s = add()
rect(s, 0, 0, SW, SH, fill=WHITE)
rect(s, 0, 0, 0.22, SH, fill=CORAL)
simple(s, MARGIN + 0.10, 0.62, 11.8, 0.32,
       [dict(text="准备被问的", size=13, color=CORAL, bold=True)], warn="s16-k")
tb = textbox(s, MARGIN + 0.10, 0.94, 11.8, 0.72)
para(tb.text_frame, True, text="我猜您会问这四个问题", size=34, color=INK,
     bold=True, font=DISPLAY, line_spacing=1.0)
qa = [
    ("数据是抓的，接口一抖结论不就变了？",
     "这正是我踩坑最多的地方：逐日区间查询解决假增长、同日取更优观测解决抽样抖动、"
     "observed 标记解决空窗、弱别名规则解决污染。四条都在第 11 页。"),
    ("每天只取头部 20 条，能代表真实热度吗？",
     "不能代表全站绝对量，但足以支撑跨梗跨日的可比排序。代价我承认："
     "一个全靠小爆款堆起来的梗会被低估，论文里会做 20 → 10 / 50 的敏感性分析。"),
    ("权重 0.25/0.25/0.20/0.16/0.14 会不会太主观？",
     "初始权重来自设计判断。约束它的是两件事：对数区间归一化让量级不吃掉权重；"
     "样本不足时不外推。权重消融与人工标注一致性检验列在第 15 周计划里。"),
    ("大模型在里面做什么？它胡说怎么办？",
     "只把算法已经定好的结论翻译成人话。返回的 status 与算法不一致时以算法为准，"
     "出现「预计」「未来 7 天」这类预测口吻直接丢弃；没 Key 时退回算法文案，闭环不断。"),
]
ROW_W = CONTENT_W - 0.10
y = 1.72
for q, a in qa:
    card(s, MARGIN + 0.10, y, ROW_W, 1.14, fill=CANVAS, line=LINE)
    rect(s, MARGIN + 0.10, y, 0.05, 1.14, fill=CORAL)
    blk(s, MARGIN + 0.42, y + 0.15, ROW_W - 0.64, 0.42,
        [dict(text="Q " + q, size=13, color=INK, bold=True)], warn="s16-q")
    blk(s, MARGIN + 0.42, y + 0.58, ROW_W - 0.64, 0.48,
        [dict(text="A " + a, size=10.5, color=GREY, line_spacing=1.24)],
        warn="s16-a")
    y += 1.14 + 0.09
simple(s, MARGIN + 0.10, 6.62, 11.60, 0.34,
       [dict(text="提前把答案写在纸上，比现场现编一个数字安全得多。",
             size=11.5, color=GREY)], warn="s16-end")
notes(s, "这一页可以不放出来，作为备用页留在放映顺序最后。\n"
         "如果现场被问到其中任何一个，直接翻到这里，照着念 A 那一行就行。\n"
         "万一被问到没准备的，老实说「这是下一步」，不要现编数字——"
         "这一页存在的意义就是让「现编」变得没必要。")
