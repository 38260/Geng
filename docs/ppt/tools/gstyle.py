# -*- coding: utf-8 -*-
"""Shared design system for the two GengChao decks.

Visual language lifted from the existing docs/pitch deck so all three read as
one family: cool-white canvas, white cards, coral accent, navy support, KaiTi
display titles, Microsoft YaHei body.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #
CORAL = RGBColor(0xFB, 0x3A, 0x5E)
CORAL_SOFT = RGBColor(0xFF, 0xEC, 0xF0)
NAVY = RGBColor(0x3C, 0x59, 0x89)
NAVY_SOFT = RGBColor(0xED, 0xF2, 0xFA)
BLUE = RGBColor(0x0D, 0x8A, 0xFE)
BLUE_SOFT = RGBColor(0xE6, 0xF3, 0xFF)
INK = RGBColor(0x14, 0x16, 0x1F)
GREY = RGBColor(0x6B, 0x7C, 0x9C)
MIST = RGBColor(0xA8, 0xB2, 0xC6)
LINE = RGBColor(0xE2, 0xE8, 0xF1)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CANVAS = RGBColor(0xF6, 0xF8, 0xFB)
GOLD = RGBColor(0xFF, 0xC9, 0x4B)
GOLD_DEEP = RGBColor(0xB9, 0x7B, 0x0A)
GREEN = RGBColor(0x1F, 0x9E, 0x6B)
GREEN_SOFT = RGBColor(0xE8, 0xF7, 0xF0)
DARK = RGBColor(0x14, 0x1B, 0x2E)
DARK_SOFT = RGBColor(0x24, 0x2E, 0x47)

BODY = "Microsoft YaHei"
DISPLAY = "KaiTi"
MONO = "Consolas"

# --------------------------------------------------------------------------- #
# geometry (16:9, 13.333 x 7.5 in)
# --------------------------------------------------------------------------- #
SW = 13.333
SH = 7.5
MARGIN = 0.62
CONTENT_W = SW - 2 * MARGIN
BODY_TOP = 1.60
BODY_BOTTOM = 6.88
BODY_H = BODY_BOTTOM - BODY_TOP
FOOT_Y = 6.99


def new_deck():
    from pptx import Presentation

    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def rect(slide, x, y, w, h, *, fill=None, line=None, line_w=1.0,
         shape=MSO_SHAPE.RECTANGLE, adj=None, shadow=False):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w)
    if not shadow:
        sh.shadow.inherit = False
    if adj is not None:
        try:
            sh.adjustments[0] = adj
        except Exception:
            pass
    sh.text_frame.word_wrap = True
    return sh


def card(slide, x, y, w, h, *, fill=WHITE, line=LINE, radius=0.055):
    return rect(slide, x, y, w, h, fill=fill, line=line,
                shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=radius)


def textbox(slide, x, y, w, h, *, anchor=MSO_ANCHOR.TOP, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    return tb


_FONT_FILES = {
    "Microsoft YaHei": r"C:\Windows\Fonts\msyh.ttc",
    "KaiTi": r"C:\Windows\Fonts\simkai.ttf",
    "Consolas": r"C:\Windows\Fonts\consola.ttf",
}
_MCACHE = {}


def _is_cjk(ch):
    o = ord(ch)
    return (0x3000 <= o <= 0x303F or 0x3400 <= o <= 0x9FFF
            or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF
            or 0x2000 <= o <= 0x206F or 0x2190 <= o <= 0x2BFF)


def _adv_em(ch):
    """Advance width in em, modelled on real PowerPoint CJK behaviour.

    The bundled LibreOffice preview substitutes a single fallback face for every
    font family (measured: 1.72 em per CJK glyph for all six families tried), so
    its widths are ~1.7x reality and cannot be used to gate layouts. These
    figures are the true Microsoft YaHei / KaiTi advances a Chinese PowerPoint
    will produce, which is what the deliverable actually has to survive.
    """
    if _is_cjk(ch):
        return 1.0
    if ch in "iljI.,:;'|![]()":
        return 0.30
    if ch == " ":
        return 0.28
    if ch.isdigit():
        return 0.56
    if ch.isupper():
        return 0.68
    if ch.isalpha():
        return 0.55
    return 0.55


def text_width_em(text):
    return sum(_adv_em(c) for c in text)


def _metrics(font, size):
    """(line_height_in, em_width_in) for one point of text.

    Line height uses PowerPoint's single line spacing (1.32x for these CJK
    faces), measured from the rendered calibration deck.
    """
    key = (font, round(size, 1))
    if key in _MCACHE:
        return _MCACHE[key]
    lh_pt = size * 1.34
    out = (lh_pt, size)
    _MCACHE[key] = out
    return out


def measure_lines(lines, w):
    """Predicted rendered height in inches for a list of `para`-style dicts."""
    total_pt = 0.0
    for ln in lines:
        size = ln.get("size", 14)
        font = ln.get("font", BODY)
        lh, em = _metrics(font, size)
        text = ln.get("text", "")
        avail_pt = max(w * 72.0 - 2.0, 24.0)
        width = text_width_em(text) * em
        rows = max(1, int(-(-width // avail_pt)))
        ls = ln.get("line_spacing", 1.22) or 1.22
        total_pt += rows * lh * ls
        total_pt += ln.get("space_before", 0) + ln.get("space_after", 0)
    return total_pt / 72.0


def fit_text(slide, x, y, w, h, lines, *, anchor=MSO_ANCHOR.TOP, pad=1.0,
             floor=0.62, warn=""):
    """`simple` that shrinks the body size until the block fits inside `h`.

    Keeps previews and PowerPoint agreeing, and catches overflow at build time
    instead of during the defense.
    """
    scale = 1.0
    while scale > floor and measure_lines(
            [dict(l, size=l.get("size", 14) * scale) for l in lines], w) > h * pad:
        scale = round(scale - 0.02, 4)
    if warn and measure_lines(
            [dict(l, size=l.get("size", 14) * scale) for l in lines], w) > h * pad:
        print("  ! overflow %s (scale %.2f)" % (warn, scale))
    tb = textbox(slide, x, y, w, h, anchor=anchor)
    tf = tb.text_frame
    for i, ln in enumerate(lines):
        opt = dict(ln)
        opt["size"] = round(opt.get("size", 14) * scale, 1)
        para(tf, i == 0, **opt)
    return tb


def para(tf, first, *, text="", size=14, color=INK, bold=False, font=BODY,
         align=PP_ALIGN.LEFT, space_before=0, space_after=0, line_spacing=1.22,
         italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    if space_before:
        p.space_before = Pt(space_before)
    if space_after:
        p.space_after = Pt(space_after)
    if line_spacing:
        p.line_spacing = line_spacing
    if text:
        r = p.add_run()
        r.text = text
        f = r.font
        f.size = Pt(size)
        f.bold = bold
        f.italic = italic
        f.name = font
        f.color.rgb = color
    return p


def rich(tf, first, chunks, *, align=PP_ALIGN.LEFT, space_before=0,
         space_after=0, line_spacing=1.22):
    """chunks: list of (text, {size,color,bold,font,italic})"""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    if space_before:
        p.space_before = Pt(space_before)
    if space_after:
        p.space_after = Pt(space_after)
    if line_spacing:
        p.line_spacing = line_spacing
    for text, opt in chunks:
        r = p.add_run()
        r.text = text
        f = r.font
        f.size = Pt(opt.get("size", 14))
        f.bold = opt.get("bold", False)
        f.italic = opt.get("italic", False)
        f.name = opt.get("font", BODY)
        f.color.rgb = opt.get("color", INK)
    return p


def simple(slide, x, y, w, h, lines, *, anchor=MSO_ANCHOR.TOP, warn=None):
    """lines: list of dicts accepted by `para` (minus `first`)."""
    need = measure_lines(lines, w)
    if warn and need > h + 0.01:
        print("  ! %s needs %.2fin but box is %.2fin" % (warn, need, h))
    tb = textbox(slide, x, y, w, h, anchor=anchor)
    tf = tb.text_frame
    for i, ln in enumerate(lines):
        opt = dict(ln)
        opt.pop("first", None)
        para(tf, i == 0, **opt)
    return tb


# --------------------------------------------------------------------------- #
# slide chrome
# --------------------------------------------------------------------------- #
def canvas(slide, *, dark=False):
    rect(slide, 0, 0, SW, SH, fill=DARK if dark else CANVAS)


def header(slide, kicker, title, *, sub=None, accent=CORAL, tag=None,
           title_size=27, dark=False):
    ink = WHITE if dark else INK
    g = MIST if dark else GREY
    if kicker:
        rect(slide, MARGIN, 0.38, 0.052, 0.19, fill=accent)
        simple(slide, MARGIN + 0.14, 0.34, CONTENT_W - 0.14, 0.27,
               [dict(text=kicker, size=11.5, color=accent, bold=True)],
               warn="header-kicker")
    # Width-aware: the title keeps one line if it fits, otherwise it shrinks a
    # little and only then wraps, so it can never run off the slide.
    tsize = title_size
    while tsize > 17 and text_width_em(title) * tsize > (CONTENT_W - 0.2) * 72:
        tsize -= 0.5
    fit_text(slide, MARGIN, 0.63, CONTENT_W, 0.65,
             [dict(text=title, size=tsize, color=ink, bold=True, font=DISPLAY,
                   line_spacing=1.04)], warn="header-title", pad=0.98)
    if sub:
        ssize = 12.5
        while ssize > 9.5 and text_width_em(sub) * ssize > (CONTENT_W - 0.2) * 72:
            ssize -= 0.25
        simple(slide, MARGIN, 1.26, CONTENT_W, 0.30,
               [dict(text=sub, size=ssize, color=g)], warn="header-sub")
    if tag:
        w = 0.105 * len(tag) + 0.30
        box = card(slide, SW - MARGIN - w, 0.38, w, 0.34,
                   fill=CORAL_SOFT if not dark else DARK_SOFT, line=None, radius=0.28)
        tf = box.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(tf, True, text=tag, size=11, color=accent if not dark else WHITE,
             bold=True, align=PP_ALIGN.CENTER)
    return BODY_TOP


def footer(slide, num, total, *, note="Bilibili 真实采集 · 口径见产品内「数据透明度」页脚",
           dark=False):
    g = MIST
    simple(slide, MARGIN, FOOT_Y, CONTENT_W - 1.1, 0.26,
           [dict(text=note, size=9.5, color=g)], warn="footer-note")
    simple(slide, SW - MARGIN - 1.0, FOOT_Y, 1.0, 0.26,
           [dict(text="%d / %d" % (num, total), size=9.5, color=g,
                 align=PP_ALIGN.RIGHT)])


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def pic(slide, path, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(path, Inches(x), Inches(y), **kw)


def pic_cover(slide, path, x, y, w, h):
    """Insert an image scaled to *fill* the box, centre-cropped."""
    from PIL import Image

    with Image.open(path) as im:
        iw, ih = im.size
    box_ar = w / h
    img_ar = iw / ih
    p = pic(slide, path, x, y, w if img_ar >= box_ar else None,
            h if img_ar < box_ar else None)
    pic_w = p.width / 914400
    pic_h = p.height / 914400
    p.left = Inches(x - (pic_w - w) / 2)
    p.top = Inches(y - (pic_h - h) / 2)
    return p
