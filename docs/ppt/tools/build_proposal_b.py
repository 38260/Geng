# =========================================================================== #
# 7 — real dataset
# =========================================================================== #
s = add()
header(s, "数据规模", "喂给算法的不是示例数据，是 5,044 条真实视频",
       sub="下面每个数字都可以现查：sqlite3 backend/data/gengv1.db "
           "\"select count(*) from videos where data_source='bilibili'\"")
kvs = [("5,044", "真实 B 站视频", "另有 108 条演示视频，来源字段分开、不混算"),
       ("2,209", "日粒度统计行", "覆盖 2026-08-28 ~ 09-28，逐日不是聚合摊派"),
       ("504", "万字", "近 30 天采信样本的头部播放合计（6.5 亿）"),
       ("61", "个梗有站内名次", "1,150 条视频带 B 站综合排序名次，够两档排法用"),
       ("0", "条演示数据进榜", "真实模式下未在线核验的梗一律不上榜")]
x = MARGIN
NCOL = 5
GAP = 0.19
CW = (CONTENT_W - (NCOL - 1) * GAP) / NCOL
for big, label, sub in kvs:
    kv(s, x, BODY_TOP, CW, 1.42, big, label, sub,
       color=CORAL if big == "0" else NAVY, bsize=25)
    x += CW + GAP
blk(s, MARGIN, BODY_TOP + 1.60, 8.20, 1.50, [
    dict(text="口径先说清楚，免得误读：", size=12.5, color=NAVY, bold=True),
    dict(text="「当日播放量」= 那天该关键词下播放量最高的 20 条相关视频的合计，"
              "不是全站绝对量。跨日、跨梗用的是同一把尺子，所以形状与排序可信，"
              "绝对数值不能拿去跟站方数据对。", size=11.5, color=INK,
         space_before=5, line_spacing=1.3),
    dict(text="为什么逐日分开查：不带日期区间时，搜索结果会被最近发布的内容占满，"
              "早期日期根本查不到。第一版就是一次搜完再聚合，算出了 +23,616% 的假增长。",
         size=11, color=GREY, space_before=5, line_spacing=1.3),
], warn="s7-note")
if os.path.exists(os.path.join(ASSET, "funnel.png")):
    pic(s, os.path.join(ASSET, "funnel.png"), 8.76, BODY_TOP + 1.92, w=3.95)
fin(s)
notes(s, "这页回答「数据从哪来、有多少」。\n"
         "一定要主动交代口径：头部 20 条合计，不是全站绝对量。"
         "被老师问到时，承认局限比遮掩有用——同时说明为什么它仍然够用来排序。\n"
         "漏斗图右侧那四个数（85 / 71 / 35 / 20）是同一套闸门的结果，"
         "第 9 页会解释每一层为什么丢人。")

# =========================================================================== #
# 8 — discovery layer
# =========================================================================== #
s = add()
header(s, "发现层设计", "我把「两个 UP 主都做过」这个规矩废掉了",
       sub="这是被真实数据打脸之后改的——而且打脸打得很干脆。")
# old
card(s, MARGIN, BODY_TOP, 5.55, 2.28, fill=WHITE, line=LINE)
rect(s, MARGIN, BODY_TOP, 5.55, 0.075, fill=MIST)
blk(s, MARGIN + 0.30, BODY_TOP + 0.26, 4.95, 1.88, [
    dict(text="旧口径：取交集（两位都介绍过）", size=14, color=GREY, bold=True),
    dict(text="90 天滚动窗口实测：梗百科单独介绍 37 个，梗指南 22 个，"
              "交集只剩 8 个。", size=12, color=INK, space_before=8,
         line_spacing=1.3),
    dict(text="等于让日更账号的选题，被周更账号的排期一票否决。",
         size=12, color=INK, space_before=6, line_spacing=1.3),
    dict(text="当时热度最高的「闪身步」（当时 81.0）就在库外——"
              "它只在梗百科做过。", size=12, color=CORAL, bold=True,
         space_before=6, line_spacing=1.3),
], warn="s8-old")
# new
card(s, 6.94, BODY_TOP, 5.55, 2.28, fill=WHITE, line=LINE)
rect(s, 6.94, BODY_TOP, 5.55, 0.075, fill=CORAL)
blk(s, 7.24, BODY_TOP + 0.26, 4.95, 1.88, [
    dict(text="新口径：取并集（任一位介绍过即入池）", size=14, color=CORAL,
         bold=True),
    dict(text="同一批投稿，入池从 8 个变成 51 个。", size=12, color=INK,
         space_before=8, line_spacing=1.3),
    dict(text="「双 UP 认证」降级为标签，而不是闸门：只有一位做过就写明是哪一位，"
              "可信度信息一点没丢。", size=12, color=INK, space_before=6,
         line_spacing=1.3),
    dict(text="认证窗口 90 天 ≠ 报告窗口 30 天：解说通常比爆发期早 1~2 周，"
              "两窗合一会把还在热的梗排除。", size=11.5, color=GREY,
         space_before=6, line_spacing=1.3),
], warn="s8-new")
band(s, BODY_TOP + 2.48, 1.34,
     "认证强度如实标在卡片上，而不是用来卡进不进库。",
     fill=NAVY_SOFT, color=NAVY, size=13,
     extra="系统实时状态：verified_both（双 UP 核验）8 个 · partially_verified（单 UP 核验）38 个 · "
           "unverified 39 个。真实模式下最后一类不进热榜——演示梗的认证位是自己写上去的，"
           "不算证据。准入口径写在 models / services / api 三处并各有测试。")
