#!/usr/bin/env python
"""从 docs/design/reference-ui.png 里裁出真实素材，供前端直接使用。

前端设计提示词 §十 明确要求"项目目录中已存在的图片资源优先直接使用，
不要生成风格完全不同的新图片"。本机没有图像生成额度，因此直接从参考图取：
梗缩略图、Logo、头像、Hero 吉祥物。

    python scripts/extract_ref_assets.py

坐标是对参考图做连通域检测 + 逐张校对得到的（参考图为 1536x1024 三面板拼图，
首页面板在 x 0..945）。裁出的小图按 3 倍 LANCZOS 放大，避免在 2x 屏上发糊。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "docs" / "design" / "reference-ui.png"
OUT = ROOT / "frontend" / "public" / "thumbs"

# (输出名, 裁剪框, 放大倍数)
ASSETS: list[tuple[str, tuple[int, int, int, int], int]] = [
    # ---- 今日热榜 5 张（卡片内缩插图，避开圆角与徽章，132x99）----
    ("muyu.png",            (205, 387, 337, 486), 3),   # 电子木鱼
    ("shiba.png",           (357, 387, 489, 486), 3),   # 狗都不谈恋爱
    ("college-girl.png",    (509, 387, 641, 486), 3),   # 我是大学生
    ("tom.png",             (661, 387, 793, 486), 3),   # 阿巴阿巴
    ("blob.png",            (813, 387, 945, 486), 3),   # 啊对对对
    # ---- 精选推荐 4 张（竖版 70x99）----
    ("shiba-serious.png",   (206, 737, 276, 836), 3),   # 我不是黄豆
    ("anime-summer.png",    (417, 737, 487, 836), 3),   # 军训好热
    ("penguin.png",         (604, 737, 674, 836), 3),   # 这也太刑了
    ("lake.png",            (787, 737, 857, 836), 3),   # 夏天的风
    # ---- 品牌与装饰 ----
    ("logo-ghost.png",      (28, 12, 80, 64), 4),       # 顶栏蓝色小幽灵 Logo（拿喇叭的那个）
    ("avatar.png",          (900, 16, 938, 54), 4),     # 顶栏头像
    # Hero 右侧整条装饰带（水彩 + 吉祥物 + "现在不赶就晚了"），
    # 左边界取在标题结束处之后，避免和真实文字叠影
    ("hero-band-right.png", (650, 74, 946, 248), 3),
    ("hero-mascot.png",     (766, 86, 946, 248), 4),    # 只要吉祥物本体
]

# 热榜封面：参考图在这里叠了名次徽章，裁出来要抹掉
HOT_LIST = {"muyu.png", "shiba.png", "college-girl.png", "tom.png", "blob.png"}


def main() -> int:
    if not REF.exists():
        print(f"找不到参考图：{REF}")
        return 1
    ref = Image.open(REF).convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)

    for name, box, scale in ASSETS:
        crop = ref.crop(box)
        if name in HOT_LIST:
            # 参考图把名次徽章画在封面左上角，裁出来会带进别人的徽章；
            # 用右侧同一条像素把它抹掉，前端自己再叠真实名次徽章。
            patch = crop.crop((48, 0, 96, 48))
            crop.paste(patch, (0, 0))
        big = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
        big.save(OUT / name)
        print(f"  {name:22s} {crop.width}x{crop.height} -> {big.width}x{big.height}")
    print(f"共 {len(ASSETS)} 张，输出目录 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
