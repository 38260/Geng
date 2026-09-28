"""《赶梗潮》数据科学课开题答辩 PPT 生成器（真·pptx）。

    python scripts/pitch_assets.py && python scripts/build_pitch.py

刻意做成"人做的"样子：
* 每页版式不一样（贴纸墙 / 黑板 / 病例单 / 时间线 / 巨大数字），而不是同一套卡片网格；
* 用真实梗封面当贴纸与榜单缩略图——讲梗的稿子当然要有梗的图；
* 标题说人话，不写「研究背景」「技术路线」，也不堆"不是A而是B"那种对仗句；
* 数字全部来自 facts.json（现取自真实库），改数据重跑两个脚本就整份刷新。
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
COVERS = FACTS.get("covers", {})
TARGET = OUT_DIR / "赶梗潮-开题答辩-v2.pptx"

CANVAS = RGBColor(0xF7, 0xFA, 0xFD)
PAPER = RGBColor(0xFF, 0xFD, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x14, 0x16, 0x1F)
INK_SOFT = RGBColor(0x3C, 0x59, 0x89)
INK_MUTE = RGBColor(0x6B, 0x7C, 0x9C)
INK_FAINT = RGBColor(0xA8, 0xB2, 0xC6)
LINE = RGBColor(0xE6, 0xEA, 0xF2)
BRAND = RGBColor(0xFB, 0x3A, 0x5E)
BRAND_SOFT = RGBColor(0xFD, 0xE9, 0xEE)
FLARE = RGBColor(0x0D, 0x8A, 0xFE)
FLARE_SOFT = RGBColor(0xEA, 0xF4, 0xFE)
GO = RGBColor(0x0B, 0x8A, 0x46)
GO_SOFT = RGBColor(0xE2, 0xF7, 0xEA)
GOLD = RGBColor(0xB9, 0x7B, 0x0A)
GOLD_SOFT = RGBColor(0xFF, 0xF0, 0xC7)
DUSK = RGBColor(0x54, 0x6F, 0x98)
BOARD = RGBColor(0x18, 0x22, 0x33)
TAPE = RGBColor(0xFF, 0xE9, 0xA8)

NL = chr(10)
SANS = "Microsoft YaHei"
BRUSH = "KaiTi"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


# --------------------------------------------------------------------------- #
# 基础件
# --------------------------------------------------------------------------- #
def new_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank(prs, *, paper=CANVAS):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = paper
    bg.line.fill.background()
    bg.shadow.inherit = False
    return slide


def shape(slide, kind, x, y, w, h, *, fill=WHITE, line=LINE, weight=1.0, angle=0.0, radius=None):
    node = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        node.adjustments[0] = radius
    if fill is None:
        node.fill.background()
    else:
        node.fill.solid()
        node.fill.fore_color.rgb = fill
    if line is None:
        node.line.fill.background()
    else:
        node.line.color.rgb = line
        node.line.width = Pt(weight)
    node.shadow.inherit = False
    if angle:
        node.rotation = angle
    return node


def card(slide, x, y, w, h, *, fill=WHITE, line=LINE, radius=0.06, angle=0.0, weight=1.0):
    return shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                 fill=fill, line=line, weight=weight, radius=radius, angle=angle)


def text(slide, x, y, w, h, runs, *, size=14, color=INK, bold=False, font=SANS,
         align=PP_ALIGN.LEFT, spacing=1.2, anchor=MSO_ANCHOR.TOP, space_after=4, angle=0.0):
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
    if angle:
        box.rotation = angle
    return box


def mark(slide, x, y, w, h=0.3, *, color=BRAND_SOFT):
    """划重点：先铺一条色块，再把字压上去。"""
    shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, h, fill=color, line=None)


def tape(slide, x, y, w=0.9, h=0.24, angle=-6):
    shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, h, fill=TAPE, line=None, angle=angle)


def sticker(slide, name, x, y, w=1.9, *, angle=0.0, caption=None, show_cover=True):
    """一张歪着贴的梗封面：白框 + 图 + 手写感标签。"""
    h = w * 0.72
    card(slide, x, y, w, h + 0.42, fill=WHITE, line=LINE, radius=0.04, angle=angle, weight=0.75)
    cover = COVERS.get(name) if show_cover else None
    if cover and (ROOT / cover).exists():
        pic = slide.shapes.add_picture(str(ROOT / cover), Inches(x + 0.07), Inches(y + 0.07),
                                       width=Inches(w - 0.14), height=Inches(h - 0.07))
        pic.rotation = angle
    else:
        block = shape(slide, MSO_SHAPE.RECTANGLE, x + 0.07, y + 0.07, w - 0.14, h - 0.07,
                      fill=BRAND_SOFT, line=None, angle=angle)
        text(slide, x + 0.07, y + h / 2 - 0.1, w - 0.14, 0.3, "封面待补", size=10,
             color=BRAND, align=PP_ALIGN.CENTER, angle=angle)
        block.rotation = angle
    text(slide, x, y + h + 0.02, w, 0.3, caption or name, size=11, color=INK_SOFT, bold=True,
         align=PP_ALIGN.CENTER, angle=angle)


def chart(slide, name, x, y, w):
    return slide.shapes.add_picture(str(ASSETS / name), Inches(x), Inches(y), width=Inches(w))


def page_no(slide, n, total=14):
    text(slide, 11.5, 6.98, 1.2, 0.3, f"{n} / {total}", size=10.5, color=INK_FAINT,
         align=PP_ALIGN.RIGHT)


def title(slide, lines, *, y=0.62, size=32, x=0.72, w=11.9, color=INK):
    text(slide, x, y, w, 1.0, lines, size=size, color=color, bold=True, spacing=1.05)


# --------------------------------------------------------------------------- #
# 13 页
# --------------------------------------------------------------------------- #
def p01_cover(prs):
    s = blank(prs)
    shape(s, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, 4.4, fill=RGBColor(0xFE, 0xF1, 0xF4), line=None)
    for index, (name, angle) in enumerate((("闪身步", -7), ("耍起", 5), ("雨中霸王龙", -3))):
        sticker(s, name, 8.35 + index * 1.5, 0.5 + (index % 2) * 0.35, w=1.55, angle=angle)
    text(s, 0.72, 0.9, 7.0, 0.4, "数据科学课程 · 开题答辩", size=13, color=BRAND, bold=True)
    text(s, 0.66, 1.34, 8.4, 1.6, "今天，赶什么梗？", size=66, color=INK, bold=True, font=BRUSH)
    text(s, 0.72, 2.72, 7.6, 0.5, "B 站网络梗热度与生命周期分析系统", size=20, color=INK_SOFT, bold=True)
    shape(s, MSO_SHAPE.RECTANGLE, 0.72, 3.42, 2.3, 0.1, fill=BRAND, line=None)
    text(s, 0.72, 4.72, 7.4, 1.0, [
        [("开场先问一句：", {"size": 12.5, "color": INK_MUTE})],
        [("「闪身步」9 月 21 日才有人解说，9 月 26 日热度 81 分、榜上第一。",
          {"size": 15, "color": INK, "bold": True})],
        [("你现在才听说它，算早还是算晚？我想把这件事算成一个数。", {"size": 13, "color": INK_SOFT})],
    ], spacing=1.34, space_after=2)
    card(s, 8.5, 4.72, 4.1, 1.5, fill=WHITE)
    text(s, 8.78, 4.9, 3.6, 1.2, [
        [("汇报人  ____________", {"size": 13, "color": INK, "bold": True})],
        [("学号  ____________", {"size": 12.5, "color": INK_SOFT})],
        [("指导教师  ____________", {"size": 12.5, "color": INK_SOFT})],
        [(f"数据截至 {FACTS['counts']['through']}，真实抓取", {"size": 11, "color": INK_FAINT})],
    ], spacing=1.34, space_after=2)
    tape(s, 8.36, 4.6, 0.8, 0.22, angle=-8)
    return s


def p02_vote(prs):
    s = blank(prs)
    title(s, "先测一下：这五个梗，认识三个以上的举手")
    text(s, 0.72, 1.42, 11.0, 0.4, "不是我编的题——它们就是此刻 B 站真实热度榜的前五名",
         size=13, color=INK_MUTE)
    for index, row in enumerate(FACTS["top"][:5]):
        x = 0.72 + index * 2.44
        angle = (-4, 3, -2, 4, -3)[index]
        sticker(s, row["name"], x, 2.0, w=2.16, angle=angle)
        mark(s, x + 0.16, 4.02, 1.5, 0.3, color=BRAND_SOFT if index == 0 else CANVAS)
        text(s, x + 0.24, 4.04, 1.5, 0.3, f"热度 {row['score']}", size=13.5, color=BRAND, bold=True)
        text(s, x + 0.24, 4.42, 1.9, 0.3, f"{row['stage']} · {row['cert']}", size=10.5, color=INK_MUTE)
    card(s, 0.72, 5.2, 11.9, 1.32, fill=PAPER, line=LINE)
    text(s, 1.06, 5.42, 11.2, 1.0, [
        [("认不全太正常了，梗的活跃窗口一般就两三周。", {"size": 14.5, "color": INK, "bold": True})],
        [("难受的地方不在这：你听说了、点开创作中心、脚本写完发出去，它已经不火了。"
          "热搜榜只会告诉你谁在前面，不会告诉你它还剩几天——这就是我要做的东西。",
          {"size": 13, "color": INK_SOFT})],
    ], spacing=1.34)
    page_no(s, 2)
    return s


def p03_problem(prs):
    s = blank(prs)
    title(s, "问来问去都是同一句话：现在做，还来得及吗")
    people = [
        ("一个 3 万粉的 UP 主", "「这个梗我上周就刷到了，现在拍是不是凉了？」",
         "他有手感，但没有刻度。同一个梗他每次判断都不一样。", FLARE, 0.62),
        ("品牌社媒运营", "「热搜上这个词，我们今晚要不要跟？」",
         "跟的是词不是梗：词还在榜上，梗可能三天前就过气了。", GOLD, 0.62),
        ("我室友（也是目标用户）", "「为什么我每次知道一个梗，它都已经不好玩了？」",
         "因为他拿到的永远是排名，不是时间。", BRAND, 0.62),
    ]
    for index, (who, quote, note, color, y0) in enumerate(people):
        y = 1.62 + index * 1.62
        card(s, 0.72, y, 7.1, 1.42, fill=WHITE)
        shape(s, MSO_SHAPE.ISOSCELES_TRIANGLE, 0.98, y + 1.4, 0.3, 0.2, fill=WHITE, line=LINE, angle=180)
        text(s, 1.0, y + 0.14, 6.5, 0.3, who, size=12, color=color, bold=True)
        text(s, 1.0, y + 0.46, 6.5, 0.4, quote, size=15, color=INK, bold=True, font=BRUSH)
        text(s, 1.0, y + 0.98, 6.5, 0.36, note, size=11.5, color=INK_MUTE)
    card(s, 8.16, 1.62, 4.46, 4.66, fill=BOARD, line=None)
    text(s, 8.46, 1.86, 3.9, 0.4, "所以我要给出的是", size=12.5, color=RGBColor(0xFF, 0xC9, 0x4B), bold=True)
    text(s, 8.46, 2.34, 3.9, 3.8, [
        [("一个能比的分数", {"size": 16, "color": WHITE, "bold": True})],
        [("0-100，跨梗可比，一条爆款吃不掉全榜。", {"size": 12, "color": RGBColor(0xC3, 0xCE, 0xE3)})],
        [("", {"size": 8})],
        [("一条有形状的时间线", {"size": 16, "color": WHITE, "bold": True})],
        [("萌芽 / 上升 / 爆发 / 平稳 / 退潮 / 过气，规则判，不靠感觉。", {"size": 12, "color": RGBColor(0xC3, 0xCE, 0xE3)})],
        [("", {"size": 8})],
        [("一个明确的赶不赶", {"size": 16, "color": WHITE, "bold": True})],
        [("还来得及 / 慎赶 / 你来晚了，附置信度和理由。", {"size": 12, "color": RGBColor(0xC3, 0xCE, 0xE3)})],
    ], spacing=1.26, space_after=2)
    page_no(s, 3)
    return s


def p04_scope(prs):
    s = blank(prs)
    title(s, "开题总得说清楚：我答哪三题，不答哪三题")
    rqs = [
        ("必答 1", "一个梗现在有多火？", "五因子加权的热度指数，绝对量先做对数区间归一。"),
        ("必答 2", "它走到哪一段了？", "增长率、距峰值差、连续下滑天数、活跃度 → 规则引擎判六个阶段。"),
        ("必答 3", "现在赶还来得及吗？", "前两问的输出交给判定规则，给三态 + 置信度 + 一句理由。"),
    ]
    for index, (tag, q_, body) in enumerate(rqs):
        y = 1.62 + index * 1.5
        card(s, 0.72, y, 6.9, 1.3, fill=PAPER, line=LINE, angle=(-1.2, 0.8, -0.6)[index])
        shape(s, MSO_SHAPE.RECTANGLE, 0.94, y + 0.16, 0.86, 0.3, fill=BRAND, line=None)
        text(s, 0.94, y + 0.19, 0.86, 0.28, tag, size=11, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        text(s, 1.96, y + 0.14, 5.4, 0.4, q_, size=16, color=INK, bold=True)
        text(s, 0.96, y + 0.66, 6.3, 0.5, body, size=12, color=INK_SOFT)
    card(s, 7.9, 1.62, 4.72, 4.5, fill=WHITE)
    text(s, 8.18, 1.8, 4.2, 0.4, "这三件我不做（做了必被问）", size=14, color=INK, bold=True)
    rows = [
        ("不预测未来数值", "只说已经发生的数据。任何「下周会爆」都不出现在产品里。"),
        ("不让大模型改事实", "LLM 只写文案；它给的状态和算法不一致时以算法为准，越界句子直接丢。"),
        ("不做多平台、不做账号体系", "先把 B 站这一把尺子做准，不铺覆盖面。"),
    ]
    for index, (head, body) in enumerate(rows):
        y = 2.34 + index * 1.24
        shape(s, MSO_SHAPE.RECTANGLE, 8.18, y + 0.04, 0.26, 0.26, fill=None, line=BRAND, weight=1.6)
        shape(s, MSO_SHAPE.RECTANGLE, 8.23, y + 0.15, 0.16, 0.05, fill=BRAND, line=None, angle=45)
        text(s, 8.6, y, 3.9, 0.36, head, size=13.5, color=INK, bold=True)
        text(s, 8.6, y + 0.4, 3.9, 0.7, body, size=11.5, color=INK_MUTE, spacing=1.26)
    page_no(s, 4)
    return s


def p04b_lit(prs):
    """研究现状与缺口：三条脉络各归各位，右边留本课题落点。"""
    s = blank(prs)
    title(s, "文献没缺，缺的是把它们接成一条链路")
    text(s, 0.72, 1.42, 11.4, 0.4, "开题前把三条研究线各自的结论摆到一起对了一遍", size=13, color=INK_MUTE)
    lanes = [
        ("梗的文化研究",
         "Dawkins 1976；Shifman 2012 / 2013；Bauckhage ICWSM 2011；" + NL + "谢朝群·何自然 2007；薛一飞 2024",
         "定义、分类、生成机制讲清楚了，" + NL + "但几乎不给出可复算的时间度量", DUSK),
        ("集体注意力与生命周期",
         "Downs 1972 议题注意力周期；Crane & Sornette PNAS 2008；" + NL
         + "Kleinberg KDD 2002；Yang & Leskovec WSDM 2011；" + NL
         + "Lorenz-Spreen Nat. Commun. 2019；宋宁·刘婵君 2016",
         "注意力形状可分类、半衰期在缩短都证明了，" + NL + "但对象是新闻与议题，不是梗", FLARE),
        ("流行度量化与预测",
         "Szabo & Huberman CACM 2010；Jenders WWW 2013；" + NL
         + "Li CIKM 2013；Tan BMSB 2014（热度寿命）；" + NL
         + "Zhou ACM CSUR 2021；Xu CIKM 2025",
         "早期增速能预测最终热度，" + NL + "但落在单条内容上，没做梗级聚合", GO),
    ]
    for index, (head, refs, gap_note, color) in enumerate(lanes):
        y = 1.94 + index * 1.42
        card(s, 0.72, y, 7.5, 1.28, fill=WHITE)
        shape(s, MSO_SHAPE.RECTANGLE, 0.72, y + 0.14, 0.055, 1.0, fill=color, line=None)
        text(s, 0.98, y + 0.1, 4.3, 0.34, head, size=13.5, color=INK, bold=True)
        text(s, 0.98, y + 0.46, 4.4, 0.78, refs, size=9.5, color=INK_MUTE, spacing=1.2)
        text(s, 5.5, y + 0.46, 2.6, 0.78, gap_note, size=10, color=INK_SOFT, spacing=1.22)
    card(s, 8.5, 1.94, 4.12, 4.12, fill=BOARD, line=None)
    text(s, 8.78, 2.14, 3.6, 0.4, "本课题站在哪", size=13.5, color=RGBColor(0xFF, 0xC9, 0x4B), bold=True)
    text(s, 8.78, 2.62, 3.6, 3.3, [
        [("先证明这是个真梗", {"size": 12, "color": WHITE, "bold": True})],
        [("两位解说 UP 主的真实投稿作证据：并集准入、90 天滚动窗口。",
          {"size": 11, "color": RGBColor(0xC3, 0xCE, 0xE3)})],
        [("再把它变成时间序列", {"size": 12, "color": WHITE, "bold": True})],
        [("逐日头部内容抽样：2,010 条日统计、1,632 条采信样本，可抽查到每条 BV。",
          {"size": 11, "color": RGBColor(0xC3, 0xCE, 0xE3)})],
        [("最后输出可质疑的判断", {"size": 12, "color": WHITE, "bold": True})],
        [("阶段与赶梗三态由规则给，带置信度与理由，口径直接显示在界面上。",
          {"size": 11, "color": RGBColor(0xC3, 0xCE, 0xE3)})],
        [("另：B 站弹幕研究（Zhang & Cassany 2020；Wang 2022；闫方洁 2017）说明弹幕就是梗的"
          "载体，所以评论与弹幕计入互动因子。", {"size": 10.5, "color": RGBColor(0x9F, 0xB0, 0xCB)})],
    ], spacing=1.24, space_after=4)
    page_no(s, 5)
    return s


def p05_data(prs):
    counts = FACTS["counts"]
    s = blank(prs)
    title(s, "数据只有一个来源：B 站，逐日抓")
    mark(s, 0.66, 2.5, 6.0, 1.2, color=BRAND_SOFT)
    text(s, 0.72, 1.62, 8.0, 0.4, "这一年攒下来的量级", size=13, color=INK_MUTE, bold=True)
    text(s, 0.72, 2.42, 8.2, 1.4, [
        [(f"{counts['views_total'] / 1e8:.2f}", {"size": 74, "color": BRAND, "bold": True}),
         (" 亿次播放", {"size": 26, "color": INK, "bold": True})],
    ], spacing=1.0)
    text(s, 0.74, 3.9, 8.2, 0.5, "不是全站播放量，是每天头部 20 条相关视频的合计——"
         "同一把尺子量所有梗，才叫可比。", size=12.5, color=INK_SOFT)
    tiles = [
        (f"{counts['memes']}", "梗库总量", f"{counts['admitted']} 个通过准入"),
        (f"{counts['stat_rows']:,}", "梗 × 天 日统计", f"{counts['stat_days_with_content']} 行真有内容"),
        (f"{counts['videos']:,}", "采信视频样本", "过相关性阈值才入库"),
        (counts["through"], "统计截至", "刻意不含今天"),
    ]
    for index, (value, label, sub) in enumerate(tiles):
        x = 0.72 + index * 2.0
        card(s, x, 4.62, 1.86, 1.3, fill=WHITE)
        text(s, x + 0.16, 4.76, 1.6, 0.4, value, size=17, color=FLARE, bold=True)
        text(s, x + 0.16, 5.18, 1.6, 0.3, label, size=11, color=INK)
        text(s, x + 0.16, 5.46, 1.6, 0.4, sub, size=10, color=INK_MUTE, spacing=1.2)
    card(s, 9.1, 1.62, 3.52, 4.3, fill=PAPER, line=LINE, angle=1.4)
    tape(s, 10.4, 1.48, 1.0, 0.24, angle=3)
    text(s, 9.4, 1.94, 3.0, 0.4, "我给自己立的三条规矩", size=13.5, color=INK, bold=True)
    text(s, 9.4, 2.44, 3.0, 3.3, [
        [("① 一天一次查询", {"size": 12.5, "color": BRAND, "bold": True})],
        [("带 pubtime 区间。第一版想省事一次抓完再摊到每天，算出过 +23616% 的假增长。", {"size": 11.5, "color": INK_SOFT})],
        [("② 只取当日头部 20 条", {"size": 12.5, "color": BRAND, "bold": True})],
        [("order=click，再按相关性阈值筛掉无关内容。", {"size": 11.5, "color": INK_SOFT})],
        [("③ 窗口不含今天", {"size": 12.5, "color": BRAND, "bold": True})],
        [("今天没过完就计入，头部偏低、增幅会假跌。", {"size": 11.5, "color": INK_SOFT})],
    ], spacing=1.22, space_after=3)
    page_no(s, 6)
    return s


def p06_discovery(prs):
    cov = FACTS["coverage"]
    s = blank(prs)
    title(s, "我把当时热度最高的梗，挡在库外整整两个月")
    steps = [
        ("8 月 21 日", "梗百科发了「老叟戏顽童」的解说", FLARE),
        ("8 月 23 日", "梗指南也跟了一期", FLARE),
        ("我定的规则", "两位都介绍过才算数，而且只看最近 30 天", BRAND),
        ("结果", "解说比爆发早 1~2 周，这条被我自己的窗口整条排除；同学当场问「这个你怎么没有」", BRAND),
    ]
    shape(s, MSO_SHAPE.RECTANGLE, 0.9, 1.94, 5.9, 0.03, fill=LINE, line=None)
    for index, (when, what, color) in enumerate(steps):
        y = 2.14 + index * 0.92
        shape(s, MSO_SHAPE.OVAL, 0.86, y + 0.06, 0.16, 0.16, fill=color, line=None)
        text(s, 1.16, y, 1.5, 0.3, when, size=12, color=color, bold=True)
        text(s, 2.7, y, 4.2, 0.7, what, size=12.5, color=INK if index == 3 else INK_SOFT,
             bold=index == 3, spacing=1.2)
    chart(s, "coverage.png", 7.16, 1.86, 5.5)
    card(s, 7.16, 4.5, 5.46, 1.9, fill=GO_SOFT, line=None)
    text(s, 7.44, 4.66, 4.9, 1.6, [
        [("改法：准入看并集，认证降级成标签", {"size": 14, "color": GO, "bold": True})],
        [(f"任一 UP 主在 90 天滚动窗口内介绍过就入池。同一批投稿，池子从 {cov['intersection']} 个变成 "
          f"{cov['union']} 个；两位都做过的仍然单独标「双 UP 认证」，但它不再是闸门。",
          {"size": 12, "color": INK_SOFT})],
    ], spacing=1.3)
    text(s, 0.9, 5.9, 5.9, 0.6, "认证窗口和报告窗口是两件事，合成一个就会漏梗——"
         "这是我这轮最贵的一课。", size=12, color=INK_MUTE, spacing=1.26)
    page_no(s, 7)
    return s


def p07_hotness(prs):
    s = blank(prs)
    title(s, "热度怎么算：五因子，但先取对数")
    card(s, 0.72, 1.62, 6.4, 1.66, fill=BOARD, line=None)
    text(s, 1.0, 1.86, 5.9, 0.5, "Hotness = 0.25·增长 + 0.25·播放 + 0.20·互动\n                 + 0.16·内容 + 0.14·创作者",
         size=15.5, color=RGBColor(0xFF, 0xE9, 0xA8), bold=True, font=BRUSH, spacing=1.3)
    text(s, 1.0, 2.82, 5.9, 0.3, "每个因子先做对数区间归一化，再加权", size=11.5,
         color=RGBColor(0xC3, 0xCE, 0xE3))
    chart(s, "weights.png", 0.72, 3.5, 6.4)
    items = [
        ("增长敢给到 1/4", "只看最近 7 天比前 7 天。去年 1 亿播放、今天没人做的梗，就不该继续霸榜。"),
        ("样本小就不外推", "前一周讨论量不到 30、或样本不到 3 条，增长率直接留空。考古区冒出一条视频，不算 +100%。"),
        ("人工碰不到分数", "封面、介绍、别名、关键词可以人改；热度、阶段、赶梗结论只能算法产出——接口层锁死，有测试盯着。"),
    ]
    for index, (head, body) in enumerate(items):
        y = 1.62 + index * 1.6
        card(s, 7.4, y, 5.22, 1.42, fill=WHITE)
        text(s, 7.68, y + 0.14, 4.7, 0.36, head, size=14.5, color=INK, bold=True)
        text(s, 7.68, y + 0.56, 4.7, 0.76, body, size=11.5, color=INK_SOFT, spacing=1.28)
    page_no(s, 8)
    return s


def p08_lifecycle(prs):
    s = blank(prs)
    title(s, "80 分有两种：一种在冲，一种在崩")
    chart(s, "curves.png", 0.72, 1.6, 7.5)
    labels = [
        ("闪身步", "09-13 起从零爬到 81，还在冲", BRAND, 1.62),
        ("琵琶曲", "脉冲型：冲完 09-25 直接断", FLARE, 2.66),
        ("老叟戏顽童", "从 84 一路退到 52，退潮期", DUSK, 3.7),
    ]
    for name, note, color, y in labels:
        card(s, 8.5, y, 4.12, 0.9, fill=WHITE)
        shape(s, MSO_SHAPE.RECTANGLE, 8.5, y + 0.12, 0.05, 0.66, fill=color, line=None)
        text(s, 8.74, y + 0.1, 3.7, 0.34, name, size=14, color=INK, bold=True)
        text(s, 8.74, y + 0.46, 3.7, 0.34, note, size=11.5, color=INK_MUTE)
    card(s, 0.72, 4.98, 7.5, 1.5, fill=PAPER, line=LINE)
    text(s, 1.0, 5.16, 7.0, 1.2, [
        [("六个阶段，规则自上而下匹配", {"size": 13.5, "color": INK, "bold": True})],
        [("萌芽 → 上升 → 爆发 → 平稳 → 退潮 → 过气。判定只用四件事：增长率、距峰值差、"
          "连续下滑天数、活跃度。阈值全在一个配置文件里，别人可以复算，也可以跟我吵。",
          {"size": 12, "color": INK_SOFT})],
    ], spacing=1.3)
    card(s, 8.5, 4.74, 4.12, 1.74, fill=WHITE)
    text(s, 8.74, 4.9, 3.7, 1.5, [
        [("LLM 只负责说人话", {"size": 13.5, "color": INK, "bold": True})],
        [("阶段和赶不赶都是算法先定，它再翻译。模型返回的状态跟算法不一致，以算法为准；"
          "文案里出现「预计」「未来 7 天」「一定会爆」这类话，直接丢掉。", {"size": 11.5, "color": INK_SOFT})],
    ], spacing=1.26)
    page_no(s, 9)
    return s


def p09_pitfalls(prs):
    s = blank(prs)
    title(s, "四个我亲手造出来的 bug")
    text(s, 0.72, 1.4, 11.0, 0.36, "都不是会报错的那种——口径错了，每个数照样算得出来，最难查",
         size=12.5, color=INK_MUTE)
    headers = ["症状", "化验单", "病因", "处方"]
    widths = [2.5, 3.1, 3.5, 3.4]
    rows = [
        ("假增长 +23,616%", "一次抓完再摊到每天", "拿今天看到的播放量回填历史某天",
         "逐日带时间区间查询，只算当天发布的头部内容"),
        ("榜首那个梗是假的", "418 条样本里 343 条在讲黄豆", "「我不是黄豆」的别名写成黄豆，炒黄豆、树叶做豆腐全灌进来",
         "短于 4 字的别名只算弱证据，必须再有第二个词佐证"),
        ("热度最高的梗不在榜上", "90 天交集只剩 8 个梗", "日更 UP 的选题被周更 UP 的排期一票否决",
         "准入改并集，认证窗口独立 90 天滚动，双 UP 降级为标签"),
        ("刷新把数据刷没了", "琵琶曲 4 天 / 3,976 万 → 1 天 / 18 条，44.2 分掉到 0.0", "同一词同一天两次返回的头部 20 条差很远",
         "同一天只留更好的一次观测（比样本数与播放量，绝不相加），另从快照回填 53 天"),
    ]
    x0, y0 = 0.72, 1.98
    shape(s, MSO_SHAPE.RECTANGLE, x0, y0, sum(widths), 0.44, fill=INK, line=None)
    for index, head in enumerate(headers):
        text(s, x0 + sum(widths[:index]) + 0.16, y0 + 0.09, widths[index] - 0.3, 0.3,
             head, size=12, color=WHITE, bold=True)
    for row_index, row in enumerate(rows):
        y = y0 + 0.44 + row_index * 1.14
        shape(s, MSO_SHAPE.RECTANGLE, x0, y, sum(widths), 1.14,
              fill=WHITE if row_index % 2 == 0 else CANVAS, line=None)
        for index, cell in enumerate(row):
            color = BRAND if index == 0 else INK if index == 1 else INK_SOFT if index == 2 else GO
            size = 13.5 if index == 0 else 11.5
            text(s, x0 + sum(widths[:index]) + 0.16, y + 0.14, widths[index] - 0.32, 0.9,
                 cell, size=size, color=color, bold=index in (0, 3), spacing=1.24)
    shape(s, MSO_SHAPE.RECTANGLE, x0, y0, sum(widths), 0.44 + 4 * 1.14, fill=None, line=LINE, weight=1.0)
    page_no(s, 10)
    return s


def p10_falsify(prs):
    corr = FACTS["correlation"]
    s = blank(prs)
    title(s, "我自己提的门槛，我自己先拿数据打了一遍")
    text(s, 0.72, 1.4, 11.4, 0.36,
         "提法：解说视频破百万才值得做。检验：把 31 个上榜梗的解说播放量和它自己的热度放一起看",
         size=12.5, color=INK_MUTE)
    chart(s, "scatter.png", 0.72, 1.92, 7.0)
    card(s, 8.0, 1.92, 4.62, 1.6, fill=WHITE)
    text(s, 8.26, 2.08, 4.1, 1.4, [
        [(f"Pearson r = {corr['pearson']:+.2f}（p = {corr['pearson_p']:.3f}）", {"size": 13, "color": INK, "bold": True})],
        [(f"秩相关 ρ = {corr['spearman']:+.2f}（p = {corr['spearman_p']:.2f}，不显著）", {"size": 12, "color": INK_SOFT})],
        [(f"播放量只能解释热度方差的约 {corr['r2'] * 100:.0f}%。", {"size": 12, "color": INK_SOFT})],
    ], spacing=1.26, space_after=2)
    for index, (name, line1, line2) in enumerate((
        ("闪身步", "解说只有 64.6 万", "热度 81.0，当前第一"),
        ("宗主第二招", "解说 160.7 万", "热度 0.0，30 天里 2 天有内容"),
    )):
        y = 3.7 + index * 1.24
        card(s, 8.0, y, 4.62, 1.1, fill=BRAND_SOFT if index == 0 else CANVAS, line=None)
        sticker(s, name, 11.6, y + 0.06, w=0.9, angle=4)
        text(s, 8.26, y + 0.12, 3.2, 0.34, name, size=14, color=INK, bold=True)
        text(s, 8.26, y + 0.5, 3.3, 0.5, [(line1 + " → ", {"color": INK_MUTE}), (line2, {"color": BRAND, "bold": True})],
             size=11.5, spacing=1.2)
    text(s, 0.72, 5.72, 7.0, 0.8, "结论：这个门槛会同时漏掉最热的、收进最凉的。播放量只适合当采集成本的预算筛，"
         "不能当准入判据——那个数字量的是 UP 主自己的粉丝盘，而且是发布那一刻的存量。",
         size=12, color=INK_SOFT, spacing=1.3)
    page_no(s, 11)
    return s


def p11_results(prs):
    counts, cov = FACTS["counts"], FACTS["coverage"]
    s = blank(prs)
    title(s, f"现在榜上 {counts['on_board']} 个活梗（明早刷新后可能就不一样了）")
    rows = FACTS["top"][:7]
    x0, y0 = 0.72, 1.66
    widths = [0.5, 1.1, 2.4, 1.0, 1.3, 1.7, 1.9]
    headers = ["#", "封面", "梗名", "热度", "阶段", "赶梗结论", "认证标签"]
    shape(s, MSO_SHAPE.RECTANGLE, x0, y0, sum(widths), 0.4, fill=INK, line=None)
    for index, head in enumerate(headers):
        text(s, x0 + sum(widths[:index]) + 0.12, y0 + 0.08, widths[index] - 0.2, 0.3, head,
             size=11.5, color=WHITE, bold=True)
    for row_index, row in enumerate(rows):
        y = y0 + 0.4 + row_index * 0.56
        shape(s, MSO_SHAPE.RECTANGLE, x0, y, sum(widths), 0.56,
              fill=WHITE if row_index % 2 == 0 else CANVAS, line=None)
        cells = [str(row_index + 1), "", row["name"], f"{row['score']:.1f}", row["stage"],
                 row["catch"], row["cert"]]
        for index, cell in enumerate(cells):
            if index == 1:
                cover = COVERS.get(row["name"])
                if cover and (ROOT / cover).exists():
                    s.shapes.add_picture(str(ROOT / cover), Inches(x0 + widths[0] + 0.08),
                                         Inches(y + 0.07), width=Inches(0.9), height=Inches(0.42))
                continue
            color = BRAND if index == 3 else INK if index in (0, 2) else INK_SOFT
            text(s, x0 + sum(widths[:index]) + 0.12, y + 0.13, widths[index] - 0.2, 0.3, cell,
                 size=12, color=color, bold=index in (2, 3))
    shape(s, MSO_SHAPE.RECTANGLE, x0, y0, sum(widths), 0.4 + 7 * 0.56, fill=None, line=LINE)
    card(s, 10.9, 1.66, 1.72, 4.74, fill=PAPER, line=LINE)
    stages = FACTS["stages"]
    text(s, 11.06, 1.82, 1.4, 4.4, [
        [("阶段分布", {"size": 11.5, "color": INK, "bold": True})],
        [(f"爆发 {stages.get('爆发期', 0)}", {"size": 11, "color": BRAND, "bold": True})],
        [(f"上升 {stages.get('上升期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"平稳 {stages.get('平稳期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"萌芽 {stages.get('萌芽期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"退潮 {stages.get('退潮期', 0)}", {"size": 11, "color": INK_SOFT})],
        [(f"过气 {stages.get('过气', 0)}", {"size": 11, "color": INK_MUTE})],
        [("", {"size": 4})],
        [(f"过气与只剩残值的 {counts['rankable'] - counts['on_board']} 个不在榜上，梗库仍查得到",
          {"size": 10, "color": INK_FAINT})],
    ], spacing=1.2, space_after=1)
    card(s, 0.72, 6.02, 10.0, 0.66, fill=WHITE)
    text(s, 0.98, 6.14, 9.6, 0.4, [
        (f"两道口径叠加：准入并集让可分析的梗从 {cov['intersection']} 个变 {cov['union']} 个，"
         f"上榜门槛再把 {counts['rankable']} 个有数据的梗收到 {counts['on_board']} 个——演示数据 0 个。",
         {"size": 12.5, "color": BRAND, "bold": True}),
    ])
    page_no(s, 12)
    return s


def p12_validation(prs):
    counts = FACTS["counts"]
    s = blank(prs)
    title(s, "我怎么确认自己没在骗自己")
    tiles = [
        ("162", "单元 + 集成测试", "算法、闸门、接口都有断言", GO),
        ("70", "接口冒烟项", "对着真实数据的后端逐项校", GO),
        ("0", "演示数据混进榜单", "真实模式下闸门强制隔离", GO),
        (f"{counts['no_series']}", "入池但采到的梗是空的", "页面显示暂无数据，不补零", GOLD),
    ]
    for index, (value, label, sub, color) in enumerate(tiles):
        x = 0.72 + index * 3.06
        card(s, x, 1.62, 2.86, 1.42, fill=WHITE)
        text(s, x + 0.2, 1.78, 2.5, 0.5, value, size=27, color=color, bold=True)
        text(s, x + 0.2, 2.34, 2.5, 0.3, label, size=11.5, color=INK)
        text(s, x + 0.2, 2.62, 2.5, 0.4, sub, size=10.5, color=INK_MUTE, spacing=1.2)
    checks = [
        ("口径写在界面上，不写在说明书里", "「当日播放量 = 该日头部 20 条相关视频合计」「统计截至 09-27，滞后 1 天」"
         "这类话直接显示在产品上，用户不用先读文档才知道数怎么来的。"),
        ("演示数据必须自报家门", "留了一套演示梗库用来跑通流程，但它永远带「演示数据」标记，真实模式下不进榜；"
         "自记自认的认证位不算证据。"),
        ("每一条样本都能抽查", "每个梗列出采信了哪些视频、各自相关性得分、命中哪个词，觉得数不对可以直接点进去看 BV 号。"),
        ("改数据要能被发现", "重算幂等（同输入同输出）；改封面改介绍不动任何指标——这条有专门的回归测试盯着。"),
    ]
    for index, (head, body) in enumerate(checks):
        y = 3.34 + index * 0.86
        shape(s, MSO_SHAPE.RECTANGLE, 0.78, y + 0.06, 0.28, 0.28, fill=None, line=GO, weight=1.6)
        shape(s, MSO_SHAPE.RECTANGLE, 0.83, y + 0.2, 0.2, 0.05, fill=GO, line=None, angle=45)
        shape(s, MSO_SHAPE.RECTANGLE, 0.9, y + 0.1, 0.05, 0.18, fill=GO, line=None, angle=45)
        text(s, 1.24, y, 5.4, 0.34, head, size=13.5, color=INK, bold=True)
        text(s, 6.9, y, 5.7, 0.8, body, size=11.5, color=INK_MUTE, spacing=1.26)
    page_no(s, 13)
    return s


def p13_next(prs):
    s = blank(prs)
    title(s, "它现在哪里不准，以及我打算怎么办")
    limits = [
        ("脉冲型梗会被误判", "琵琶曲 30 天只有 4 天有内容，那天却播了 3,976 万。只看天数的门槛会判死它。",
         "上榜改双条件：天数 或 头部播放量"),
        ("过气梗还占着位置", f"榜上 {FACTS['stages'].get('过气', 0)} 个热度 0.0 的梗，把「今天玩什么」的地方占了。",
         "过气不出榜，单独归到考古区"),
        ("更早的投稿拿不全", "空间接口匿名只稳定给最近约 50 条，两位 UP 的更早投稿要 Cookie。",
         "换指纹重试 + 索引缓存 + 缺口如实报告"),
        ("刷新还得手动跑", f"全库一轮 {FACTS['coverage']['union']} 个梗要 30~45 分钟，目前没有调度。",
         "每日增量刷新 + 单梗重采入口"),
    ]
    for index, (head, body, plan) in enumerate(limits):
        y = 1.62 + index * 1.16
        card(s, 0.72, y, 7.1, 1.04, fill=WHITE)
        text(s, 0.98, y + 0.12, 6.6, 0.34, head, size=14, color=INK, bold=True)
        text(s, 0.98, y + 0.5, 4.6, 0.5, body, size=11, color=INK_MUTE, spacing=1.22)
        text(s, 5.72, y + 0.5, 2.0, 0.5, plan, size=11, color=GO, bold=True, spacing=1.22)
    card(s, 8.1, 1.62, 4.52, 4.44, fill=PAPER, line=LINE)
    tape(s, 10.1, 1.5, 1.0, 0.24, angle=2)
    text(s, 8.4, 1.86, 4.0, 0.4, "剩下几周怎么排", size=13.5, color=INK, bold=True)
    plans = [
        ("第 1-2 周", "上榜层口径重做，补一组对照实验"),
        ("第 3 周", "增量刷新与调度；采空的梗用别名兜底再跑"),
        ("第 4 周", "20 人小实验：看热搜 vs 看本系统，谁的选题更准"),
        ("第 5 周", "阶段判定混淆矩阵、热度与人工标注一致性检验"),
        ("第 6 周", "写论文与图表"),
    ]
    for index, (when, what) in enumerate(plans):
        y = 2.4 + index * 0.72
        shape(s, MSO_SHAPE.OVAL, 8.5, y + 0.06, 0.12, 0.12, fill=BRAND, line=None)
        if index < len(plans) - 1:
            shape(s, MSO_SHAPE.RECTANGLE, 8.55, y + 0.2, 0.02, 0.56, fill=LINE, line=None)
        text(s, 8.76, y, 1.1, 0.3, when, size=12, color=BRAND, bold=True)
        text(s, 9.9, y, 2.6, 0.6, what, size=11.5, color=INK_SOFT, spacing=1.22)
    shape(s, MSO_SHAPE.RECTANGLE, 0, 6.4, 13.333, 1.1, fill=INK, line=None)
    text(s, 0.72, 6.66, 11.9, 0.5, [
        [("有问题现在问——明天榜单就不长这样了。", {"size": 17, "color": WHITE, "bold": True, "font": BRUSH}),
         ("      现场可演示：127.0.0.1:5173，数据是昨晚真跑出来的", {"size": 11.5, "color": INK_FAINT})],
    ])
    return s


NOTES = [
    "别念标题。直接问「闪身步是什么？」，停两秒，再宣布它是今天真实榜第一。",
    "举手 30 秒。目的是让全场亲眼看到信息差存在，然后把痛点收到「还剩几天」这一句上。",
    "三个气泡各念一句就够，重点是右边黑板：分数、时间线、赶不赶，三样东西。",
    "40 秒。必答三题要念得出口也经得起追问；不做清单主动讲，比被老师问到再解释强。",
    "45 秒。三条脉络各说一句它们缺什么，右边说我们接起来的那条链路；这页证明我读过文献，别逐个念人名。",
    "60 秒。先讲 2.08 亿是什么口径，再挑「不含今天」这一条细讲，其它一句话带过。",
    "60 秒，重点页。先讲漏掉老叟戏顽童这个事故，再讲并集怎么修——问题驱动方法比直接摆规则有说服力。",
    "60 秒。公式不用逐字念，讲两件事：为什么取对数，为什么增长敢给 1/4。",
    "60 秒。指着曲线说：闪身步和老叟戏顽童分数接近但形状相反，所以阶段判定不能只看分数。再补一句 LLM 只能写文案。",
    "90 秒，最能证明我真做过的一页。每行按症状 → 化验单 → 病因 → 处方讲，黄豆那条可以多说一句。",
    "60 秒。先承认这是我自己提的直觉，再拿数据打它：r=+0.40 只解释 16% 方差，两个反例足够判门槛不成立。",
    "60 秒。指出前三名热度接近但赶梗结论不同，说明阶段不是热度的复读。顺带交代并集带来的覆盖提升。",
    "45 秒。强调验证的目标不是跑通，是错了会被发现：测试数、演示数据隔离、能抽查到每条视频。",
    "45 秒收尾。主动交代四个不准，再给时间表。最后一句留在屏幕上，等老师提问。",
]


def main() -> int:
    prs = new_deck()
    builders = [p01_cover, p02_vote, p03_problem, p04_scope, p04b_lit, p05_data, p06_discovery,
                p07_hotness, p08_lifecycle, p09_pitfalls, p10_falsify, p11_results,
                p12_validation, p13_next]
    for index, builder in enumerate(builders):
        slide = builder(prs) if index == 0 else builder(prs)
        slide.notes_slide.notes_text_frame.text = NOTES[index]
    prs.save(TARGET)
    print(f"已生成 {TARGET}（{len(builders)} 页）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