band(s, BODY_TOP + 3.96, 1.10,
     "顺手记一个坑：UP 主为规避敏感词会把标题写成「XX在哪？最优骑士小碎步」这类占位名。",
     fill=RGBColor(0xFF, 0xF7, 0xE3), color=GOLD_DEEP, size=11.5,
     extra="实测 51 条里有 6 条。这类名字没法拿去检索，在抽取阶段直接丢弃，"
           "而不是让它进库当一条永远采不到数据的空壳。")
fin(s)
notes(s, "这是全场最能体现「数据科学」的一页：先立规矩，再用数据把规矩推翻，然后改规矩。\n"
         "一定要说出「一票否决」这四个字——老师会立刻明白交集口径的问题。\n"
         "如果问「并集会不会太松」：松的部分我承认，所以留了人工新增入口；"
         "而且每一次准入都带真实 BV 号，可以逐条核对。")

# =========================================================================== #
# 9 — hotness index
# =========================================================================== #
s = add()
header(s, "热度指数（RQ1）", "0.25 给了增长，因为要回答的是「最近是不是在变热」",
       sub="权重不散落在代码里：全部集中在 backend/app/config/algorithms.py，改数只改这一处。")
if os.path.exists(os.path.join(ASSET, "weights.png")):
    pic(s, os.path.join(ASSET, "weights.png"), MARGIN, BODY_TOP - 0.06, w=6.00)
bullets = [
    ("对数区间归一化。", "播放量差三个量级的梗必须能同框比较；线性归一会让亿级老梗永远压住新梗。"),
    ("增长只看最近 7 天 vs 前 7 天。", "去年 1 亿播放、今天没人做的梗，不该排在前面。"),
    ("样本不足就不外推。", "前一周讨论量 < 30 或相关视频 < 3 条时，增长率置空并对整体打折，"
                      "卡片显示「—」而不是 +585% 这种噪声。"),
    ("门槛与算法分开。", "「准入」回答这是不是个真梗；「上榜」还要回答今天玩什么——"
                    "过气不上榜，近 7 天头部播放 < 1 万不上榜。"),
]
y = BODY_TOP + 1.62
for head, body in bullets:
    card(s, MARGIN, y, 12.09, 0.74, fill=WHITE, line=LINE)
    blk(s, MARGIN + 0.30, y + 0.13, 11.50, 0.50, [
        dict(text=head + body, size=11.5, color=INK, line_spacing=1.28)],
        warn="s9-bullet")
    y += 0.74 + 0.09
band(s, y + 0.02, 0.42,
     "四条约束合起来就是一句话：热度回答「最近是不是在变热」，而不是「历史上有多热」。",
     fill=NAVY_SOFT, color=NAVY, size=11, exsize=0)
fin(s)
notes(s, "核心一句话：这个指数是用来回答「最近是不是在变热」，所以增长权重跟播放权重一样大。\n"
         "如果老师质疑权重主观：老实说初始权重来自设计判断，"
         "但有两件事约束它——对数区间归一化让量级不吃掉权重，"
         "以及论文阶段计划做权重消融（每次 ±0.05 看排名稳定性）与人工标注一致性检验。\n"
         "「样本不足就不外推」这条要强调：它是本课题数据质量立场的一部分。")

