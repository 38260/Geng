# =========================================================================== #
# 11 — limitations and honest accounting
# =========================================================================== #
s = add()
header(s, "局限与未解问题", "四件我到现在也没解决的事",
       sub="第 4 条是一个已知的口径偏差，我没修——这是一个取舍，不是疏忽。")
rows = [
    ("脉冲型梗会被误判", "琵琶曲 30 天只有 4 天有内容，却播了 3,976 万，规则容易判成过气",
     "上榜层用「近 7 天头部播放下限」兜底；后续为脉冲型单独建模", CORAL),
    ("残值会被误判成萌芽", "「omg你吓到了我」近 7 天只剩 3,770 次播放，却落在萌芽期",
     "给萌芽期补最低活跃度约束（下一步）", GOLD_DEEP),
    ("样本量偏小", "n = 31 的证伪实验、71 个入池梗，做曲线拟合仍然不宽裕",
     "继续每日增量积累；等样本变大后复算全部结论", NAVY),
    ("已知未修的口径偏差", "view 是「该日发布 cohort 的累计播放」，老日子多攒了十几天，"
                       "序列天生向今天下坡，7 天对 7 天的增长率偏高估跌",
     "年龄中性的替代量是 search_total（实测上周 789/天 vs 这周 750/天）；"
     "改它会重排全部榜单与赶梗结论，2026-09-28 决定先修可信度、暂不动公式", GREY),
]
y = BODY_TOP
for title, prob, plan, ac in rows:
    h = 1.06 if len(prob) < 60 else 1.24
    card(s, MARGIN, y, 12.09, h, fill=WHITE, line=LINE)
    rect(s, MARGIN, y, 0.055, h, fill=ac)
    blk(s, MARGIN + 0.32, y + 0.14, 2.65, h - 0.26,
        [dict(text=title, size=11.5, color=ac, bold=True, line_spacing=1.24)],
        warn="d11-t")
    blk(s, MARGIN + 3.10, y + 0.14, 4.35, h - 0.26,
        [dict(text=prob, size=10, color=INK, line_spacing=1.24)], warn="d11-p")
    blk(s, MARGIN + 7.60, y + 0.14, 4.22, h - 0.26,
        [dict(text="→ " + plan, size=10, color=GREY, line_spacing=1.24)],
        warn="d11-pl")
    y += h + 0.09
band(s, y + 0.02, 0.76,
     "还有两件小事也记在这里：B 站风控下匿名只能取到账号最近约 150~400 条投稿；"
     "字幕这一档需要 Cookie，所以「字幕原文摘录」现在可能是空的——那是如实标注。",
     fill=NAVY_SOFT, color=NAVY, size=10.5, exsize=0)
fin(s)
notes(s, "主动拆自己，让老师没有可拆的地方。\n"
         "第 4 条要讲出取舍的口气：我知道它偏，但改它会推翻前面所有结论，"
         "所以先修可信度——这是一个工程判断，不是没想到。\n"
         "如果老师认为应该改：接受，并说明改动范围（全部榜单与赶梗结论需重算）。")

# =========================================================================== #
# 12 — future work
# =========================================================================== #
s = add()
header(s, "下一步", "如果继续做，我会按这个顺序补",
       sub="顺序不是随意的：先补「能不能信」，再补「准不准」，最后才扩范围。")
items = [
    ("补可信度", CORAL, ["把第 4 条口径偏差的替代量（search_total）跑一遍对照，"
                     "看排名会怎么变",
                     "把四块空白实验里的观测覆盖率与快照回填做成常规回归测试"]),
    ("补准确度", NAVY, ["阶段判定混淆矩阵 + 权重消融 + 抽样口径敏感性分析",
                     "用户实验：20 人对照「看热搜」与「看本系统」的选题表现"]),
    ("扩观测面", GOLD_DEEP, ["配 BILI_COOKIE 打通 UP 主空间与字幕轨，"
                        "把「字幕原文摘录」这一档填满",
                        "用 search_total 与互动量构造年龄中性指标，替代累计播放口径"]),
    ("扩研究对象", GREEN, ["从「梗」扩到「梗的类型」：看动作梗、台词梗、"
                      "形象梗的衰减曲线是否不同",
                      "在 B 站之外只加一个平台做对照，验证这套口径可迁移"]),
]
x = MARGIN
NCOL = 4
GAP = 0.19
CW = (CONTENT_W - (NCOL - 1) * GAP) / NCOL
for title, ac, subs in items:
    card(s, x, BODY_TOP, CW, 2.60, fill=WHITE, line=LINE)
    rect(s, x, BODY_TOP, CW, 0.075, fill=ac)
    blk(s, x + 0.24, BODY_TOP + 0.26, CW - 0.48, 2.20,
        [dict(text=title, size=14, color=ac, bold=True)] +
        [dict(text="· " + t, size=10, color=GREY, space_before=9,
              line_spacing=1.26) for t in subs], warn="d12")
    x += CW + GAP
