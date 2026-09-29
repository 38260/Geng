# =========================================================================== #
# 7 — data quality: the four traps
# =========================================================================== #
s = add()
header(s, "数据质量（方法贡献）", "四个坑，每个都留了症状、诊断、处方",
       sub="上游接口是测不准的，稳定观测得自己造出来——这是我认为本课题最有数据科学含量的部分。")
rows = [
    ("假增长", "一次抓完再摊到每天，算出 +23,616%",
     "拿今天看到的累计播放量回填了历史某天",
     "逐日带 pubtime_begin/end 区间查询，只统计当天发布内容"),
    ("抽样抖动", "同一个词同一天两次：一次 20 条、一次 0 条",
     "琵琶曲从 4 天 / 3,976 万被刷成 1 天 / 18 条，热度 44.2 → 0.0",
     "同一天只保留更好的一次观测（比样本数与播放量，绝不相加）"),
    ("空窗误删", "一次采空就把历史真实数据清掉",
     "把「没看见」当成「没有」，空壳与真零在库里无法区分",
     "空窗只清非同源数据；同源旧快照保留并计数，拿不到就记 observed=0"),
    ("短别名污染", "「我不是黄豆」的别名「黄豆」命中即算相关",
     "418 条样本里 343 条其实只在讲黄豆（琵琶曲黄豆版、炒黄豆），该梗还挂着榜首",
     "短于 4 字的别名只算弱证据，必须再有第二个词佐证才能过阈值"),
]
hdr = ["症状", "实测现象", "诊断", "处方"]
CW = [1.50, 3.50, 2.70, 4.15]
y = BODY_TOP
x = MARGIN
for i, h in enumerate(hdr):
    card(s, x, y, CW[i], 0.42, fill=NAVY, line=None, radius=0.10)
    blk(s, x + 0.09, y + 0.08, CW[i] - 0.18, 0.28,
        [dict(text=h, size=11.5, color=WHITE, bold=True)], warn="d7-h")
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
            warn="d7-cell")
        x += CW[i] + 0.05
    y += rh + 0.07
band(s, BODY_TOP + 4.44, 0.84,
     "统一句式：症状 → 实测现象 → 诊断 → 处方。四条都能在 "
     "docs/data/refresh-report.md 与库里复查。",
     fill=NAVY_SOFT, color=NAVY, size=11.5,
     extra="另外两个可复现的实测结论：匿名请求 player/wbi/v2 返回 code=0 但字幕轨为空数组；"
           "B 站图床带 Referer 会 403、不带才 200（所以前端 img 必须 no-referrer）。", exsize=10)
fin(s)
notes(s, "全场最重要的一页，讲慢。\n"
         "每一条都按「症状 → 现象 → 诊断 → 处方」讲，现象里带可报出来的数字。\n"
         "如果老师问「这是工程问题还是科学问题」：这是测量问题——"
         "在上游测不准的前提下，怎么构造一个稳定、可复算的观测量，属于方法贡献。\n"
         "最后两个实测细节用来证明「这些都是真跑出来的，不是想出来的」。")

# =========================================================================== #
# 8 — verification experiments that DID run
# =========================================================================== #
s = add()
header(s, "验证实验（已做）", "三项做完了的验证，结论都写在这里",
       sub="没做的三项在下一页，画成空白面板——这两页请不要混看。")
