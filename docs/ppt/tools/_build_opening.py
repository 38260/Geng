# -*- coding: utf-8 -*-
"""Deck 1 (开题汇报) — part A: slides 1-6.

All numbers are real, read from backend/data/gengv1.db and the documented
falsification experiment. Placeholders sit only where a human must fill in.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gstyle import *  # noqa: F401,F403
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.path.join(HERE, "..", "assets")
ROOT = os.path.dirname(HERE)
COVER = os.path.join(ROOT, "docs", "pitch", "assets", "covers")
F = json.load(open(os.path.join(HERE, "deck_facts.json"), encoding="utf-8"))
TOTAL = 16
MASCOT = os.path.join(ROOT, "docs", "design", "asset-mascot-sign.png")

prs = new_deck()
N = [0]


def add(*, dark=False):
    s = blank(prs)
    canvas(s, dark=dark)
    N[0] += 1
    return s


def fin(s, note="Bilibili 真实采集 · 阈值集中写死在 backend/app/config/algorithms.py"):
    footer(s, N[0], TOTAL, note=note)


def blk(s, x, y, w, h, lines, *, warn=None, pad=1.0):
    return fit_text(s, x, y, w, h, lines, warn=warn or ("s%d" % N[0]), pad=pad)


def kv(s, x, y, w, h, big, label, sub=None, *, color=CORAL, bsize=30,
       fill=WHITE, line=LINE, bigfont=BODY):
    card(s, x, y, w, h, fill=fill, line=line)
    lines = [dict(text=big, size=bsize, color=color, bold=True, font=bigfont),
             dict(text=label, size=12, color=INK, bold=True, space_before=4)]
    if sub:
        lines.append(dict(text=sub, size=10, color=GREY, space_before=3,
                          line_spacing=1.2))
    blk(s, x + 0.26, y + 0.20, w - 0.52, h - 0.36, lines)


def thumb(s, name, x, y, w, h, score, stage, rank=None, tag=None):
    card(s, x, y, w, h, radius=0.06)
    img_h = h * 0.60
    p = os.path.join(COVER, name + ".jpg")
    if os.path.exists(p):
        pic_cover(s, p, x + 0.085, y + 0.085, w - 0.17, img_h)
    else:
        rect(s, x + 0.085, y + 0.085, w - 0.17, img_h, fill=NAVY_SOFT)
    if rank:
        b = rect(s, x + 0.20, y + 0.20, 0.40, 0.40,
                 fill=GOLD if rank == 1 else WHITE, shape=MSO_SHAPE.OVAL)
        b.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(b.text_frame, True, text=str(rank), size=13, bold=True,
             align=PP_ALIGN.CENTER, color=INK)
    ty = y + img_h + 0.20
    lines = [dict(text=name, size=13.5, color=INK, bold=True),
             dict(text="热度 %.1f · %s" % (score, stage), size=10, color=CORAL,
                  bold=True, space_before=3)]
    if tag:
        lines.append(dict(text=tag, size=9.5, color=GREY, space_before=2))
    blk(s, x + 0.18, ty, w - 0.36, y + h - ty - 0.10, lines)


def band(s, y, h, text, *, fill=CORAL_SOFT, color=INK, size=13, w=None,
         x=None, bold=True, extra=None, exsize=11):
    x = MARGIN if x is None else x
    w = CONTENT_W if w is None else w
    card(s, x, y, w, h, fill=fill, line=None)
    lines = [dict(text=text, size=size, color=color, bold=bold)]
    if extra:
        lines.append(dict(text=extra, size=exsize, color=GREY, space_before=4,
                          line_spacing=1.2))
    blk(s, x + 0.32, y + 0.15, w - 0.64, h - 0.28, lines)


# =========================================================================== #
# 1 — cover
# =========================================================================== #
s = add()
rect(s, 0, 0, SW, 5.60, fill=WHITE)
rect(s, 0, 0, 0.22, 5.60, fill=CORAL)
simple(s, MARGIN + 0.10, 0.72, 9.0, 0.32,
       [dict(text="数据科学课程 · 开题汇报", size=14, color=CORAL, bold=True)],
       warn="cover-kicker")
tb = textbox(s, MARGIN + 0.10, 1.06, 9.4, 1.05)
para(tb.text_frame, True, text="今天，赶什么梗？", size=54, color=INK,
     bold=True, font=DISPLAY, line_spacing=1.0)
rect(s, MARGIN + 0.10, 2.22, 1.90, 0.075, fill=CORAL)
simple(s, MARGIN + 0.10, 2.44, 9.0, 0.46,
       [dict(text="B 站网络梗热度与生命周期分析系统", size=19, color=NAVY,
             bold=True)], warn="cover-sub")
blk(s, MARGIN + 0.10, 3.06, 8.60, 2.32, [
    dict(text="开场先问一句", size=12, color=GREY),
    dict(text="「闪身步」9 月 21 日才有人解说，如今热度 76.8，全站第一；"
              "近 7 天头部播放 1,670 万。", size=15, color=INK, bold=True,
         space_before=6, line_spacing=1.3),
    dict(text="从「有人把它讲明白」到「火到不能再拖」，中间只有 5 天。",
         size=13.5, color=NAVY, space_before=7),
    dict(text="这 5 天，就是这个课题要研究的东西。", size=13.5, color=CORAL,
         bold=True, space_before=7),
], warn="cover-hook")
if os.path.exists(MASCOT):
    pic(s, MASCOT, 10.62, 0.98, h=2.05)
simple(s, 10.30, 3.18, 2.35, 0.30,
       [dict(text="今天，赶什么梗？", size=12, color=INK, bold=True,
             font=DISPLAY, align=PP_ALIGN.CENTER)], warn="cover-mascot-cap")
rect(s, 0, 5.60, SW, 1.90, fill=CANVAS)
info = card(s, 9.60, 5.86, 3.10, 1.60, radius=0.10)
blk(s, 9.86, 6.04, 2.58, 1.28, [
    dict(text="汇报人　＿＿＿＿＿＿", size=13, color=INK, bold=True),
    dict(text="学　号　＿＿＿＿＿＿", size=13, color=INK, space_before=6),
    dict(text="指导教师　＿＿＿＿＿＿", size=13, color=INK, space_before=6),
    dict(text="＿＿＿＿ 年 ＿＿ 月 ＿＿ 日", size=10.5, color=GREY,
         space_before=7),
], warn="cover-info")
band(s, 5.86, 1.60, "先把话说在前面：本阶段交付的是「一条跑通的真实数据链路 + 一套可复算的测量口径」，"
                    "不是一堆已经成立的结论。",
     fill=CORAL_SOFT, size=13.5, w=8.60, x=MARGIN,
     extra="里面有一个我自己先立、后被数据推翻的实验（第 11 页）——"
           "我认为那才是这个课题最有价值的部分。")
fin(s, note="数据截至 2026-09-28，真实抓取；演示梗单独标注、不进真实榜单")
notes(s, "开场不要念标题。\n"
         "直接问：有谁听过「闪身步」？——它是 9 月 21 日才被解说、9 月 26 日就冲到榜首的梗。\n"
         "然后主动交底：现在给的是链路和口径，不是结论。把预期压低，后面被追问时不会翻车。\n"
         "数字来源：hotness_snapshots 里「闪身步」= 76.8（爆发期，还来得及，置信度 0.95），"
         "近 7 天头部播放 16,705,446。")

# =========================================================================== #
# 2 — hook
# =========================================================================== #
s = add()
header(s, "先测一下", "这五个梗，认识三个以上的举手",
       sub="不是我编的题——它们就是此刻 B 站真实热榜前五名。封面是真实视频封面，数字是库里现算的。")
names = [("闪身步", 76.8, "爆发期", "爆发期 · 置信度 0.95"),
         ("耍起", 67.2, "上升期", "上升期 · 还来得及"),
         ("闹吃vs古振兴", 54.6, "上升期", "上升期 · 慎赶"),
         ("野生狗奶", 47.5, "上升期", "双 UP 认证 · 慎赶"),
         ("大狗叫", 47.0, "数据不足", "近 7 天只观测到几天")]
x = MARGIN
NCOL = 5
GAP = 0.19
CW = (CONTENT_W - (NCOL - 1) * GAP) / NCOL
for i, (n, sc, st, tg) in enumerate(names):
    thumb(s, n, x, BODY_TOP, CW, 2.98, sc, st, rank=i + 1, tag=tg)
    x += CW + GAP
band(s, BODY_TOP + 3.16, 1.34,
     "认不全太正常了：梗的活跃窗口一般就两三周。难受的地方不在这——"
     "你听说了、点开创作中心、脚本写完发出去，它已经不火了。",
     fill=CORAL_SOFT, size=14,
     extra="注意第 5 名「大狗叫」：热度 47.0 排进前十，但近 7 天真正观测到的天数太少，"
           "算法拒绝给阶段与赶梗结论，标成「数据不足」。宁可说不知道，也不编一个阶段。")
fin(s)
notes(s, "现场互动 10 秒，别恋战。\n"
         "重点落在最后那句：第 5 名被标成「数据不足」。这是全课题的立场——"
         "拿接口空洞判「正在退潮」，是这类产品最不该犯的错。\n"
         "五个名字与分数都来自 lifecycle_snapshots / hotness_snapshots，可现场查库。")

# =========================================================================== #
# 3 — why it hurts
# =========================================================================== #
s = add()
header(s, "问题在哪", "三家人在问同一句话：现在做，还来得及吗",
       sub="他们都缺同一个东西——不是排名，是刻度。")
rows = [
    ("一个 3 万粉的 UP 主", "「这个梗我上周就刷到了，现在拍是不是凉了？」",
     "他有手感，但没有刻度：同一个梗，他每次判断都不一样。", BLUE, BLUE_SOFT),
    ("品牌社媒运营", "「热搜上这个词，我们今晚要不要跟？」",
     "跟的是词，不是梗：词还挂在榜上，梗可能三天前就过气了。", GOLD_DEEP, RGBColor(0xFF, 0xF7, 0xE3)),
    ("我室友（也是目标用户）", "「为什么我每次知道一个梗，它都已经不好玩了？」",
     "因为他拿到的永远是排名，不是时间。", CORAL, CORAL_SOFT),
]
y = BODY_TOP
RH = 1.10
for title, quote, note, ac, bg in rows:
    card(s, MARGIN, y, CONTENT_W, RH, fill=WHITE, line=LINE)
    rect(s, MARGIN, y, 0.055, RH, fill=ac)
    blk(s, MARGIN + 0.34, y + 0.15, 3.10, 0.84, [
        dict(text=title, size=13, color=ac, bold=True),
        dict(text=note, size=10.5, color=GREY, space_before=5,
             line_spacing=1.2)])
    blk(s, MARGIN + 3.70, y + 0.22, CONTENT_W - 4.10, 0.68, [
        dict(text=quote, size=16, color=INK, bold=True, font=DISPLAY)])
    y += RH + 0.15
band(s, y + 0.03, 1.40,
     "现有工具都能回答「此刻什么排在前面」，回答不了三个更值钱的问题——"
     "有多火（一个跨梗可比的数）、走到哪一段（在冲、在顶、还是在崩）、现在赶还来不来得及。",
     fill=NAVY_SOFT, color=NAVY, size=13.5,
     extra="微博热搜与平台热榜是存量快照：一个梗崩盘当天照样挂在榜上；"
           "百度指数度量的是搜索词，不是梗——「松弛感」这类口语词会混进大量无关检索。")
fin(s)
notes(s, "这一页讲「需求真实存在」，用三句原话，不要讲成抽象的市场分析。\n"
         "关键一句：他们要的不是排名，是刻度。\n"
         "如果老师问「这跟热搜有什么不同」：热搜是存量快照 + 关键词，"
         "我们是逐日时间序列 + 梗级聚合，还能给出剩余窗口判断。")

# =========================================================================== #
# 4 — RQ
# =========================================================================== #
s = add()
header(s, "研究问题", "把「还赶不赶得上」拆成三个能被回答的问题",
       sub="每个问题都对应一个已实现的算法模块；不能量化的一律不做。")
rqs = [
    ("RQ1", "一个梗现在到底有多火？", CORAL, CORAL_SOFT,
     ["输出 0-100 热度指数：五因子加权，绝对量先做对数区间归一化",
      "同一个数可以横向比两个梗，也可以纵向比一个梗的两周",
      "实现：backend/app/analytics/hotness.py"]),
    ("RQ2", "它走到了生命周期的哪一段？", NAVY, NAVY_SOFT,
     ["六个阶段：萌芽 / 上升 / 爆发 / 平稳 / 退潮 / 过气",
      "只用四个可观测量判定：增长率、距峰值差、连续下滑天数、活跃度",
      "实现：backend/app/analytics/lifecycle.py（规则自上而下匹配）"]),
    ("RQ3", "现在赶还来得及吗？", GOLD_DEEP, RGBColor(0xFF, 0xF7, 0xE3),
     ["三态输出：还来得及 / 慎赶 / 你来晚了，附带置信度与一句理由",
      "由 RQ1 + RQ2 结果经判定规则导出，不是独立模型猜的",
      "实现：backend/app/analytics/catch_up.py"]),
]
x = MARGIN
NCOL = 3
CW = (CONTENT_W - (NCOL - 1) * 0.17) / NCOL
for code, title, ac, bg, bullets in rqs:
    card(s, x, BODY_TOP, CW, 3.36, fill=WHITE, line=LINE)
    rect(s, x, BODY_TOP, CW, 0.075, fill=ac)
    tag = card(s, x + 0.28, BODY_TOP + 0.26, 0.80, 0.36, fill=bg, line=None,
               radius=0.26)
    tag.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    para(tag.text_frame, True, text=code, size=12, color=ac, bold=True,
         align=PP_ALIGN.CENTER)
    lines = [dict(text=title, size=15.5, color=INK, bold=True, space_before=6,
                  line_spacing=1.18)]
    for b in bullets:
        lines.append(dict(text="· " + b, size=10.5, color=GREY, space_before=6,
                          line_spacing=1.24))
    blk(s, x + 0.28, BODY_TOP + 0.78, CW - 0.56, 2.36, lines)
    x += CW + 0.17
band(s, BODY_TOP + 3.56, 1.42,
     "明确不做的三件事，写在幻灯片上，也写在代码里：",
     fill=NAVY_SOFT, color=NAVY, size=13,
     extra="① 不做未来数值预测，只描述已经发生的数据；"
           "② 不让大模型修改任何事实或判定——它只能把算法结论翻译成人话，"
           "越界表述（「预计」「一定会爆」）在服务层直接丢弃；"
           "③ 不做多平台、不做用户体系，先把 B 站这一把尺子做准。")
fin(s)
notes(s, "这一页是全场的技术骨架，讲慢一点。\n"
         "三个问题的顺序有讲究：先有可比的数，才有阶段，才有「赶不赶」。"
         "反过来做（先问赶不赶）就是拍脑袋。\n"
         "老师最容易问「为什么不用深度学习预测」——答案在 RQ3 那句："
         "本课题的输出是判定问题，不是外推问题；而且样本量撑不起深度模型"
         "（84 条梗记录、2,209 行日统计）。")

# =========================================================================== #
# 5 — literature gap
# =========================================================================== #
s = add()
header(s, "文献位置", "三条线各自都做到了，缺的是把它们接起来的那个人",
       sub="不是没人研究，是没人把「梗」当成一个能跨创作者聚合、还能复算的时间序列对象。")
cols = [
    ("模因与网络梗研究", NAVY, "定义、分类、生成机制、社会心态", 
     "Dawkins 1976 · Shifman 2012/2013 · Bauckhage ICWSM 2011 · 谢朝群 2007 · 薛一飞 2024",
     "几乎不给出可复算的时间度量"),
    ("注意力与话题生命周期", BLUE, "曲线形状可分类、半衰期在缩短、阶段可划分",
     "Downs 1972 · Crane & Sornette PNAS 2008 · Kleinberg KDD 2002 · Yang & Leskovec WSDM 2011 · Lorenz-Spreen 2019",
     "对象是新闻 / 议题 / 搜索词，不是「梗」"),
    ("流行度量化与预测", GOLD_DEEP, "早期增速可预测、热度寿命可建模",
     "Szabo & Huberman CACM 2010 · Tan BMSB 2014 · Li 2016 · Xu CIKM 2025",
     "落到单条内容，未做跨创作者的「梗」级聚合"),
]
x = MARGIN
NCOL = 3
CW = (CONTENT_W - (NCOL - 1) * 0.17) / NCOL
for title, ac, got, cites, gap in cols:
    card(s, x, BODY_TOP, CW, 3.20, fill=WHITE, line=LINE)
    rect(s, x, BODY_TOP, CW, 0.075, fill=ac)
    lines = [
        dict(text=title, size=14.5, color=INK, bold=True),
        dict(text="做到了什么", size=10, color=ac, bold=True, space_before=12),
        dict(text=got, size=11.5, color=INK, space_before=3, line_spacing=1.24),
        dict(text="代表工作", size=10, color=ac, bold=True, space_before=12),
        dict(text=cites, size=9.5, color=GREY, line_spacing=1.22),
        dict(text="留下的缺口", size=10, color=CORAL, bold=True, space_before=12),
        dict(text=gap, size=11.5, color=INK, space_before=3, line_spacing=1.24),
    ]
    blk(s, x + 0.28, BODY_TOP + 0.28, CW - 0.56, 2.68, lines)
    x += CW + 0.17
band(s, BODY_TOP + 3.40, 1.58,
     "本课题的位置：把三条线接成一条能跑起来的链路。",
     fill=CORAL_SOFT, size=14,
     extra="用两位解说 UP 主的真实投稿证明「这是个真梗」→ 用逐日头部内容抽样把它变成时间序列 → "
           "用五因子指数与规则引擎给出热度、阶段与赶梗判断 → 把全部口径与数据新鲜度"
           "直接印在产品界面上。文献核验记录（DOI / CNKI）在 docs/research/related-literature.md。")
fin(s)
notes(s, "这一页不要逐条念文献。只讲结构：三条线、三个缺口、一个位置。\n"
         "如果老师是传播学背景，重点接 Lorenz-Spreen 2019（注意力半衰期在缩短）——"
         "它说明「还剩多久」比「有多热」更值钱，直接支撑 RQ3。\n"
         "如果老师是数据挖掘背景，重点接 Szabo & Huberman 2010（早期增速可预测）——"
         "它支撑我们把增长权重给到 0.25。\n"
         "所有 DOI 都核验过，被质疑引用可当场翻 docs/research/related-literature.md。")

# =========================================================================== #
# 6 — feasibility: the pipeline already runs
# =========================================================================== #
s = add()
header(s, "可行性：不是设想", "这条链路已经跑通了，今天的数字都是它算出来的",
       sub="先把「能不能做」回答掉，后面才轮得到「做得对不对」。",
       tag="已可运行")
# pipeline
steps = [("B 站接口", NAVY), ("逐日采集", NAVY), ("清洗 + 梗匹配", NAVY),
         ("发现层准入", CORAL), ("日粒度聚合", NAVY), ("热度指数", CORAL),
         ("生命周期", CORAL), ("赶梗判断", CORAL), ("FastAPI", NAVY),
         ("React", NAVY)]
x = MARGIN
NCOL = 10
CW = (CONTENT_W - (NCOL - 1) * 0.045) / NCOL
for i, (t, c) in enumerate(steps):
    card(s, x, BODY_TOP, CW, 0.86, fill=WHITE if c == NAVY else CORAL_SOFT,
         line=LINE if c == NAVY else None, radius=0.14)
    blk(s, x + 0.06, BODY_TOP + 0.10, CW - 0.12, 0.66,
        [dict(text=t, size=11, color=c if c == NAVY else CORAL, bold=True,
              align=PP_ALIGN.CENTER, line_spacing=1.1)])
    x += CW + 0.045
simple(s, MARGIN, BODY_TOP + 0.98, CONTENT_W, 0.26,
       [dict(text="数据负责证明　·　算法负责判断　·　大模型负责解释　·　界面负责让人想看",
             size=11, color=GREY, align=PP_ALIGN.CENTER)])
kvs = [
    ("69", "后端 Python 模块", "10,409 行；另有 22 个测试文件 4,507 行", CORAL),
    ("279", "后端测试全绿", "假客户端 + 内存库，全部离线可复跑", NAVY),
    ("125", "接口冒烟用例", "对着运行中的真实后端逐个打过去", NAVY),
    ("31", "前端 TS/TSX 文件", "4,666 行，Vite 构建产物 204KB（gzip 66KB）", NAVY),
    ("11", "秒", "依赖就绪时 start.bat 一键起前后端；空库自动灌演示数据", GOLD_DEEP),
]
x = MARGIN
NCOL = 5
GAP = 0.19
CW = (CONTENT_W - (NCOL - 1) * GAP) / NCOL
for big, label, sub, c in kvs:
    kv(s, x, BODY_TOP + 1.34, CW, 1.28, big, label, sub, color=c, bsize=26)
    x += CW + GAP
band(s, BODY_TOP + 2.72, 0.86,
     "数据可得性也验证过了，不是假设：WBI 签名后匿名可用的只有搜索与视频详情接口。",
     fill=NAVY_SOFT, color=NAVY, size=12.5,
     extra="UP 主空间接口会被风控（-352 / 412），字幕轨与站内 AI 总结端点匿名一律拿不到"
           "（实测 code=0 但 subtitles 为空、总结接口直接 -101 未登录）。"
           "这两件事都如实写进了产品的「数据透明度」，没有拿旧证据凑数。")
fin(s)
notes(s, "这一页的作用是让老师放心：这不是一个 PPT 项目。\n"
         "建议现场直接演示 start.bat（约 11 秒）。\n"
         "数字出处：LOC 与测试数用仓库实测统计；279 项由 python -m pytest 收集得出；"
         "125 项来自 scripts/smoke_api.py。\n"
         "最后那条限制很重要，主动说：字幕这一档要 Cookie 才有，"
         "所以界面上「字幕原文摘录」现在可能是空的——那是如实标注，不是坏掉。")

prs.save(os.path.join(HERE, "deck_proposal_A.pptx"))
print("part A ok, slides:", N[0])

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

prs.save(os.path.join(HERE, "..", "赶梗潮-开题汇报.pptx"))
print("opening deck ok, slides:", N[0])
