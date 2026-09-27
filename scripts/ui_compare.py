#!/usr/bin/env python3
"""视觉比对：把实拍截图缩到参考稿画板宽度，和参考图并排 + 叠图。

    python scripts/ui_compare.py .shots/desktop-home.png home
    python scripts/ui_compare.py .shots/desktop-detail.png detail

输出 .shots/cmp-<name>.png（左参考 / 右实拍）与 .shots/blend-<name>.png
（50% 叠加，错位、尺寸不对会直接看出重影）。参考稿是三个画板拼的一张图，
所以先按画板裁出来。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "docs" / "design" / "reference-ui.png"

# 参考稿里三个画板的位置（左上/右下），按像素目测后固定下来
PANELS = {
    "home": (14, 14, 946, 995),
    "detail": (966, 14, 1522, 700),
    "settings": (966, 706, 1522, 995),
}


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    shot_path, panel = Path(sys.argv[1]), sys.argv[2]
    if panel not in PANELS:
        print(f"未知画板 {panel}，可选：{', '.join(PANELS)}")
        return 2
    if not shot_path.exists():
        print(f"找不到截图 {shot_path}")
        return 2

    ref = Image.open(REF).convert("RGB").crop(PANELS[panel])
    shot = Image.open(shot_path).convert("RGB")

    # 缩到画板同宽，这样两张图的每一个元素都能直接对齐比较
    scale = ref.width / shot.width
    shot = shot.resize((ref.width, max(1, round(shot.height * scale))), Image.LANCZOS)

    gap = 18
    canvas = Image.new("RGB", (ref.width * 2 + gap, max(ref.height, shot.height) + 30), (235, 240, 248))
    draw = ImageDraw.Draw(canvas)
    canvas.paste(ref, (0, 30))
    canvas.paste(shot, (ref.width + gap, 30))
    draw.text((6, 8), "reference", fill=(60, 70, 90))
    draw.text((ref.width + gap + 6, 8), f"{shot_path.name} @{scale * 100:.0f}%", fill=(60, 70, 90))
    out_cmp = ROOT / ".shots" / f"cmp-{panel}.png"
    canvas.save(out_cmp)

    height = min(ref.height, shot.height)
    blend = Image.blend(
        ref.crop((0, 0, ref.width, height)), shot.crop((0, 0, shot.width, height)), 0.5
    )
    out_blend = ROOT / ".shots" / f"blend-{panel}.png"
    blend.save(out_blend)

    print(f"ok  {out_cmp}")
    print(f"ok  {out_blend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
