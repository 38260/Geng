"""把开题报告 Markdown 排成可提交的 Word / PDF。

    python scripts/build_report.py

docx 走 pandoc（Markdown → docx，标题层级和表格都保留，可在 Word 里继续编辑）；
pdf 走 LibreOffice 的 HTML→pdf（本机 LibreOffice 的 docx 导出组件是坏的，
报 `impl_store ... 0x81a`，所以 docx 不要再交给它）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "research" / "开题报告.md"
OUT_DIR = SRC.parent
SOFFICE = Path("C:/Program Files/LibreOffice/program/soffice.exe")

CSS = """
@page { size: A4; margin: 2.2cm 2cm; }
body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 10.8pt;
       line-height: 1.75; color: #14161f; }
h1 { font-size: 20pt; margin: 0 0 4pt; }
h2 { font-size: 14.5pt; margin: 22pt 0 6pt; border-bottom: 1.4pt solid #FB3A5E;
     padding-bottom: 3pt; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; color: #3C5989; }
p { margin: 0 0 7pt; text-align: justify; }
hr { border: none; border-top: 0.6pt solid #d8deea; margin: 12pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 10pt; }
th, td { border: 0.6pt solid #b9c3d4; padding: 4pt 6pt; vertical-align: top; }
th { background: #eef3fa; text-align: left; }
code, pre { font-family: Consolas, monospace; font-size: 9.6pt; background: #f3f6fb; }
pre { padding: 7pt 9pt; border: 0.6pt solid #d8deea; white-space: pre-wrap; }
blockquote { margin: 6pt 0; padding: 5pt 9pt; border-left: 2.6pt solid #FB3A5E;
             background: #fdf3f5; color: #3C5989; }
ol { margin: 0 0 8pt 18pt; padding: 0; }
ol > li { margin-bottom: 2pt; }
strong { color: #0b1a33; }
"""


def docx_via_pandoc() -> bool:
    """pandoc 能把 Markdown 直接转成可编辑的 docx（本机 LibreOffice 不行）。"""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        return False
    subprocess.run(
        [pandoc, str(SRC), "-o", str(OUT_DIR / "开题报告.docx"),
         "--from", "markdown", "--to", "docx"],
        check=False, capture_output=True, timeout=240,
    )
    return (OUT_DIR / "开题报告.docx").exists()


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"找不到源文件：{SRC}")
    body = markdown.markdown(SRC.read_text(encoding="utf-8"),
                             extensions=["tables", "sane_lists", "smarty"])
    html = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="utf-8"/>'
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )
    interim = OUT_DIR / "开题报告.html"
    interim.write_text(html, encoding="utf-8")

    if docx_via_pandoc():
        produced = OUT_DIR / "开题报告.docx"
        print(f"已生成 {produced}（{produced.stat().st_size // 1024} KB）")
    else:
        print(f"pandoc 不可用：用 Word/WPS 打开 {interim} → 另存为 .docx 即可，"
              f"样式（标题层级、表格边框、字体）都在。")

    if not SOFFICE.exists():
        print(f"未找到 LibreOffice（{SOFFICE}），pdf 未生成，可打印 {interim}")
        return 1

    # 过滤器要写死：只写 "pdf" 时 LibreOffice 会挑错导出组件而失败
    # subprocess 不过 shell，引号要原样给 soffice，不要再转义
    subprocess.run(
        [str(SOFFICE), "--headless", "--convert-to", "pdf:writer_pdf_Export",
         "--outdir", str(OUT_DIR), str(interim)],
        check=False, capture_output=True, timeout=240,
    )
    produced = OUT_DIR / "开题报告.pdf"
    size = produced.stat().st_size if produced.exists() else 0
    print(f"{'已生成' if size else '生成失败'} {produced}（{size // 1024} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
