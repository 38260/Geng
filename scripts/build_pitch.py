"""生成《赶梗潮》数据科学课程开题答辩 PPT（真·pptx，可课堂放映、可自己改）。

    python scripts/build_pitch.py        # 产出 docs/pitch/赶梗潮-开题答辩.pptx

依赖 scripts/pitch_assets.py 先生成 facts.json 与四张图（数字全部从真实库现取）。
版式刻意不用 PowerPoint 默认占位符：整页自己排版，配色取自产品前端的设计令牌，
这样答辩稿看起来像这个产品自己的东西，而不是套模板。
正文里的引用一律用「」，不用 ASCII 引号——既符合中文排版，也不会把 Python 字符串截断。
"""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "pitch"
ASSETS = OUT_DIR / "assets"
FACTS = json.loads((OUT_DIR / "facts.json").read_text(encoding="utf-8"))
TARGET = OUT_DIR / "赶梗潮-开题答辩.pptx"

# 设计令牌（与 frontend/tailwind.config.js 同一套）
CANVAS = RGBColor(0xF7, 0xFA, 0xFD)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x00, 0x02, 0x14)
INK_SOFT = RGBColor(0x3C, 0x59, 0x89)
INK_MUTE = RGBColor(0x5E, 0x73, 0x9F)
INK_FAINT = RGBColor(0xB0, 0xBA, 0xD0)
LINE = RGBColor(0xEC, 0xF0, 0xF6)
BRAND = RGBColor(0xFB, 0x3A, 0x5E)
BRAND_SOFT = RGBColor(0xFD, 0xE9, 0xEE)
FLARE = RGBColor(0x0D, 0x8A, 0xFE)
GO = RGBColor(0x01, 0x96, 0x46)
GO_SOFT = RGBColor(0xE5, 0xFC, 0xF2)
GOLD = RGBColor(0xC8, 0x8A, 0x14)
GOLD_SOFT = RGBColor(0xFF, 0xF3, 0xDC)
DUSK = RGBColor(0x54, 0x6F, 0x98)

SANS = "Microsoft YaHei"
BRUSH = "KaiTi"          # 封面标题用楷体，避开企业报表感；Windows 自带

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def new_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = CANVAS
    bg.line.fill.background()
    bg.shadow.inherit = False
    return slide


def rect(slide, x, y, w, h, *, fill=WHITE, line=LINE, radius=0.09, weight=1.0):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    if radius:
        shape.adjustments[0] = radius
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(weight)
    shape.shadow.inherit = False
    return shape


def text(slide, x, y, w, h, runs, *, size=14, color=INK, bold=False, font=SANS,
         align=PP_ALIGN.LEFT, spacing=1.18, anchor=MSO_ANCHOR.TOP, space_after=4):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    paragraphs = runs if isinstance(runs, list) and runs and isinstance(runs[0], list) else [runs]
    for index, paragraph in enumerate(paragraphs):
        para = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        para.alignment = align
        para.line_spacing = spacing
        para.space_after = Pt(space_after)
        pieces = paragraph if isinstance(paragraph, list) else [(paragraph, {})]
        for piece in pieces:
            value, style = (piece, {}) if isinstance(piece, str) else piece
            run = para.add_run()
            run.text = value
            run.font.size = Pt(style.get("size", size))
            run.font.bold = style.get("bold", bold)
            run.font.name = style.get("font", font)
            run.font.color.rgb = style.get("color", color)
    return box


def kicker(slide, label, *, page=None, color=BRAND):
    rect(slide, 0.62, 0.52, 0.16, 0.16, fill=color, radius=0, line=None)
    text(slide, 0.88, 0.42, 8.6, 0.36, label, size=12.5, color=color, bold=True)
    if page is not None:
        text(slide, 11.6, 0.42, 1.1, 0.36, f"{page:02d}", size=12.5,
             color=INK_FAINT, bold=True, align=PP_ALIGN.RIGHT)


def headline(slide, x, y, w, lines, *, size=30):
    text(slide, x, y, w, 1.15, lines, size=size, color=INK, bold=True, spacing=1.06)


def stat(slide, x, y, w, value, label, *, color=BRAND, sub=""):
    rect(slide, x, y, w, 1.32, fill=WHITE)
    text(slide, x + 0.22, y + 0.16, w - 0.44, 0.5, value, size=25, color=color, bold=True)
    body = [[(label, {})]]
    if sub:
        body.append([(sub, {"size": 10.5, "color": INK_MUTE})])
    text(slide, x + 0.22, y + 0.7, w - 0.44, 0.56, body, size=12, color=INK_MUTE, spacing=1.16,
         space_after=1)


def card(slide, x, y, w, h, title, body, *, accent=BRAND):
    rect(slide, x, y, w, h, fill=WHITE)
    rect(slide, x, y + 0.16, 0.055, h - 0.32, fill=accent, radius=0, line=None)
    text(slide, x + 0.3, y + 0.18, w - 0.6, 0.4, title, size=14.5, color=INK, bold=True)
    text(slide, x + 0.3, y + 0.62, w - 0.6, h - 0.8, body, size=12, color=INK_SOFT, spacing=1.28)


