# -*- coding: utf-8 -*-
"""Full bounds audit: every shape must sit inside the slide margins."""
import sys, os
from pptx import Presentation
EMU = 914400.0
SW, SH, M = 13.333, 7.5, 0.62
LEFT_MAX = SW - M + 0.02   # right margin line
BOT_MAX = SH - 0.02

bad = 0
for path in sys.argv[1:]:
    prs = Presentation(path)
    print("=" * 80)
    print(os.path.basename(path), "| slides:", len(prs.slides))
    for i, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            l, t = sh.left / EMU, sh.top / EMU
            w, h = sh.width / EMU, sh.height / EMU
            r, b = l + w, t + h
            probs = []
            # deliberate full-bleed backdrops and edge bars
            if abs(l) < 0.001 and w >= SW - 0.001:
                continue
            if abs(l) < 0.001 and abs(h - SH) < 0.02:
                continue
            if r > LEFT_MAX + 1e-6:
                probs.append("right=%.3f (>%.3f)" % (r, LEFT_MAX))
            if b > BOT_MAX + 1e-6:
                probs.append("bottom=%.3f (>%.3f)" % (b, BOT_MAX))
            if l < -0.001 or t < -0.001:
                probs.append("negative origin (%.3f, %.3f)" % (l, t))
            if probs:
                bad += 1
                name = (sh.text_frame.text[:34].replace("\n", " ")
                        if sh.has_text_frame else sh.shape_type)
                print("  s%-2d %-34s L%.2f T%.2f W%.2f H%.2f | %s"
                      % (i, str(name), l, t, w, h, "; ".join(probs)))
    print("  ok" if not bad else "  ^^ problems above")
print()
print("TOTAL OUT-OF-BOUNDS SHAPES:", bad)
