#!/usr/bin/env python
"""把 Web 端 Hero 的水彩素材切成小程序能用的透明底贴图。

小程序首页 Hero 之前只有文字，参考图里那截"现在不赶就晚了！+ 戴耳机的吉祥物"
整块没搬过来。原因是 `frontend/public/thumbs/hero-band-right.png` 是从参考 UI
直接裁的**不透明**位图（粉底），在 Web 上靠"卡片背景与素材同色"糊过去，
而手机上卡片要放右下角一小块，糊不住，必须真透明。

这里做三件事：
1. 从原素材按区域裁出吉祥物 / 手写标语 / 毛笔下划线；
2. 从四边向内做容差漫水填充，只把**连通的背景**抠成透明，
   被描边包住的白色身体和水彩笔触都保留（阈值法会把身体一起吃掉）；
3. 按显示尺寸 2x 缩放 + 调色板量化，控制体积（小程序主包 2M 上限）。

    python scripts/cut_mp_assets.py

输出到 `miniprogram/src/assets/hero/`，由 Taro 的 copy.patterns 带进 dist/assets/。
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC_BAND = ROOT / "frontend" / "public" / "thumbs" / "hero-band-right.png"
SRC_REF = ROOT / "docs" / "design" / "reference-ui.png"
OUT = ROOT / "miniprogram" / "src" / "assets" / "hero"

# (输出名, 源图, 裁剪框, 抠图方式, 背景容差(每通道平均), 目标宽, 额外抹掉的源图坐标)
#   flood   ：从四边向内漫水填充，只抠掉与边框连通的近背景色
#   redness ：按"有多珊瑚红"给 alpha，黑色毛笔字和蓝色副标题会被自动丢掉
#   wipe    ：素材互相咬合时点名抹掉的碎片（例如标语那根"!"压在吉祥物头上）
JOBS: list[tuple[str, Path, tuple[int, int, int, int], str, int, int, list[tuple[int, int, int, int]]]] = [
    # 整块构图：手写标语 + 吉祥物。参考图里两者是咬合在一起的，
    # 拆开切会互相带进对方的碎片，所以首页 Hero 用这一整块。
    ("hero-art.png", SRC_BAND, (140, 55, 762, 522), "flood", 30, 340, []),
    # 只留吉祥物：y 从 170 起切才不削掉帽子顶，标语那根"!"用 wipe 抹掉
    ("mascot.png", SRC_BAND, (415, 170, 762, 522), "flood", 30, 300, [(432, 152, 468, 208)]),
    # 标题下那道珊瑚红横扫：参考图 y166..202 那一条
    ("underline.png", SRC_REF, (190, 166, 652, 202), "redness", 0, 464, []),
]


def wipe_region(im: Image.Image, box: tuple[int, int, int, int], origin: tuple[int, int]) -> Image.Image:
    """把源图坐标下的一块区域抹成透明。"""
    arr = np.array(im).astype(int)
    x0, y0, x1, y1 = (box[0] - origin[0], box[1] - origin[1], box[2] - origin[0], box[3] - origin[1])
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(arr.shape[1], x1), min(arr.shape[0], y1)
    arr[y0:y1, x0:x1, 3] = 0
    return Image.fromarray(arr.clip(0, 255).astype("uint8"))


def flood_key(rgb: Image.Image, tol_per_channel: int) -> Image.Image:
    """把与四边连通、且颜色接近背景的像素变成透明。"""
    arr = rgb.convert("RGB")
    px = np.array(arr).astype(int)
    h, w, _ = px.shape
    border = np.concatenate([px[0], px[-1], px[:, 0], px[:, -1]])
    ref = np.median(border, axis=0)
    close = (np.abs(px - ref).sum(axis=2) < tol_per_channel * 3)

    keyed = np.zeros((h, w), dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    def seed(y: int, x: int) -> None:
        if close[y, x] and not keyed[y, x]:
            keyed[y, x] = True
            queue.append((y, x))

    for x in range(w):
        seed(0, x)
        seed(h - 1, x)
    for y in range(h):
        seed(y, 0)
        seed(y, w - 1)

    while queue:
        y, x = queue.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and close[ny, nx] and not keyed[ny, nx]:
                keyed[ny, nx] = True
                queue.append((ny, nx))

    alpha = (255 - keyed.astype("uint8") * 255).reshape(h, w)
    out = arr.convert("RGBA")
    # 边缘羽化 1px，避免缩放后出现锯齿硬边
    out.putalpha(Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(0.6)))
    return out


def redness_key(rgb: Image.Image, _tol: int = 0) -> Image.Image:
    """只保留"够珊瑚红"的像素：越红越不透明，黑字/蓝字/浅粉底都变透明。"""
    arr = rgb.convert("RGB")
    px = np.array(arr).astype(int)
    red = px[..., 0] - np.maximum(px[..., 1], px[..., 2])
    alpha = np.clip((red - 18) * 9, 0, 255).astype("uint8")
    out = arr.convert("RGBA")
    out.putalpha(Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(0.5)))
    return out


KEYERS = {"flood": flood_key, "redness": redness_key}


def fade_bottom(im: Image.Image, frac: float = 0.16) -> Image.Image:
    """把最下面一截渐隐。素材是从参考图那条带子底边直接切下来的，
    吉祥物被拦腰切断，贴在卡片上会露出一道硬边；淡出就没这个问题。"""
    arr = np.array(im).astype(int)
    h = arr.shape[0]
    start = int(h * (1 - frac))
    ramp = np.ones(h)
    tail = np.linspace(1.0, 0.0, h - start)
    ramp[start:] = tail
    arr[..., 3] = (arr[..., 3] * ramp[:, None]).astype(int)
    return Image.fromarray(arr.clip(0, 255).astype("uint8"))


def trim(im: Image.Image) -> Image.Image:
    box = im.getbbox()
    return im.crop(box) if box else im


def main() -> int:
    missing = [str(p) for p in {SRC_BAND, SRC_REF} if not p.exists()]
    if missing:
        print("缺少源图：" + "、".join(missing))
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, src, box, mode, tol, target_w, wipes in JOBS:
        base = Image.open(src).convert("RGB")
        keyed = KEYERS[mode](base.crop(box), tol)
        for region in wipes:
            keyed = wipe_region(keyed, region, (box[0], box[1]))
        crop = trim(keyed)
        if mode == "flood":
            crop = fade_bottom(crop)
        scale = target_w / crop.width
        out = crop.resize((target_w, max(1, round(crop.height * scale))), Image.LANCZOS)
        colors = 64 if mode == "redness" else 192
        out = out.quantize(colors=colors, method=Image.FASTOCTREE).convert("RGBA")
        path = OUT / name
        out.save(path, optimize=True)
        print(f"  {name:14s} {crop.width}x{crop.height} -> {out.width}x{out.height}  {path.stat().st_size // 1024} KB")
    print(f"输出目录 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