band(s, BODY_TOP + 2.80, 1.72,
     "一个我自己最想知道的后续问题：梗的「半衰期」能不能算出来？",
     fill=CORAL_SOFT, size=13.5,
     extra="现在系统只能回答「它处于哪一段」。如果能对每个梗拟合出一条衰减曲线，"
           "就能回答「按历史规律，它还剩几天」——但这就落进了预测，"
           "而我在本课题一开始就把「不做未来数值预测」写成了边界。"
           "要越过这条线，得先补上足够的样本与一套可验证的评估方式；"
           "在那之前，我宁可只报现状。")
fin(s)
notes(s, "这一页讲「我接下来会怎么走」，也是给课题续命的理由。\n"
         "最后那个「半衰期」的问题很有价值：它是本课题的自然延伸，"
         "但它越过了我自己划的边界——把这个张力讲出来，比直接说「以后做预测」成熟得多。\n"
         "如果老师建议做预测：回应「需要先补样本与评估方案」，不要当场承诺。")

# =========================================================================== #
# 13 — closing
# =========================================================================== #
s = add()
ROW_W = CONTENT_W - 0.10
rect(s, 0, 0, SW, SH, fill=WHITE)
rect(s, 0, 0, 0.22, SH, fill=CORAL)
simple(s, MARGIN + 0.10, 0.66, 9.0, 0.32,
       [dict(text="收尾", size=13, color=CORAL, bold=True)], warn="d13-k")
tb = textbox(s, MARGIN + 0.10, 1.00, ROW_W, 0.86)
para(tb.text_frame, True, text="梗会凉，但这个账算得清", size=38, color=INK,
     bold=True, font=DISPLAY, line_spacing=1.0)
blk(s, MARGIN + 0.10, 2.06, ROW_W, 1.20, [
    dict(text="本课题交出来的不是一个分数，而是一套能被质疑、能被复算的测量方式：",
         size=14, color=INK, line_spacing=1.3),
    dict(text="口径写在配置文件里，结论由算法算出，证据带真实 BV 号，"
              "算不出来的地方就写「数据不足」。", size=14, color=INK,
         space_before=6, line_spacing=1.3),
], warn="d13-body")
sums = [("85", "条记录"), ("35", "个真实且已核验"), ("20", "个上热榜"),
        ("33", "个如实说「数据不足」")]
x = MARGIN + 0.10
ROW_W = CONTENT_W - 0.10
NCOL = 4
CW = (ROW_W - (NCOL - 1) * 0.11) / NCOL
for big, label in sums:
    card(s, x, 3.52, CW, 1.04, fill=CANVAS, line=LINE)
    blk(s, x + 0.24, 3.66, CW - 0.48, 0.78, [
        dict(text=big, size=26, color=CORAL, bold=True),
        dict(text=label, size=11.5, color=INK, bold=True, space_before=2)],
        warn="d13-sum")
    x += CW + 0.11
blk(s, MARGIN + 0.10, 4.82, ROW_W, 1.60, [
    dict(text="请各位老师重点看两处，也欢迎直接拆：", size=13, color=CORAL,
         bold=True),
    dict(text="① 「数据不足」这个闸门该不该存在——把不知道做成合法输出，"
              "是不是一个合格的数据产品该有的态度？", size=12.5, color=INK,
         space_before=8, line_spacing=1.32),
    dict(text="② 第 4 条已知未修的口径偏差，我的取舍（先修可信度、暂不动公式）"
              "是否合理？", size=12.5, color=INK, space_before=6, line_spacing=1.32),
], warn="d13-ask")
simple(s, MARGIN + 0.10, 6.60, ROW_W, 0.34,
       [dict(text="欢迎提问。数据、口径、代码、以及那四块没做完的实验，都可以当场翻。",
             size=12, color=GREY)], warn="d13-end")
notes(s, "收尾只做两件事：把核心立场再讲一遍，然后明确请老师看哪两处。\n"
         "不要总结技术细节——那些前面都讲过了。\n"
         "最后一句「都可以当场翻」很有用：它把整场的可信度押在可验证性上，"
         "也顺势把提问引到我准备过的地方。")