exp = [
    ("① 判据证伪实验", CORAL, CORAL_SOFT,
     ["假设：解说播放量破百万的梗才值得做",
      "方法：对 31 个上榜梗做相关分析",
      "结果：Pearson r = +0.40（p = 0.028）；Spearman ρ = +0.29（p = 0.12，不显著）；R² ≈ 0.16",
      "结论：判据被推翻，改用它做成本预算筛，不做准入门槛"]),
    ("② 观测策略的覆盖率提升", NAVY, NAVY_SOFT,
     ["问题：同词同日匿名搜索会随机返回空结果（30 次里只有 12 次拿到内容）",
      "方法：每天额外重试 2 次 + 同日取更优观测 + 快照回填",
      "结果：单日覆盖度 40% → 87%；同日沿用更优观测 169 天",
      "结论：把「没看见」和「没有」在数据模型里彻底分开"]),
    ("③ 门槛消融（规则层）", GOLD_DEEP, RGBColor(0xFF, 0xF7, 0xE3),
     ["做法：逐层加上「过气不上榜」与「近 7 天播放 ≥ 1 万」两条门槛",
      "结果：候选从 35 收敛到 20；挡掉的 15 个里 2 个过气、13 个只剩历史残值",
      "反例检验：琵琶曲 30 天只有 4 天有内容却播了 3,976 万——刻意不用天数当门槛",
      "结论：门槛用播放量下限而不是活跃天数，避免误杀脉冲型梗"]),
]
y = BODY_TOP
for title, ac, bg, lines in exp:
    h = 1.48
    card(s, MARGIN, y, 12.09, h, fill=WHITE, line=LINE)
    rect(s, MARGIN, y, 0.055, h, fill=ac)
    blk(s, MARGIN + 0.34, y + 0.18, 2.95, h - 0.34,
        [dict(text=title, size=13.5, color=ac, bold=True, line_spacing=1.24)],
        warn="d8-t")
    blk(s, MARGIN + 3.50, y + 0.18, 8.42, h - 0.34,
        [dict(text="· " + t, size=10.5, color=INK, space_before=0 if i == 0 else 6,
              line_spacing=1.26) for i, t in enumerate(lines)], warn="d8-b")
    y += h + 0.14
band(s, y + 0.02, 0.74,
     "这三项的共同点：都是先立一个可被数据推翻的说法，再去检验它。",
     fill=CORAL_SOFT, size=12.5, exsize=0)
fin(s)
notes(s, "这一页的作用是「我确实做过验证」，但不要夸大。\n"
         "第①项是判据证伪，第②项是观测策略的覆盖率，第③项是门槛消融——"
         "注意第③项是规则层消融，不是权重消融，措辞上要说准，别让老师以为权重也做了。\n"
         "如果老师追问权重消融：直接说「没做，在下一页的空白面板里」。")

# =========================================================================== #
# 9 — pending experiments (visible blanks)
# =========================================================================== #
s = add()
header(s, "验证实验（未做）", "这四块是空的，我不打算装作它们已经跑完",
       sub="现场如果必须填，我会说「这是下一步」——不会现编数字。",
       accent=GOLD, tag="空白面板")
pending(s, MARGIN, BODY_TOP, 5.95, 1.96, "A · 阶段判定一致性（混淆矩阵）",
        ["标注方案：_____ 个梗 × _____ 名标注者（待定）",
         "指标：混淆矩阵 + 准确率 / Kappa = ________",
         "对照：规则判定 vs 3 名标注者多数票"],
        note="计划第 5 周完成")
pending(s, 6.76, BODY_TOP, 5.95, 1.96, "B · 权重消融实验",
        ["做法：每次对一个权重 ±0.05，重算排名",
         "指标：排名 Spearman 相关 = ________",
         "目的：证明 0.25/0.25/0.20/0.16/0.14 不是拍脑袋"],
        note="计划第 5 周完成")
pending(s, MARGIN, BODY_TOP + 2.14, 5.95, 1.96, "C · 用户实验（对照）",
        ["方案：_____ 人对照「看热搜」vs「看本系统」",
         "指标：选题准确率 = ________ / 主观有用性 = ________",
         "待定：实验平台与任务设计"],
        note="计划第 4 周完成")
pending(s, 6.76, BODY_TOP + 2.14, 5.95, 1.96, "D · 抽样口径敏感性分析",
        ["做法：把头部 20 条改成 10 / 50 重跑",
         "指标：排名 Spearman 相关 = ________",
         "目的：说明结论对样本量不敏感"],
        note="计划第 5-6 周完成")
band(s, BODY_TOP + 4.30, 0.98,
     "为什么把它们画成空白面板：一份答辩如果什么都不缺，通常说明标准定得太低。",
     fill=RGBColor(0xFF, 0xF7, 0xE3), color=GOLD_DEEP, size=12,
     extra="这四块分别对应用户实验、混淆矩阵、权重消融、抽样敏感性——"
           "也是评委最常问的四组数字。我先承认它们没有，再讲我打算怎么补。")