# =========================================================================== #
# 10 — lifecycle
# =========================================================================== #
s = add()
header(s, "生命周期与赶梗判断（RQ2 / RQ3）", "六个阶段是数出来的，不是感觉出来的",
       sub="判定只用四个可观测量：增长率、距峰值差、连续下滑天数、活跃度。")
stages = [("萌芽", "🌱", "#6FCF97"), ("上升", "📈", "#5BB8F5"),
          ("爆发", "🔥", "#FB3A5E"), ("平稳", "🌊", "#FFC94B"),
          ("退潮", "📉", "#9AA8BF"), ("过气", "🪦", "#6B7280")]
x = MARGIN
NCOL = 6
CW = (CONTENT_W - (NCOL - 1) * 0.10) / NCOL
for i, (name, emoji, col) in enumerate(stages):
    card(s, x, BODY_TOP, CW, 1.06, fill=WHITE, line=LINE)
    blk(s, x + 0.16, BODY_TOP + 0.16, CW - 0.32, 0.78, [
        dict(text=emoji + " " + name, size=14, color=INK, bold=True,
             align=PP_ALIGN.CENTER),
        dict(text="规则自上而下匹配", size=8.5, color=GREY,
             align=PP_ALIGN.CENTER, space_before=3)])
    if i < len(stages) - 1:
        simple(s, x + CW, BODY_TOP + 0.36, 0.16, 0.34,
               [dict(text="→", size=14, color=MIST, align=PP_ALIGN.CENTER)])
    x += CW + 0.10
gate = card(s, MARGIN, BODY_TOP + 1.24, 12.09, 1.16, fill=CORAL_SOFT, line=None)
blk(s, MARGIN + 0.34, BODY_TOP + 1.40, 11.4, 0.86, [
    dict(text="第七个状态不是阶段，是闸门：「数据不足」。", size=13.5,
         color=CORAL, bold=True),
    dict(text="近 7 天真正观测到的天数不足 4 天时，算法拒绝给阶段与赶梗结论，置信度记 0。"
              "热度照给（存量水平是横截面比较），但时间轴上的结论没有地基就不说。",
         size=11, color=INK, space_before=5, line_spacing=1.3),
], warn="s10-gate")
# live distribution
blk(s, MARGIN, BODY_TOP + 2.56, 5.10, 1.80, [
    dict(text="当前真实分布（入池 71 个梗）", size=12, color=NAVY, bold=True),
    dict(text="数据不足 33 · 退潮期 12 · 萌芽期 9 · 上升期 8 · 平稳期 5 · 过气 4 · 爆发期 1",
         size=11.5, color=INK, space_before=6, line_spacing=1.35),
    dict(text="最大的一格是「数据不足」，我没有把它藏起来。",
         size=11.5, color=CORAL, bold=True, space_before=6),
], warn="s10-dist")
blk(s, 6.96, BODY_TOP + 2.56, 5.75, 1.80, [
    dict(text="赶梗三态由算法给出，大模型只能复述", size=12, color=NAVY, bold=True),
    dict(text="还来得及 / 慎赶 / 你来晚了，各带置信度与一句理由。"
              "模型返回的 status 与算法不一致时以算法为准；文案里出现「预计」"
              "「未来 7 天」「一定会爆」这类预测口吻会被直接丢弃。",
         size=11.5, color=INK, space_before=6, line_spacing=1.35),
    dict(text="大模型不参与任何数值判断，也不做未来数值预测。",
         size=11.5, color=CORAL, bold=True, space_before=6),
], warn="s10-catch")
band(s, BODY_TOP + 4.48, 0.80,
     "阶段划分的来路：Downs（1972）议题—注意力周期 · 宋宁、刘婵君（2016）舆情演化阶段 · "
     "Crane & Sornette（2008）在线注意力只有少数几种可复用的脉冲响应形状。",
     fill=NAVY_SOFT, color=NAVY, size=10.5, exsize=0)
