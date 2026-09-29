# -*- coding: utf-8 -*-
"""Build 赶梗潮-结题答辩.pptx by running the three slide-content parts in order."""
import os, sys, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
g = runpy.run_path(os.path.join(HERE, "_defense_common.py"))
prs, N, add, fin, blk, kv, band, pending, rank_table = (
    g["make_deck"]())
g.update(dict(prs=prs, N=N, add=add, fin=fin, blk=blk, kv=kv, band=band,
              pending=pending, rank_table=rank_table))

for part in ("_defense_p1.py", "_defense_p2.py", "_defense_p3.py"):
    code = open(os.path.join(HERE, part), encoding="utf-8").read()
    exec(compile(code, part, "exec"), g)
    print("  after %-18s slides: %d" % (part, N[0]))

out = os.path.join(HERE, "..", "赶梗潮-结题答辩.pptx")
prs.save(out)
print("defense deck ok ->", os.path.normpath(out), "| slides:", N[0])