fin(s)
notes(s, "这一页必须讲得坦荡，不要心虚。\n"
         "开场就说：这四块是空的，我画成空白面板而不是删掉，就是想让大家知道缺口在哪。\n"
         "这四块正好覆盖评委最常问的四组数字，主动交底可以避免被追着问。\n"
         "如果有人愿意给建议（比如标注方案怎么设计），当场记下来。")

# =========================================================================== #
# 10 — engineering evidence
# =========================================================================== #
s = add()
header(s, "工程证据", "不是「我做了个网站」，是 279 项测试在守着那些口径",
       sub="所有数字都可用仓库里的命令复现，不是截图。")
kvs = [("279", "后端测试全绿", "假客户端 + 内存库，全部离线可复跑", CORAL),
       ("125", "接口冒烟用例", "对着运行中的真实后端逐个打过去", NAVY),
       ("21", "小程序测试用例", "展示层纯函数 + 对着真实后端的接口契约", NAVY),
       ("69 + 31", "后端模块 + 前端文件", "10,409 行 Python、4,666 行 TS/TSX", NAVY),
       ("204KB", "前端构建产物", "gzip 66KB，ECharts 拆到详情页按需加载", GOLD_DEEP)]
x = MARGIN
NCOL = 5
GAP = 0.19
CW = (CONTENT_W - (NCOL - 1) * GAP) / NCOL
for big, label, sub, c in kvs:
    kv(s, x, BODY_TOP, CW, 1.42, big, label, sub, color=c,
       bsize=27 if len(big) < 6 else 22)
    x += CW + GAP
blk(s, MARGIN, BODY_TOP + 1.60, 5.95, 2.94, [
    dict(text="被测试锁住的关键断言（这几条最容易被做坏）", size=12, color=NAVY,
         bold=True),
    dict(text="· 改封面、改介绍，不会改变热度与榜单——人工只能碰展示层",
         size=10.5, color=INK, space_before=8, line_spacing=1.26),
    dict(text="· 重算是幂等的：同一份数据算两次，结果完全一致", size=10.5,
         color=INK, space_before=5, line_spacing=1.26),
    dict(text="· 演示数据不得进真实榜单（真实模式下未核验的梗一律挡掉）",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
    dict(text="· 观测不足时生命周期与赶梗判断必须返回「数据不足」", size=10.5,
         color=INK, space_before=5, line_spacing=1.26),
    dict(text="· 大模型返回的 status 与算法不一致时，以算法为准", size=10.5,
         color=INK, space_before=5, line_spacing=1.26),
    dict(text="· 没有 Key、错误 Key、超时三种情况页面都不崩，且可「重新判断」",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
], warn="d10-left")
blk(s, 6.76, BODY_TOP + 1.60, 5.95, 2.94, [
    dict(text="AI 不是单点故障（这条也有测试覆盖）", size=12, color=CORAL,
         bold=True),
    dict(text="· 未配 Key：文案位显示算法自己写的那句话，标注「文案来源：算法兜底」",
         size=10.5, color=INK, space_before=8, line_spacing=1.26),
    dict(text="· 调用失败 / 超时：返回 unavailable，卡片给「暂时无法生成 + 重新判断」",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
    dict(text="· 热度、生命周期、图表、B 站数据全部不依赖 AI，照常渲染",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
    dict(text="· 结果按 (meme_id, kind, data_version) 缓存，数据没变不再打接口",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
    dict(text="· 429 / 5xx / 超时会重试，但次数有限（默认 2 次，指数退避），绝不无限重试",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
    dict(text="· API Key 不进前端 bundle、不进日志（有脱敏过滤器）、不进 Git",
         size=10.5, color=INK, space_before=5, line_spacing=1.26),
], warn="d10-right")
band(s, BODY_TOP + 4.66, 0.62,
     "复现命令：cd backend && python -m pytest ｜ python scripts/smoke_api.py（需后端在跑）",
     fill=NAVY_SOFT, color=NAVY, size=10.5, exsize=0)
fin(s)
notes(s, "这一页是给「这不是个课程作业网站吗」这个问题准备的答案。\n"
         "重点讲左边那六条断言——它们说明「口径」不是写在文档里的，是被测试守着的。\n"
         "如果现场有网有环境，可以跑一次 pytest；没环境就报数字并说明命令。\n"
         "右边讲 AI 降级：这是产品设计的一部分，不是容错补丁。")