def chip(slide, x, y, w, label, *, fill=CANVAS, color=INK_MUTE):
    rect(slide, x, y, w, 0.32, fill=fill, radius=0.5, line=None)
    text(slide, x, y + 0.05, w, 0.3, label, size=11, color=color, bold=True, align=PP_ALIGN.CENTER)


def pic(slide, name, x, y, w):
    return slide.shapes.add_picture(str(ASSETS / name), Inches(x), Inches(y), width=Inches(w))


def footer(slide, note):
    text(slide, 0.62, 6.94, 12.1, 0.34, note, size=10.5, color=INK_FAINT)


# --------------------------------------------------------------------------- #
def slide_cover(prs):
    counts = FACTS["counts"]
    slide = blank(prs)
    rect(slide, 0, 0, 13.333, 3.16, fill=RGBColor(0xFE, 0xF0, 0xF5), line=None)
    rect(slide, 0.62, 3.66, 2.6, 0.13, fill=BRAND, radius=0, line=None)
    text(slide, 0.62, 1.06, 9.0, 0.4, "数据科学课程 · 开题答辩", size=13.5, color=BRAND, bold=True)
    text(slide, 0.56, 1.46, 11.8, 1.5, "今天，赶什么梗？", size=62, color=INK, bold=True, font=BRUSH)
    text(slide, 0.62, 2.66, 11.0, 0.5, "B 站网络梗热度与生命周期分析系统", size=21, color=INK_SOFT, bold=True)
    text(slide, 0.62, 4.06, 11.6, 0.9, [
        [("热搜榜已经会告诉你什么在爆。它回答另外三件事：", {"size": 15, "color": INK_MUTE})],
        [("有多火 · 现在什么阶段 · 现在赶还来得及吗", {"size": 20, "color": INK, "bold": True})],
    ], spacing=1.4)
    rect(slide, 0.62, 5.3, 6.6, 1.3, fill=WHITE)
    text(slide, 0.92, 5.48, 6.1, 1.0, [
        [("开场先问一句", {"size": 12, "color": INK_MUTE})],
        [("「闪身步」9 月 21 日才被人解说，9 月 26 日热度 81 分居榜首。", {"size": 14, "color": INK, "bold": True})],
        [("你现在才听说它，算早还是算晚？这套系统就是来给个准数的。", {"size": 12.5, "color": INK_SOFT})],
    ], spacing=1.32, space_after=2)
    text(slide, 7.62, 5.5, 5.1, 1.0, [
        [("汇报人 ____________", {"size": 13.5, "color": INK, "bold": True})],
        [("学号 ____________    指导教师 ________", {"size": 12.5, "color": INK_MUTE})],
        [(f"数据截至 {counts['through']}，真实抓取，非样例数据", {"size": 11.5, "color": INK_FAINT})],
    ], spacing=1.4)
    return slide


def slide_hook(prs, page):
    slide = blank(prs)
    kicker(slide, "开场 · 现场测一下", page=page)
    headline(slide, 0.62, 0.94, 11.8, "这五个梗，现场能认出三个以上的同学请举手")
    text(slide, 0.62, 1.7, 11.6, 0.4, "它们都是最近 30 天 B 站真实热度榜上的前五名",
         size=13.5, color=INK_MUTE)
    for index, row in enumerate(FACTS["top"][:5]):
        x = 0.62 + index * 2.46
        rect(slide, x, 2.28, 2.28, 2.5, fill=WHITE)
        rect(slide, x + 0.16, 2.44, 0.5, 0.5, fill=BRAND if index == 0 else GOLD_SOFT, radius=0.3, line=None)
        text(slide, x + 0.16, 2.52, 0.5, 0.4, str(index + 1), size=15,
             color=WHITE if index == 0 else GOLD, bold=True, align=PP_ALIGN.CENTER)
        text(slide, x + 0.18, 3.1, 1.98, 0.5, row["name"], size=17, color=INK, bold=True)
        text(slide, x + 0.18, 3.66, 1.98, 0.4, f"热度 {row['score']}", size=15, color=BRAND, bold=True)
        text(slide, x + 0.18, 4.1, 1.98, 0.6, [
            [(row["stage"], {"size": 11.5, "color": INK_SOFT})],
            [(row["cert"], {"size": 10.5, "color": INK_FAINT})],
        ], spacing=1.2, space_after=1)
    rect(slide, 0.62, 5.08, 12.1, 1.46, fill=WHITE)
    text(slide, 0.94, 5.26, 11.5, 1.1, [
        [("认不出来很正常——梗的活跃窗口通常只有两三周。", {"size": 14, "color": INK, "bold": True})],
        [("真正难受的不是没听过，而是：你听说了、点进创作中心、写完脚本发出去，它已经不火了。"
          "本课题要量化的正是这段还剩多少时间。", {"size": 13, "color": INK_SOFT})],
    ], spacing=1.34)
    return slide


