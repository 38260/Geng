# =========================================================================== #
# 1 — cover
# =========================================================================== #
s = add()
rect(s, 0, 0, SW, 5.60, fill=WHITE)
rect(s, 0, 0, 0.22, 5.60, fill=CORAL)
simple(s, MARGIN + 0.10, 0.72, 9.0, 0.32,
       [dict(text="数据科学课程 · 结题答辩", size=14, color=CORAL, bold=True)],
       warn="c-kicker")
tb = textbox(s, MARGIN + 0.10, 1.06, 9.4, 1.05)
para(tb.text_frame, True, text="梗会凉，账要算清", size=54, color=INK,
     bold=True, font=DISPLAY, line_spacing=1.0)
rect(s, MARGIN + 0.10, 2.22, 1.90, 0.075, fill=CORAL)
simple(s, MARGIN + 0.10, 2.44, 9.0, 0.46,
       [dict(text="赶梗潮：B 站网络梗热度与生命周期分析", size=19, color=NAVY,
             bold=True)], warn="c-sub")
blk(s, MARGIN + 0.10, 3.06, 8.60, 2.32, [
    dict(text="一句话结论", size=12, color=GREY),
    dict(text="「梗」可以做成一个可复算的时间序列对象："
              "85 条记录 → 35 个通过核验 → 20 个上榜，每一步的丢人原因都能列出来。",
         size=14.5, color=INK, bold=True, space_before=6, line_spacing=1.3),
    dict(text="而最有价值的部分，是我用真实数据推翻了自己的一个判据（第 9 页）。",
         size=13.5, color=CORAL, bold=True, space_before=8),
], warn="c-hook")
if os.path.exists(MASCOT):
    pic(s, MASCOT, 10.62, 0.98, h=2.05)
simple(s, 10.30, 3.18, 2.35, 0.30,
       [dict(text="今天，赶什么梗？", size=12, color=INK, bold=True,
             font=DISPLAY, align=PP_ALIGN.CENTER)], warn="c-mascot-cap")
rect(s, 0, 5.60, SW, 1.90, fill=CANVAS)
info = card(s, 9.60, 5.86, 3.10, 1.60, radius=0.10)
blk(s, 9.86, 6.04, 2.58, 1.28, [
    dict(text="汇报人　＿＿＿＿＿＿", size=13, color=INK, bold=True),
    dict(text="学　号　＿＿＿＿＿＿", size=13, color=INK, space_before=6),
    dict(text="指导教师　＿＿＿＿＿＿", size=13, color=INK, space_before=6),
    dict(text="＿＿＿＿ 年 ＿＿ 月 ＿＿ 日", size=10.5, color=GREY,
         space_before=7),
], warn="c-info")
band(s, 5.86, 1.60, "这份答辩分三段：先给能证明的，再给还没做完的，最后给不打算做的。",
     fill=CORAL_SOFT, size=13.5, w=8.60, x=MARGIN,
     extra="还没做完的（混淆矩阵、权重消融、用户实验）在第 10 页，画成了空白面板，"
           "我不会拿它们冒充结果。")
fin(s, note="数据截至 2026-09-28，真实抓取；演示梗单独标注、不进真实榜单")
notes(s, "开场 30 秒讲完，不要念标题。\n"
         "重点是把三段的顺序说清楚：能证明的 → 没做完的 → 不打算做的。"
         "先声明「我不会拿没做的冒充结果」，后面整场会轻很多。\n"
         "结论那句话里的 85 / 35 / 20 是本次答辩的主干数字，"
         "分别对应「记录数」「真实且已核验」「过门槛上榜」。")

# =========================================================================== #
# 2 — headline results
# =========================================================================== #
s = add()
header(s, "结论先行", "三个数说清这个系统今天算出了什么",
       sub="三个数不是同一个东西的三次说法——它们是三层口径收紧之后的结果。")
