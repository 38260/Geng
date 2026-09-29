# -*- coding: utf-8 -*-
"""Assemble the opening-proposal deck from its three content parts."""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
files = ["build_proposal_a.py", "build_proposal_b.py", "build_proposal_c.py"]
chunks = []
for i, f in enumerate(files):
    src = open(os.path.join(HERE, f), encoding="utf-8").read()
    if i > 0:
        # drop the part's own imports and its intermediate save
        src = re.sub(r"^# -\+-.*?\n(?:.*?\n)*?(?=# =)", "", src, flags=re.S)
        src = re.sub(r"^import .*?\n|^from .*?\n|^sys\.path.*?\n", "", src,
                     flags=re.M)
        src = src.replace('prs.save(os.path.join(HERE, "deck_proposal_A.pptx"))', "")
        src = src.replace('print("part A ok, slides:", N[0])', "")
    chunks.append(src)
out = "\n".join(chunks)
out += '\nprs.save(os.path.join(HERE, "..", "赶梗潮-开题汇报.pptx"))\n'
out += 'print("opening deck ok, slides:", N[0])\n'
open(os.path.join(HERE, "_build_opening.py"), "w", encoding="utf-8").write(out)
print("assembled", len(out), "chars")