def slide_problem(prs, page):
    slide = blank(prs)
    kicker(slide, "问题定义", page=page)
    headline(slide, 0.62, 0.94, 11.9, "现成工具都在报「现在什么在爆」，没人报「这个梗还剩几天」")
    rows = [
        ("微博热搜 / B 站热门", "存量快照", "只告诉你此刻谁在前面，不看趋势形状；一个梗崩盘当天照样能挂在榜上。", DUSK),
        ("百度指数 / 巨量算数", "搜索词", "搜的是词不是梗，「松弛感」这类口语词混进大量无关搜索，也不分阶段。", FLARE),
        ("UP 主凭手感", "个人经验", "选题靠刷，刷到往往已晚两天；同一个人判断「早晚」每次都不一样。", GOLD),
    ]
    text(slide, 0.62, 1.84, 6.6, 0.4, "三类现成做法各差在哪", size=14, color=INK_MUTE, bold=True)
    for index, (name, kind, gap, color) in enumerate(rows):
        y = 2.3 + index * 1.04
        rect(slide, 0.62, y, 6.7, 0.92, fill=WHITE)
        rect(slide, 0.62, y + 0.14, 0.055, 0.64, fill=color, radius=0, line=None)
        text(slide, 0.86, y + 0.12, 4.4, 0.4, name, size=14.5, color=INK, bold=True)
        chip(slide, 5.66, y + 0.16, 1.5, kind, color=color)
        text(slide, 0.86, y + 0.5, 6.3, 0.42, gap, size=11.5, color=INK_SOFT)
    rect(slide, 7.6, 1.84, 5.12, 3.5, fill=BRAND_SOFT, line=None)
    text(slide, 7.94, 2.06, 4.5, 0.4, "本课题要补的那一格", size=13.5, color=BRAND, bold=True)
    text(slide, 7.94, 2.56, 4.5, 2.6, [
        [("把「梗」当成一个可测量的时间序列对象：", {"size": 14, "color": INK, "bold": True})],
        [("", {"size": 5})],
        [("· 有口径的热度值，不是排名，是可比的分数", {"size": 12.5, "color": INK_SOFT})],
        [("· 有规则的阶段判定，萌芽到爆发再到过气", {"size": 12.5, "color": INK_SOFT})],
        [("· 有置信度的赶梗结论：还来得及 / 慎赶 / 你来晚了", {"size": 12.5, "color": INK_SOFT})],
    ], spacing=1.32, space_after=2)
    footer(slide, "缺口不是数据不够多，而是没人把「还剩多久」当成一个可以被证伪的问题来定义。")
    return slide


def slide_rq(prs, page):
    slide = blank(prs)
    kicker(slide, "研究问题与边界", page=page)
    headline(slide, 0.62, 0.94, 11.9, "三个能回答、也能被证伪的问题，以及三件明确不做的事")
    rqs = [
        ("RQ1", "一个梗现在有多火？",
         "构造 0-100 的自定义热度指数：播放 / 互动 / 内容量 / 创作者 / 增长五因子加权，绝对量先做对数区间归一。"),
        ("RQ2", "它处在生命周期的哪一段？",
         "用时间序列特征（增长率、距峰值差、连续下滑天数、活跃度）跑规则引擎，落到六个阶段之一。"),
        ("RQ3", "现在赶这个梗，来得及吗？",
         "把 RQ1/RQ2 的输出交给判定规则，给三态结论 + 置信度 + 一句人话理由。"),
    ]
    for index, (tag, title, body) in enumerate(rqs):
        y = 1.98 + index * 1.18
        rect(slide, 0.62, y, 7.1, 1.04, fill=WHITE)
        text(slide, 0.86, y + 0.14, 0.7, 0.4, tag, size=13, color=BRAND, bold=True)
        text(slide, 1.5, y + 0.12, 6.0, 0.4, title, size=15, color=INK, bold=True)
        text(slide, 1.5, y + 0.52, 6.0, 0.5, body, size=11.5, color=INK_SOFT, spacing=1.26)
    rect(slide, 7.98, 1.98, 4.74, 3.52, fill=WHITE)
    text(slide, 8.26, 2.16, 4.2, 0.4, "V1 刻意不做（做了必挨问）", size=13.5, color=INK, bold=True)
    text(slide, 8.26, 2.62, 4.2, 2.8, [
        [("不做未来数值预测", {"size": 12.5, "color": BRAND, "bold": True})],
        [("只描述已经发生的数据，不宣称「下周会爆」。", {"size": 11.5, "color": INK_MUTE})],
        [("不让大模型改任何事实", {"size": 12.5, "color": BRAND, "bold": True})],
        [("LLM 只写解释文案；它给的状态与算法不一致时以算法为准，越界表述直接丢弃。", {"size": 11.5, "color": INK_MUTE})],
        [("不做多平台、不做用户体系", {"size": 12.5, "color": BRAND, "bold": True})],
        [("只测 B 站，先把一把尺子做准，不追覆盖面。", {"size": 11.5, "color": INK_MUTE})],
    ], spacing=1.24, space_after=2)
    footer(slide, "边界写清楚不是缩水，是让每个结论都能被检验：能算错，也算得出来谁对。")
    return slide