kvs = [("20", "个梗上了热榜", "从 85 条记录里筛出来的最终结果", CORAL),
       ("76.8", "榜首热度（闪身步）", "爆发期 · 还来得及 · 置信度 0.95", CORAL),
       ("55.4%", "平均观测覆盖度", "近 7 天窗口里真正采到数据的天数占比", NAVY),
       ("33", "个梗被判「数据不足」", "不是算不出来，是不肯硬算", GOLD_DEEP)]
x = MARGIN
NCOL = 4
GAP = 0.19
CW = (CONTENT_W - (NCOL - 1) * GAP) / NCOL
for big, label, sub, c in kvs:
    kv(s, x, BODY_TOP, CW, 1.58, big, label, sub, color=c, bsize=34)
    x += CW + GAP
# top board table
blk(s, MARGIN, BODY_TOP + 1.80, 12.09, 0.30,
    [dict(text="当前热榜前 8（全部来自真实采集，可在库里逐条复核）", size=12,
          color=NAVY, bold=True)], warn="c2-th")
cols = [("名次", 0.85), ("梗", 2.55), ("热度", 1.25), ("阶段", 1.60),
        ("赶梗判断", 1.75), ("置信度", 1.30), ("认证", 2.59)]
y = BODY_TOP + 2.16
x = MARGIN
for h, w in cols:
    card(s, x, y, w, 0.40, fill=NAVY, line=None, radius=0.10)
    blk(s, x + 0.12, y + 0.07, w - 0.24, 0.26,
        [dict(text=h, size=10.5, color=WHITE, bold=True,
              align=PP_ALIGN.CENTER)], warn="c2-h")
    x += w + 0.03
y += 0.44
top = F["top_board"][:8]
cert = ["梗百科认证", "梗百科认证", "梗百科认证", "双 UP 认证", "双 UP 认证",
        "双 UP 认证", "双 UP 认证", "双 UP 认证"]
for i, r in enumerate(top):
    x = MARGIN
    card(s, MARGIN, y, sum(w for _, w in cols) + 0.18, 0.375,
         fill=WHITE if i % 2 == 0 else RGBColor(0xFA, 0xFB, 0xFD), line=LINE)
    vals = [str(i + 1), r["name"], "%.1f" % r["score"], r["stage"],
            r["catch"], "%.2f" % r["conf"], cert[i]]
    for (h, w), v, in zip(cols, vals):
        c = CORAL if h in ("热度", "赶梗判断") else INK
        blk(s, x + 0.12, y + 0.075, w - 0.24, 0.24,
            [dict(text=v, size=10.5, color=c, bold=True,
                  align=PP_ALIGN.CENTER if h != "梗" else PP_ALIGN.LEFT)],
            warn="c2-r%d" % i)
        x += w + 0.03
    y += 0.395
fin(s)
notes(s, "这一页就是「结论」。讲三个数，不要念表格。\n"
         "20 = 最终上榜数；76.8 = 榜首热度；55.4% = 平均观测覆盖度。\n"
         "特别解释第 4 个数（33 个「数据不足」）：这是本系统的一个主动选择——"
         "观测不足就拒答，而不是硬给一个阶段。\n"
         "表格可以留给老师自己看，如果现场断网它就是兜底。")

# =========================================================================== #
# 3 — where the data came from
# =========================================================================== #
s = add()
header(s, "数据从哪来", "5,044 条真实视频、2,209 行日统计，全部来自公开接口",
       sub="没有一条是生成出来的：演示数据单独标注、单独存储、不进真实榜单。")
kvs = [("5,044", "真实 B 站视频", "data_source='bilibili'"),
       ("2,209", "日粒度统计行", "覆盖 2026-08-28 ~ 09-28"),
       ("652,023,906", "近 30 天头部播放合计", "6.52 亿，按周发布 cohort 的累计口径"),
       ("1,150", "条视频带站内名次", "61 个梗有 B 站综合排序名次")]
