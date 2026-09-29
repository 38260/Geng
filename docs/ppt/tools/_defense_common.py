# -*- coding: utf-8 -*-
"""Shared preamble for the 结题答辩 deck: imports, palette hooks, helpers.

Each build_defense_*.py starts with `from _defense_common import *` so the three
parts stay short and only contain slide content.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gstyle import *  # noqa: F401,F403
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.path.join(HERE, "..", "assets")
ROOT = os.path.dirname(HERE)
COVER = os.path.join(ROOT, "docs", "pitch", "assets", "covers")
F = json.load(open(os.path.join(HERE, "deck_facts.json"), encoding="utf-8"))
TOTAL = 13
MASCOT = os.path.join(ROOT, "docs", "design", "asset-mascot-sign.png")
PENDING = RGBColor(0xF2, 0xF4, 0xF8)
PENDING_LINE = RGBColor(0xC9, 0xD3, 0xE3)


def make_deck():
    prs = new_deck()
    N = [0]

    def add(*, dark=False):
        s = blank(prs)
        canvas(s, dark=dark)
        N[0] += 1
        return s

    def fin(s, note="结论均由算法从数据算出 · 数值可用 sqlite3 backend/data/gengv1.db 复核"):
        footer(s, N[0], TOTAL, note=note)

    def blk(s, x, y, w, h, lines, *, warn=None, pad=1.0):
        return fit_text(s, x, y, w, h, lines, warn=warn or ("s%d" % N[0]), pad=pad)

    def kv(s, x, y, w, h, big, label, sub=None, *, color=CORAL, bsize=30,
           fill=WHITE, line=LINE):
        card(s, x, y, w, h, fill=fill, line=line)
        lines = [dict(text=big, size=bsize, color=color, bold=True),
                 dict(text=label, size=12, color=INK, bold=True, space_before=4)]
        if sub:
            lines.append(dict(text=sub, size=10, color=GREY, space_before=3,
                              line_spacing=1.2))
        blk(s, x + 0.26, y + 0.20, w - 0.52, h - 0.36, lines)

    def band(s, y, h, text, *, fill=CORAL_SOFT, color=INK, size=13, w=None,
             x=None, bold=True, extra=None, exsize=11):
        x = MARGIN if x is None else x
        w = CONTENT_W if w is None else w
        card(s, x, y, w, h, fill=fill, line=None)
        lines = [dict(text=text, size=size, color=color, bold=bold)]
        if extra:
            lines.append(dict(text=extra, size=exsize, color=GREY,
                              space_before=4, line_spacing=1.2))
        blk(s, x + 0.32, y + 0.15, w - 0.64, h - 0.28, lines)

    def pending(s, x, y, w, h, title, fields, note=None):
        """A deliberately unfinished-looking panel for work not yet done."""
        card(s, x, y, w, h, fill=PENDING, line=PENDING_LINE)
        lines = [dict(text="待补实验", size=9.5, color=GOLD_DEEP, bold=True),
                 dict(text=title, size=13, color=INK, bold=True, space_before=3)]
        for f in fields:
            lines.append(dict(text="· " + f, size=10, color=GREY,
                              space_before=6, line_spacing=1.24))
        if note:
            lines.append(dict(text=note, size=9.5, color=GOLD_DEEP,
                              space_before=7, line_spacing=1.2))
        blk(s, x + 0.26, y + 0.20, w - 0.52, h - 0.38, lines)
        rect(s, x, y, w, 0.06, fill=GOLD)

    def rank_table(s, y, rows, certs, *, row_h=0.375, gap=0.02, head_h=0.40,
                   size=10.5):
        cols = [("名次", 0.85), ("梗", 2.55), ("热度", 1.25), ("阶段", 1.60),
                ("赶梗判断", 1.75), ("置信度", 1.30), ("认证", 2.59)]
        x = MARGIN
        for h, w in cols:
            card(s, x, y, w, head_h, fill=NAVY, line=None, radius=0.10)
            blk(s, x + 0.12, y + 0.07, w - 0.24, 0.26,
                [dict(text=h, size=10.5, color=WHITE, bold=True,
                      align=PP_ALIGN.CENTER)], warn="th")
            x += w + 0.03
        yy = y + head_h + 0.04
        for i, r in enumerate(rows):
            x = MARGIN
            card(s, MARGIN, yy, sum(w for _, w in cols) + 0.18, row_h,
                 fill=WHITE if i % 2 == 0 else RGBColor(0xFA, 0xFB, 0xFD),
                 line=LINE)
            vals = [str(i + 1), r["name"], "%.1f" % r["score"], r["stage"],
                    r["catch"], "%.2f" % r["conf"], certs[i]]
            for (h, w), v in zip(cols, vals):
                c = CORAL if h in ("热度", "赶梗判断") else INK
                blk(s, x + 0.12, yy + 0.075, w - 0.24, 0.24,
                    [dict(text=v, size=size, color=c, bold=True,
                          align=PP_ALIGN.LEFT if h == "梗" else PP_ALIGN.CENTER)],
                    warn="tr")
                x += w + 0.03
            yy += row_h + gap
        return yy

    return prs, N, add, fin, blk, kv, band, pending, rank_table