def slide_data(prs, page):
    counts = FACTS["counts"]
    slide = blank(prs)
    kicker(slide, "数据 · 从哪来，有多少", page=page, color=FLARE)
    headline(slide, 0.62, 0.94, 11.9, "全部真实抓取：没有一条数据是我编的，也没有一条拿样例顶")
    stat(slide, 0.62, 1.9, 2.9, f"{counts['memes']}", "梗库总量", color=FLARE,
         sub=f"其中 {counts['admitted']} 个通过准入")
    stat(slide, 3.7, 1.9, 2.9, f"{counts['stat_rows']:,}", "梗 × 天 日统计行", color=FLARE,
         sub=f"{counts['stat_days_with_content']} 行真有内容")
    stat(slide, 6.78, 1.9, 2.9, f"{counts['videos']:,}", "采信视频样本", color=FLARE,
         sub="过相关性阈值才入库")
    stat(slide, 9.86, 1.9, 2.86, f"{counts['views_total'] / 1e8:.2f} 亿", "头部样本累计播放", color=FLARE,
         sub=f"统计截至 {counts['through']}")
    rect(slide, 0.62, 3.5, 6.6, 3.06, fill=WHITE)
    text(slide, 0.9, 3.68, 6.1, 0.4, "采集口径三条，都是踩坑换来的", size=14, color=INK, bold=True)
    text(slide, 0.9, 4.16, 6.1, 2.3, [
        [("① 按天带时间区间查询", {"size": 12.5, "color": FLARE, "bold": True})],
        [("每天单独取 pubtime_begin / end；一次抓完再回填历史，算出过 +23616% 的假增长。", {"size": 12, "color": INK_SOFT})],
        [("② 当日头部 20 条相关视频当样本", {"size": 12.5, "color": FLARE, "bold": True})],
        [("所以「当日播放量」是头部内容的合计，跨日跨梗同一把尺子，不是全站绝对量。", {"size": 12, "color": INK_SOFT})],
        [("③ 统计窗口不含今天", {"size": 12.5, "color": FLARE, "bold": True})],
        [("今天还没过完，计入会让头部样本偏低、增幅出现假下跌。", {"size": 12, "color": INK_SOFT})],
    ], spacing=1.22, space_after=2)
    rect(slide, 7.48, 3.5, 5.24, 3.06, fill=WHITE)
    text(slide, 7.76, 3.68, 4.7, 0.4, "梗的存在性证明：两位解说 UP 主", size=14, color=INK, bold=True)
    text(slide, 7.76, 4.16, 4.7, 2.3, [
        [("梗百科 ", {"size": 13, "color": INK, "bold": True}),
         ("日更，90 天内 41 条投稿、识别出 37 个梗名", {"size": 12, "color": INK_SOFT})],
        [("梗指南 ", {"size": 13, "color": INK, "bold": True}),
         ("周更，22 条投稿、22 个梗名", {"size": 12, "color": INK_SOFT})],
        [("", {"size": 5})],
        [("为什么拿他们当入口：一个梗值不值得被记录，先要看有没有人把它讲明白过。"
          "证据是真实 BV 号、标题与发布时间，页面上能直接点开验证。", {"size": 12, "color": INK_SOFT})],
    ], spacing=1.26, space_after=2)
    footer(slide, "接口：B 站 wbi 搜索 + 视频详情，匿名设备指纹 + WBI 签名；空间投稿接口按会话风控，深翻页会被 412 / -352 拦下。")
    return slide


def slide_discovery(prs, page):
    cov = FACTS["coverage"]
    slide = blank(prs)
    kicker(slide, "方法 · 发现层", page=page)
    headline(slide, 0.62, 0.94, 11.9, "准入规则从「交集」改成「并集」，是被一个漏掉的梗逼出来的")
    pic(slide, "coverage.png", 0.62, 1.94, 6.1)
    rect(slide, 7.0, 1.94, 5.72, 1.6, fill=WHITE)
    text(slide, 7.28, 2.12, 5.2, 1.3, [
        [("旧口径：两位 UP 主都介绍过才算数。", {"size": 13, "color": INK, "bold": True})],
        [(f"90 天实测：梗百科 37 个、梗指南 22 个，交集只剩 {cov['intersection']} 个。"
          "等于让日更 UP 的选题被周更 UP 的排期一票否决。", {"size": 12.5, "color": INK_SOFT})],
    ], spacing=1.28)
    rect(slide, 7.0, 3.7, 5.72, 1.6, fill=GO_SOFT, line=None)
    text(slide, 7.28, 3.88, 5.2, 1.3, [
        [("新口径：任一 UP 主 90 天内介绍过即入池。", {"size": 13, "color": GO, "bold": True})],
        [(f"同一批投稿，池子从 {cov['intersection']} 个变成 {cov['union']} 个；两位都做过的仍然单独标"
          "「双 UP 认证」，只是降级成标签而不是闸门。", {"size": 12.5, "color": INK_SOFT})],
    ], spacing=1.28)
    rect(slide, 0.62, 5.52, 12.1, 1.06, fill=WHITE)
    text(slide, 0.9, 5.68, 11.6, 0.8, [
        [("两个窗口必须分开，这是最贵的一课：", {"size": 13, "color": BRAND, "bold": True}),
         ("解说视频通常比梗的爆发期早 1~2 周。我一开始拿 30 天报告窗口同时当认证窗口用，"
          "结果把 8 月 21 日解说的「老叟戏顽童」整条排除在外，还据此断言两位 UP 都没做过——被当场指出。",
          {"size": 12.5, "color": INK_SOFT})],
    ], spacing=1.3)
    return slide