x = MARGIN
NCOL = 4
GAP = 0.19
CW = (CONTENT_W - (NCOL - 1) * GAP) / NCOL
for big, label, sub in kvs:
    kv(s, x, BODY_TOP, CW, 1.46, big, label, sub, color=NAVY,
       bsize=25 if len(big) < 9 else 19)
    x += CW + GAP
if os.path.exists(os.path.join(ASSET, "funnel.png")):
    pic(s, os.path.join(ASSET, "funnel.png"), MARGIN, BODY_TOP + 1.80, w=7.10)
blk(s, 8.45, BODY_TOP + 1.70, 4.26, 3.00, [
    dict(text="三层口径，每层都在丢人", size=12, color=NAVY, bold=True),
    dict(text="85 → 71：有梗但窗口内没采到内容，不装作有数据", size=10.5,
         color=INK, space_before=7, line_spacing=1.26),
    dict(text="71 → 35：来源必须是真实采集，且至少一位 UP 主的投稿里真抓到过证据",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
    dict(text="35 → 20：过气的 2 个 + 近 7 天头部播放不足 1 万的 13 个，被「活着」门槛挡掉",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
    dict(text="被挡掉的梗没有消失：梗库接口 scope=all 仍然返回，"
              "趋势和详情都能看，只是不进首页热榜。",
         size=10.5, color=GREY, space_before=9, line_spacing=1.26),
    dict(text="目前 8 个双 UP 核验、38 个单 UP 核验、39 个未核验。"
              "最后一类不进热榜——演示梗的认证位是自己写上去的，不算证据。",
         size=10.5, color=CORAL, bold=True, space_before=9, line_spacing=1.26),
], warn="c3-side")
fin(s)
notes(s, "先讲「数据是真的」，再讲「怎么变少」。\n"
         "数字全部可以现查：videos / meme_daily_stats / meme_certifications 三张表。\n"
         "如果老师问「为什么只有 20 个上榜」：把三层口径背下来（85→71→35→20），"
         "每一层的理由一句话讲清。这比说「数据还不够多」有说服力得多。")

# =========================================================================== #
# 4 — measurement definition
# =========================================================================== #
s = add()
header(s, "测量口径（RQ1）", "热度不是播放量，是五个因子加权出来的",
       sub="权重全部集中在一个文件里，不散落在代码各处，前端一行判定逻辑都不写。")
if os.path.exists(os.path.join(ASSET, "weights.png")):
    pic(s, os.path.join(ASSET, "weights.png"), MARGIN, BODY_TOP - 0.04, w=6.00)
blk(s, MARGIN, BODY_TOP + 1.34, 7.10, 1.30, [
    dict(text="公式与实现", size=12, color=NAVY, bold=True),
    dict(text="Hotness = 0.25·增长 + 0.25·播放 + 0.20·互动 + 0.16·内容 + 0.14·创作者",
         size=12.5, color=INK, bold=True, font=MONO, space_before=5),
    dict(text="backend/app/analytics/hotness.py ｜ 阈值与权重："
              "backend/app/config/algorithms.py", size=10, color=GREY,
         space_before=5, font=MONO, line_spacing=1.24),
], warn="c4-f")
blk(s, 8.45, BODY_TOP - 0.04, 4.26, 4.60, [
    dict(text="四个刻意的设计决定", size=12.5, color=CORAL, bold=True),
    dict(text="① 对数区间归一化", size=11.5, color=INK, bold=True,
         space_before=10),
    dict(text="播放量差三个量级的梗必须能同框比较。线性归一会让亿级老梗永远压住新梗。",
         size=10.5, color=GREY, space_before=3, line_spacing=1.26),
    dict(text="② 增长权重 = 播放权重 = 0.25", size=11.5, color=INK, bold=True,
         space_before=10),
    dict(text="要回答的是「最近是不是在变热」。去年 1 亿播放、今天没人做的梗不该排前面。",
         size=10.5, color=GREY, space_before=3, line_spacing=1.26),
    dict(text="③ 样本不足就不外推", size=11.5, color=INK, bold=True,
         space_before=10),
    dict(text="前一周讨论量 < 30 或相关视频 < 3 条时增长率置空并对整体打折，"
              "显示「—」而不是 +585% 这种噪声。",
         size=10.5, color=GREY, space_before=3, line_spacing=1.26),
    dict(text="④ 算法与文案分离", size=11.5, color=INK, bold=True,
         space_before=10),
    dict(text="热度、阶段、赶梗判断全部由算法算出；大模型不参与任何数值判断。",
         size=10.5, color=GREY, space_before=3, line_spacing=1.26),
], warn="c4-r")
fin(s)
notes(s, "讲四件事，不要念公式。\n"
         "如果老师质疑权重主观：坦白说初始权重来自设计判断，"
         "这次答辩给不出消融实验结果（第 10 页有空白面板），"
         "但已有两条硬约束——对数区间归一化让量级不吃掉权重、样本不足不外推。\n"
         "「算法与文案分离」这一条要强调：它保证了大模型坏掉时产品不坏。")

# =========================================================================== #
# 5 — lifecycle results
# =========================================================================== #
s = add()
header(s, "生命周期判定（RQ2 / RQ3）", "六个阶段加一个闸门，判定只用四个可观测量",
       sub="增长率 · 距峰值差 · 连续下滑天数 · 活跃度——规则自上而下匹配，每条结论都能指出依据。")
stages = [("萌芽", "🌱", 9), ("上升", "📈", 8), ("爆发", "🔥", 2),
          ("平稳", "🌊", 4), ("退潮", "📉", 12), ("过气", "🪦", 3)]
x = MARGIN
NCOL = 6
CW = (CONTENT_W - (NCOL - 1) * 0.10) / NCOL
for i, (name, emoji, cnt) in enumerate(stages):
    card(s, x, BODY_TOP, CW, 1.20, fill=WHITE, line=LINE)
    blk(s, x + 0.16, BODY_TOP + 0.16, CW - 0.32, 0.92, [
        dict(text=emoji + " " + name, size=13.5, color=INK, bold=True,
             align=PP_ALIGN.CENTER),
        dict(text="%d 个" % cnt, size=18, color=CORAL, bold=True,
             align=PP_ALIGN.CENTER, space_before=3)])
    x += CW + 0.10
gate = card(s, MARGIN, BODY_TOP + 1.38, 12.09, 1.06, fill=CORAL_SOFT, line=None)
blk(s, MARGIN + 0.34, BODY_TOP + 1.54, 11.4, 0.78, [
    dict(text="最大的一格不在上排，在闸门里：「数据不足」33 个。", size=13.5,
         color=CORAL, bold=True),
    dict(text="近 7 天观测到的天数不足 4 天时，算法拒绝给阶段与赶梗结论，置信度记 0。"
              "界面不把它画进生命轴线——它不是第七个阶段，是「没有地基所以不说」。",
         size=11, color=INK, space_before=5, line_spacing=1.3),
], warn="c5-gate")
if os.path.exists(os.path.join(ASSET, "coverage.png")):
    pic(s, os.path.join(ASSET, "coverage.png"), MARGIN, BODY_TOP + 2.72, w=7.10)
blk(s, 8.45, BODY_TOP + 2.60, 4.26, 2.10, [
    dict(text="为什么这一格这么大", size=12, color=NAVY, bold=True),
    dict(text="B 站匿名搜索对同一个词、同一天会随机返回空结果：实测逐日打 "
              "15 天 × 2 次，30 次里只有 12 次拿到内容。", size=10.5, color=INK,
         space_before=6, line_spacing=1.26),
    dict(text="不重试就会把序列打出一片 0，而「0」和「那天真没人做」在返回体里长得一样。",
         size=10.5, color=INK, space_before=6, line_spacing=1.26),
    dict(text="处理：每天额外重试 2 次（间隔递增）→ 覆盖度从 40% 提到 87%；"
              "拿不到就记 observed=0，绝不写 0 活动。",
         size=10.5, color=GREY, space_before=6, line_spacing=1.26),
    dict(text="当前全库平均观测覆盖度 55.4%。", size=10.5, color=CORAL,
         bold=True, space_before=6),
], warn="c5-side")
fin(s)
notes(s, "这一页的主角是「33 个数据不足」，不是那六个阶段。\n"
         "讲清一件事：「没看见」不等于「没有」。早期版本给窗口里每一天无条件写一行，"
         "空壳变成 video_count=0，跟「当天真没人做」在库里长得一样——"
         "「琵琶曲」被判「退潮」就是这么来的。\n"
         "覆盖度图：浅色柱是「当天有记录的梗数」，深色柱是「真正观测到的」，"
         "中间那段就是缺口，我们不把它画成 0。")

# =========================================================================== #
# 6 — the headline finding / scatter preview
# =========================================================================== #
s = add()
header(s, "先给一个被推翻的结论", "解说播放量高的梗，并不更热",
       sub="这是我自己先立的判据，然后拿 31 个真实样本把它推翻了。")
if os.path.exists(os.path.join(ASSET, "scatter.png")):
    pic(s, os.path.join(ASSET, "scatter.png"), MARGIN, BODY_TOP - 0.02, w=5.85)
blk(s, 6.95, BODY_TOP - 0.02, 5.76, 3.10, [
    dict(text="被检验的假设", size=10.5, color=NAVY, bold=True),
    dict(text="「解说视频播放量破百万的梗，才值得花成本去做。」", size=14,
         color=INK, bold=True, font=DISPLAY, space_before=4, line_spacing=1.24),
    dict(text="检验结果（n = 31）", size=10.5, color=CORAL, bold=True,
         space_before=12),
    dict(text="Pearson r = +0.40（p = 0.028）", size=15, color=INK, bold=True,
         font=MONO, space_before=4),
    dict(text="Spearman ρ = +0.29（p = 0.12，不显著）", size=12, color=GREY,
         font=MONO, space_before=3),
    dict(text="R² ≈ 0.16：解说播放量只能解释热度方差的约 16%。",
         size=11.5, color=INK, bold=True, space_before=8, line_spacing=1.28),
    dict(text="两个方向相反的反例：", size=10.5, color=INK, space_before=10),
    dict(text="· 闪身步：解说 64.6 万 → 梗热度 76.8（全站第一）", size=10.5,
         color=CORAL, space_before=4, line_spacing=1.26),
    dict(text="· 宗主第二招：解说 160.7 万 → 梗热度 0.0", size=10.5,
         color=GOLD_DEEP, space_before=3, line_spacing=1.26),
], warn="c6-side")
band(s, BODY_TOP + 3.32, 1.18,
     "结论：解说播放量衡量的是那个账号自己的粉丝盘，而且是发布时刻的存量。",
     fill=CORAL_SOFT, size=12.5,
     extra="它能用来做采集成本的预算筛，不能当准入判据——"
           "所以新口径用的是「两位 UP 主里至少一位介绍过」，而不是「播放量够高」。")
fin(s)
notes(s, "这页是本次答辩的「高光页」，讲出过程比讲结论重要。\n"
         "顺序：我先立假设 → 拿 31 个上榜梗检验 → Pearson 显著但 Spearman 不显著 → "
         "R² 只有 0.16 → 反例方向相反 → 判据被推翻 → 我改了准入口径。\n"
         "如果老师问「为什么不做更大样本」：n = 31 是当时上热榜的梗数，"
         "确实小，这一点写在局限里；等数据积累后可复算。")
