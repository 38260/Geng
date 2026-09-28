"""生成 tabBar 图标（可重跑，别手改 PNG）。

    python scripts/make_tab_icons.py

为什么是几何线稿而不是表情或插画：tabBar 图标只有 81px，emoji 在不同机型上
字形不一致（微信会替换成系统表情），插画在小尺寸下糊成一团。三个图形各自只
表达一件事：热榜=递增的柱子、梗库=一格一格的库、口径=一页说明。

配色取自 frontend/tailwind.config.js：未选中 dusk #546F98、选中 nav #1152F3。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "src" / "assets" / "tabbar"
SIZE = 81          # 微信建议 81×81
SS = 4             # 4x 超采样后缩小，边缘才不毛
INACTIVE = (84, 111, 152, 255)     # #546F98
ACTIVE = (17, 82, 243, 255)        # #1152F3


def _draw() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def _save(image: Image.Image, name: str, suffix: str) -> None:
    image.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / f"{name}{suffix}.png")


def hot(color, suffix) -> None:
    """热榜：三根递增的圆头柱。"""
    image, draw = _draw()
    heights = [26, 44, 62]
    width, gap = 14 * SS, 9 * SS
    left = (SIZE * SS - (width * 3 + gap * 2)) // 2
    base = 70 * SS
    for index, height in enumerate(heights):
        x0 = left + index * (width + gap)
        draw.rounded_rectangle(
            [x0, base - height * SS, x0 + width, base], radius=width // 2, fill=color
        )
    _save(image, "hot", suffix)


def library(color, suffix) -> None:
    """梗库：2x2 圆角格子。"""
    image, draw = _draw()
    cell, gap = 26 * SS, 9 * SS
    origin = (SIZE * SS - cell * 2 - gap) // 2
    for row in range(2):
        for column in range(2):
            x0 = origin + column * (cell + gap)
            y0 = origin + row * (cell + gap)
            draw.rounded_rectangle(
                [x0, y0, x0 + cell, y0 + cell],
                radius=8 * SS,
                outline=color,
                width=6 * SS,
            )
    _save(image, "library", suffix)


def about(color, suffix) -> None:
    """口径：一页带横线的说明。"""
    image, draw = _draw()
    left, top = 18 * SS, 12 * SS
    draw.rounded_rectangle(
        [left, top, 63 * SS, 69 * SS], radius=8 * SS, outline=color, width=6 * SS
    )
    for index, width in enumerate((28, 28, 18)):
        y = top + (14 + index * 12) * SS
        draw.rounded_rectangle(
            [left + 10 * SS, y, left + 10 * SS + width * SS, y + 6 * SS],
            radius=3 * SS,
            fill=color,
        )
    _save(image, "about", suffix)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for shape, name in ((hot, "hot"), (library, "library"), (about, "about")):
        for suffix, color in (("", INACTIVE), ("-on", ACTIVE)):
            (OUT / f"{name}{suffix}.png").unlink(missing_ok=True)
            shape(color, suffix)
    files = sorted(path.name for path in OUT.glob("*.png"))
    print(f"已生成 {len(files)} 张 → {OUT}")
    print(" ", files)


if __name__ == "__main__":
    main()