def slide_hotness(prs, page):
    slide = blank(prs)
    kicker(slide, "方法 · 度量层", page=page)
    headline(slide, 0.62, 0.94, 11.9, "热度指数：一条爆款视频吃不掉整个榜")
    pic(slide, "weights.png", 0.62, 1.96, 6.6)
    rect(slide, 0.62, 4.56, 6.6, 2.0, fill=WHITE)
    text(slide, 0.9, 4.74, 6.1, 1.7, [
        [("Hotness = 0.25·增长 + 0.25·播放 + 0.20·互动 + 0.16·内容 + 0.14·创作者",
          {"size": 12.5, "color": INK, "bold": True})],
        [("每个因子先做对数区间归一化再加权：播放量差三个量级的梗要能同框比较，"
          "线性归一会让亿级老梗永远压着新梗。", {"size": 12, "color": INK_SOFT})],
    ], spacing=1.32)
    rect(slide, 7.5, 1.96, 5.22, 4.6, fill=WHITE)
    text(slide, 7.78, 2.14, 4.7, 0.4, "三个反直觉的设计决定", size=14, color=INK, bold=True)
    items = [
        ("增长权重给到 0.25", "只看最近 7 天对前 7 天。去年 1 亿播放、今天没人做的梗不会赖在榜首。"),
        ("样本太小就不外推", "前一周讨论量 < 30 或样本视频 < 3 条时增长率直接置空——考古区冒出一条视频不算 +100%。"),
        ("人工改不到分数", "封面、介绍、别名、关键词可以人工维护；热度、阶段、赶梗结论只由算法产出，接口层强制。"),
    ]
    for index, (title, body) in enumerate(items):
        y = 2.66 + index * 1.28
        rect(slide, 7.78, y, 0.32, 0.32, fill=BRAND_SOFT, radius=0.5, line=None)
        text(slide, 7.78, y + 0.04, 0.32, 0.3, str(index + 1), size=11, color=BRAND, bold=True,
             align=PP_ALIGN.CENTER)
        text(slide, 8.22, y - 0.02, 4.3, 0.4, title, size=13, color=INK, bold=True)
        text(slide, 8.22, y + 0.38, 4.3, 0.84, body, size=11.5, color=INK_SOFT, spacing=1.26)
    return slide


def slide_lifecycle(prs, page):
    slide = blank(prs)
    kicker(slide, "方法 · 生命周期与赶梗判断", page=page)
    headline(slide, 0.62, 0.94, 11.9, "同样是 80 分，一个在冲、一个在崩，结论就不能一样")
    pic(slide, "curves.png", 0.62, 1.9, 7.3)
    text(slide, 0.62, 4.66, 7.3, 0.6,
         "闪身步 09-13 起从零爬到 81（爆发期）；琵琶曲是脉冲型，冲高后 09-25 断崖；"
         "老叟戏顽童从 84 一路退到 52（退潮期）。", size=11.5, color=INK_MUTE, spacing=1.26)
    rect(slide, 8.2, 1.9, 4.52, 3.36, fill=WHITE)
    text(slide, 8.46, 2.08, 4.0, 0.4, "六个阶段，规则自上而下匹配", size=13.5, color=INK, bold=True)
    text(slide, 8.46, 2.54, 4.0, 1.6, [
        [("萌芽 → 上升 → 爆发 → 平稳 → 退潮 → 过气", {"size": 12.5, "color": INK, "bold": True})],
        [("判定只用四件事：增长率、距峰值差、连续下滑天数、活跃度。"
          "阈值全部集中在一个配置文件里，可复算、可讨论。", {"size": 11.5, "color": INK_SOFT})],
    ], spacing=1.3)
    rect(slide, 8.46, 4.12, 3.94, 0.94, fill=GO_SOFT, line=None)
    text(slide, 8.62, 4.22, 3.7, 0.8, [
        [("赶梗三态由算法给：", {"size": 11.5, "color": GO, "bold": True})],
        [("还来得及 / 慎赶 / 你来晚了，附置信度与理由", {"size": 11, "color": INK_SOFT})],
    ], spacing=1.2)
    rect(slide, 0.62, 5.4, 12.1, 1.18, fill=WHITE)
    text(slide, 0.9, 5.56, 11.6, 1.0, [
        [("LLM 在这里只干一件事：把算法已经定好的结论翻译成人话。", {"size": 13.5, "color": INK, "bold": True})],
        [("它不许改状态、不许预测。模型返回的 status 与算法不一致时以算法为准；"
          "文案里出现「预计」「未来 7 天」「一定会爆」这类预测口吻会被直接丢弃。", {"size": 12, "color": INK_SOFT})],
    ], spacing=1.3)
    return slide