fin(s)
notes(s, "先用「数据不足」这个闸门抓住老师：它不是第七个阶段，界面上也不画进时间轴。\n"
         "拿「琵琶曲」举例：30 天里只有 4 天有内容，但那几天播了 3,976 万——"
         "按「有内容天数」卡会把它误杀，所以门槛刻意不用天数，只用近期播放量下限。\n"
         "被问「为什么不用 LSTM」：输出是判定不是外推，而且 84 条梗、2,209 行日统计"
         "撑不起深度模型；规则引擎的好处是每条判定都能指出是哪条规则、哪个阈值。")

# =========================================================================== #
# 11 — data quality (the core contribution)
# =========================================================================== #
s = add()
header(s, "数据质量", "四个我自己踩出来的坑，每个都留了症状、诊断、处方",
       sub="这一页是我认为整个课题最有数据科学含量的部分——上游接口是测不准的，观测得自己造。")
rows = [
    ("假增长", "一次抓完再摊到每天，算出 +23,616%",
     "拿今天看到的累计播放量回填了历史某天",
     "逐日带 pubtime_begin/end 区间查询，只统计当天发布内容"),
    ("抽样抖动", "同一个词同一天两次：一次 20 条、一次 0 条",
     "琵琶曲从 4 天 / 3,976 万被刷成 1 天 / 18 条，热度 44.2 → 0.0",
     "同一天只保留更好的一次观测（比样本数与播放量，绝不相加），并提供快照回填工具"),
    ("空窗误删", "一次采空就把历史真实数据清掉",
     "把「没看见」当成「没有」",
     "空窗只清非同源数据，同源旧快照保留并计数；没拿到就写 observed=0"),
    ("短别名污染", "「我不是黄豆」的别名「黄豆」命中即算相关",
     "418 条样本里 343 条其实只在讲黄豆，该梗还挂着榜首",
     "短于 4 字的别名只算弱证据，必须再有第二个词佐证"),
]
hdr = ["症状", "实测现象", "诊断", "处方"]
CW = [1.50, 3.50, 2.70, 4.15]
y = BODY_TOP
x = MARGIN
for i, h in enumerate(hdr):
    card(s, x, y, CW[i], 0.42, fill=NAVY, line=None, radius=0.10)
    blk(s, x + 0.09, y + 0.08, CW[i] - 0.18, 0.28,
        [dict(text=h, size=11.5, color=WHITE, bold=True)], warn="s11-head")
    x += CW[i] + 0.05
y += 0.47
for name, sym, diag, fix in rows:
    x = MARGIN
    cells = [(name, CORAL, True), (sym, INK, False), (diag, GREY, False),
             (fix, INK, False)]
    rh = 0.94
    card(s, MARGIN, y, sum(CW) + 0.06, rh, fill=WHITE, line=LINE)
    for i, (txt, col, bold) in enumerate(cells):
        blk(s, x + 0.09, y + 0.12, CW[i] - 0.18, rh - 0.22,
            [dict(text=txt, size=10, color=col, bold=bold, line_spacing=1.24)],
            warn="s11-%s-%d" % (name, i))
        x += CW[i] + 0.05
    y += rh + 0.07
band(s, BODY_TOP + 4.44, 0.84,
     "顺带一个反直觉的实测：B 站匿名搜索对同一个词、同一天会随机返回空结果——"
     "逐日打 15 天 × 2 次，30 次里只有 12 次拿到内容。",
     fill=NAVY_SOFT, color=NAVY, size=11.5,
     extra="所以「没观测到」和「当天没人做」在库里必须长得不一样。"
           "重试后覆盖度从 40% 提到 87%；当前全库平均观测覆盖度 55.4%。", exsize=10)
fin(s)
notes(s, "这是全场最重要的一页，讲慢，让老师听完能复述。\n"
         "统一句式：症状 → 实测现象 → 诊断 → 处方。每个坑都配了可报出来的数字。\n"
         "最后那个「30 次里只有 12 次拿到内容」很能说明问题：上游是随机的，"
         "所以观测策略本身就是方法贡献。\n"
         "主动补一句诚实的现状：即便上了这些处方，当前全库平均观测覆盖度也只有 55.4%，"
         "像「琵琶曲」这种脉冲型梗到今天仍然落在「数据不足」里（热度 50.3、近 7 天头部播放 669 万，"
         "但真正观测到的天数不够）。处方是改善了、没有根治——这一条正好接得上后面的局限页。\n"
         "如果老师问「这些是你编的吗」：全部可以在 docs/data/refresh-report.md "
         "和 backend/data/gengv1.db 里复查。")