def slide_pitfalls(prs, page):
    slide = blank(prs)
    kicker(slide, "真实数据最好玩的部分：它脏得毫不讲理", page=page)
    headline(slide, 0.62, 0.94, 11.9, "四个我亲自踩出来的坑，每个都改掉了口径")
    cards = [
        ("假增长 +23,616%", "第一版一次抓完再按天聚合，等于拿今天看到的播放量回填历史某一天。",
         "改成逐日带时间区间查询，只统计当天发布的头部内容。", BRAND),
        ("418 条样本里 343 条在讲黄豆", "「我不是黄豆」的别名写成黄豆，于是琵琶曲黄豆版、炒黄豆、树叶做豆腐全被灌进来，该梗还挂着榜首。",
         "短于 4 字的别名只算弱证据，必须再有第二个词佐证才能过阈值。", FLARE),
        ("真梗被闸门挡在库外", "交集口径 90 天只剩 8 个梗，热度实测最高的闪身步（81.0）根本进不来。",
         "准入改并集，认证窗口独立 90 天滚动，双 UP 降级为标签。", GO),
        ("刷新把数据刷薄了", "同一个词同一天两次返回的头部 20 条差很远：琵琶曲 4 天 / 3,976 万播放被刷成 1 天 / 18 条，热度 44.2 → 0.0。",
         "同一天只保留更好的一次观测（比样本数与播放量，绝不相加），并从快照回填 53 天。", GOLD),
    ]
    for index, (title, story, fix, color) in enumerate(cards):
        x = 0.62 + (index % 2) * 6.22
        y = 1.92 + (index // 2) * 2.2
        rect(slide, x, y, 5.9, 2.02, fill=WHITE)
        rect(slide, x, y + 0.14, 0.055, 1.74, fill=color, radius=0, line=None)
        text(slide, x + 0.26, y + 0.14, 5.4, 0.4, title, size=14.5, color=INK, bold=True)
        text(slide, x + 0.26, y + 0.58, 5.4, 0.8, story, size=11.5, color=INK_SOFT, spacing=1.26)
        text(slide, x + 0.26, y + 1.46, 5.4, 0.5,
             [("修法  ", {"size": 11, "color": color, "bold": True}), (fix, {"size": 11.5, "color": INK})],
             spacing=1.2)
    footer(slide, "这四个坑都不是会报错的那种，而是口径错了但每个数都算得出来——最难查的一类。")
    return slide


def slide_falsify(prs, page):
    corr = FACTS["correlation"]
    slide = blank(prs)
    kicker(slide, "把直觉拿去跟数据对一遍", page=page, color=FLARE)
    headline(slide, 0.62, 0.94, 11.9, "「解说破百万才值得做」？我拿 31 个样本验了一遍")
    pic(slide, "scatter.png", 0.62, 2.14, 6.9)
    rect(slide, 8.0, 1.92, 4.72, 2.26, fill=WHITE)
    text(slide, 8.26, 2.1, 4.2, 2.0, [
        [(f"Pearson r = {corr['pearson']:+.2f}（p = {corr['pearson_p']:.3f}）", {"size": 13, "color": INK, "bold": True})],
        [(f"秩相关 ρ = {corr['spearman']:+.2f}（p = {corr['spearman_p']:.2f}，不显著）", {"size": 12.5, "color": INK_SOFT})],
        [(f"播放量能解释的热度方差约 {corr['r2'] * 100:.0f}%。", {"size": 12.5, "color": INK_SOFT})],
        [("那个数字量的是 UP 主自己的粉丝盘，还是发布时刻的存量；梗的生命周期在它之后才展开。",
          {"size": 12, "color": INK_MUTE})],
    ], spacing=1.26, space_after=2)
    rect(slide, 8.0, 4.34, 4.72, 2.22, fill=BRAND_SOFT, line=None)
    text(slide, 8.26, 4.5, 4.2, 2.0, [
        [("两个致命反例", {"size": 13, "color": BRAND, "bold": True})],
        [("闪身步：解说只有 64.6 万 → 该梗热度 81.0，当前榜首。", {"size": 12, "color": INK})],
        [("宗主第二招：解说 160.7 万 → 该梗热度 0.0，30 天里只有 2 天有内容。", {"size": 12, "color": INK})],
        [("结论：播放量门槛会同时漏掉最热的、收进最凉的。它只适合当采集成本的预算筛，不能当准入判据。",
          {"size": 11.5, "color": INK_SOFT})],
    ], spacing=1.24, space_after=2)
    return slide


def slide_results(prs, page):
    counts, cov = FACTS["counts"], FACTS["coverage"]
    slide = blank(prs)
    kicker(slide, "当前结果", page=page, color=GO)
    headline(slide, 0.62, 0.94, 11.9, f"{counts['on_board']} 个真梗在榜：热度接近的三个，赶梗结论完全不同")
    rows = FACTS["top"][:8]
    left, top = 0.62, 1.96
    widths = [0.6, 2.5, 1.1, 1.4, 1.9, 1.9]
    headers = ["#", "梗名", "热度", "阶段", "赶梗结论", "认证标签"]
    rect(slide, left, top, sum(widths), 0.46, fill=INK, line=None)
    for index, head in enumerate(headers):
        text(slide, left + sum(widths[:index]) + 0.14, top + 0.1, widths[index] - 0.2, 0.3,
             head, size=11.5, color=WHITE, bold=True)
    for row_index, row in enumerate(rows):
        y = top + 0.46 + row_index * 0.42
        rect(slide, left, y, sum(widths), 0.42, fill=WHITE if row_index % 2 else CANVAS, line=None)
        cells = [str(row_index + 1), row["name"], f"{row['score']:.1f}", row["stage"],
                 row["catch"], row["cert"]]
        for index, cell in enumerate(cells):
            color = BRAND if index == 2 else INK if index in (0, 1) else INK_SOFT
            text(slide, left + sum(widths[:index]) + 0.14, y + 0.075, widths[index] - 0.2, 0.3,
                 cell, size=11.5, color=color, bold=index in (1, 2))
    rect(slide, 10.98, 1.96, 1.74, 3.82, fill=WHITE)
    stages = FACTS["stages"]
    text(slide, 11.14, 2.12, 1.5, 3.5, [
        [("阶段分布", {"size": 11.5, "color": INK, "bold": True})],
        [(f"爆发 {stages.get('爆发期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"上升 {stages.get('上升期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"平稳 {stages.get('平稳期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"萌芽 {stages.get('萌芽期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"退潮 {stages.get('退潮期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"过气 {stages.get('过气', 0)}", {"size": 11, "color": BRAND, "bold": True})],
        [("", {"size": 4})],
        [("过气仍占位，是下一步要解决的", {"size": 10, "color": INK_MUTE})],
    ], spacing=1.2, space_after=1)
    rect(slide, 0.62, 5.94, 12.1, 0.7, fill=WHITE)
    text(slide, 0.9, 6.06, 11.6, 0.5, [
        [("同一批投稿、同一套算法，只把准入从交集换成并集：", {"size": 12, "color": INK_MUTE}),
         (f"可分析的梗 {cov['intersection']} → {cov['union']} 个，榜单 {counts['on_board']} 个真梗，演示数据 0 个。",
          {"size": 13.5, "color": BRAND, "bold": True})],
    ], spacing=1.2)
    return slide


def slide_validation(prs, page):
    counts = FACTS["counts"]
    slide = blank(prs)
    kicker(slide, "怎么知道结果可信", page=page, color=GO)
    headline(slide, 0.62, 0.94, 11.9, "验证不是跑通了，是错了会被发现")
    stat(slide, 0.62, 1.9, 2.9, "162", "单元与集成测试", color=GO, sub="算法、闸门、接口都覆盖")
    stat(slide, 3.7, 1.9, 2.9, "70", "接口冒烟项", color=GO, sub="对着真实数据的后端逐项校")
    stat(slide, 6.78, 1.9, 2.9, "0", "混进榜单的演示数据", color=GO, sub="真实模式闸门强制隔离")
    stat(slide, 9.86, 1.9, 2.86, f"{counts['no_series']}", "入池但采空的梗", color=GOLD,
         sub="如实显示暂无数据，不补零")
    cards = [
        ("口径写进界面，不写进说明书", "「当日播放量 = 该日头部 20 条相关视频合计」「统计截至 09-27，滞后 1 天」"
         "这类话直接显示在产品上，用户不用先读文档才知道数字怎么来的。", GO),
        ("演示数据必须自报家门", "系统留了一套演示梗库用来跑通全流程，但它永远带「演示数据」标记，"
         "真实模式下不进榜——自记自认的认证位不算证据。", FLARE),
        ("能抽查到每一条视频", "每个梗都列出采信了哪些样本、各自相关性得分多少、命中哪个词，"
         "觉得数不对，可以直接点进去看 BV 号。", BRAND),
        ("幂等与回归锁死", "重算不改变榜单（同输入同输出）；改封面改介绍不会改动任何指标——接口测试专门锁了这条。", DUSK),
    ]
    for index, (title, body, color) in enumerate(cards):
        x = 0.62 + (index % 2) * 6.22
        y = 3.52 + (index // 2) * 1.6
        card(slide, x, y, 5.9, 1.44, title, body, accent=color)
    return slide


def slide_next(prs, page):
    slide = blank(prs)
    kicker(slide, "局限 · 下一步 · 时间计划", page=page, color=DUSK)
    headline(slide, 0.62, 0.94, 11.9, "我知道它现在哪里不准")
    limits = [
        ("脉冲型梗会误判", "琵琶曲 30 天只有 4 天有内容，那天却播了 3,976 万；只看天数的门槛会判死它。",
         "上榜层改双条件"),
        ("过气梗仍占榜单位置", f"榜上 {FACTS['stages'].get('过气', 0)} 个热度 0.0 的梗，占了「今天玩什么」的位置。",
         "过气不出榜，另归考古区"),
        ("深翻页受平台风控限制", "空间投稿接口匿名只稳定给最近约 50 条，更早的要 Cookie。",
         "换指纹重试 + 索引缓存"),
        ("刷新还是手动", f"全库一轮 {FACTS['coverage']['union']} 个梗约 30~45 分钟，没有调度器。",
         "每日增量 + 单梗重采"),
    ]
    for index, (title, body, plan) in enumerate(limits):
        y = 1.92 + index * 1.02
        rect(slide, 0.62, y, 7.5, 0.9, fill=WHITE)
        text(slide, 0.88, y + 0.1, 6.9, 0.36, title, size=13.5, color=INK, bold=True)
        text(slide, 0.88, y + 0.46, 4.55, 0.42, body, size=11, color=INK_MUTE, spacing=1.2)
        text(slide, 5.6, y + 0.46, 2.36, 0.42, plan, size=11, color=GO, bold=True, spacing=1.2)
    rect(slide, 8.4, 1.92, 4.32, 3.9, fill=WHITE)
    text(slide, 8.66, 2.1, 3.8, 0.4, "剩余时间计划", size=14, color=INK, bold=True)
    plan_rows = [
        ("第 1-2 周", "上榜层口径重做：过气不出榜、脉冲型梗单独处理；补一组对照实验。"),
        ("第 3 周", "增量刷新与调度；把采空的梗用别名兜底再跑一轮。"),
        ("第 4 周", "用户实验：20 人对照看热搜与看本系统的选题准确率差异。"),
        ("第 5 周", "写论文与图表：阶段判定混淆矩阵、热度与人工标注的一致性检验。"),
    ]
    for index, (when, what) in enumerate(plan_rows):
        y = 2.6 + index * 0.82
        text(slide, 8.66, y, 1.2, 0.3, when, size=12, color=BRAND, bold=True)
        text(slide, 9.86, y, 2.7, 0.7, what, size=11, color=INK_SOFT, spacing=1.24)
    rect(slide, 0.62, 6.06, 12.1, 0.62, fill=INK, line=None)
    text(slide, 0.94, 6.18, 11.6, 0.4, [
        [("我想做的不是热搜的复读机，而是热点的倒计时器。", {"size": 14, "color": WHITE, "bold": True}),
         ("    现场可演示：127.0.0.1:5173（真实数据，非样例）", {"size": 11.5, "color": INK_FAINT})],
    ], spacing=1.2)
    return slide


NOTES = [
    "开场 20 秒：别念标题，直接问「闪身步是什么？」——停顿两秒让场子安静，再宣布这是真实榜单第一名。",
    "举手环节 30 秒。目的不是互动，是让所有人亲眼看到「信息差」确实存在，然后把痛点收到「还剩几天」上。",
    "30 秒。三类工具各说一句话就够，重点落在右边那格：把梗当成时间序列对象来测，这是本课题的位置。",
    "40 秒。RQ 要念得出口、也要能被证伪；右边「不做清单」是防追问的挡箭牌，主动讲比被问到再答好。",
    "60 秒。四个数字讲清规模，然后只挑一条口径细讲：为什么统计窗口不含今天（今天没过完，会算出假下跌）。",
    "60 秒，本稿重点之一。先讲漏掉老叟戏顽童这个事故，再讲并集怎么修——问题驱动方法，比直接摆规则有说服力。",
    "60 秒。公式不用念完，讲两件事：为什么对数归一（亿级老梗会永远压着新梗），为什么增长权重给到 0.25。",
    "60 秒。指着曲线说：闪身步和老叟戏顽童分数接近，但一个在冲一个在崩，所以必须判成不同结论。再补一句 LLM 只能写文案。",
    "90 秒，最能证明我真做过的一页。每个坑讲「现象 → 原因 → 修法」，其中黄豆那条最直观，可以多说一句。",
    "60 秒。先说这是我自己提的直觉，再拿数据把它推翻：r=+0.40 但只解释 16% 方差，两个反例足够判门槛不成立。",
    "60 秒。指出前三名热度接近但赶梗结论不同，说明阶段判定不是热度的复读。顺带交代并集带来的覆盖提升。",
    "45 秒。强调验证的目标不是跑通，而是错了会被发现：测试数、演示数据隔离、能抽查到每一条视频。",
    "45 秒收尾。主动交代四个已知不准，再给时间表；最后一句留在屏幕上：不是热搜的复读机，是热点的倒计时器。",
]


def main() -> int:
    prs = new_deck()
    builders = [
        slide_cover, slide_hook, slide_problem, slide_rq, slide_data, slide_discovery,
        slide_hotness, slide_lifecycle, slide_pitfalls, slide_falsify, slide_results,
        slide_validation, slide_next,
    ]
    for index, builder in enumerate(builders):
        slide = builder(prs) if index == 0 else builder(prs, index)
        if index < len(NOTES):
            slide.notes_slide.notes_text_frame.text = NOTES[index]
    prs.save(TARGET)
    print(f"已生成 {TARGET}（{len(builders)} 页，含逐页讲稿备注）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
