#!/usr/bin/env bash
# 生成 README 用的项目实拍图：Chrome 无头截取各页面 -> 压到 1100px 宽 -> 落到 docs/screenshots/。
# （README「〇、界面速览」一节引用的就是这里产出的图）
#
#   bash scripts/readme_shots.sh                 # 默认打 http://127.0.0.1:5173
#   BASE=http://127.0.0.1:4173 bash scripts/readme_shots.sh
#
# 依赖：本机 Chrome（headless）+ 运行中的前后端。产物直接进版本库（README 引用），
# 中间图落在 .shots/readme/（已被 .gitignore 忽略）。
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:5173}"
MEME_ID="${MEME_ID:-51}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
TMP="$ROOT/.shots/readme"
OUT="$ROOT/docs/screenshots"

cd "$ROOT"
mkdir -p "$TMP" "$OUT"
TMP_WIN="$(pwd -W)/.shots/readme"

shot() {
  local name="$1" path="$2" width="$3" height="$4"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
    --force-device-scale-factor=1 \
    --user-data-dir="$(pwd -W)/.shots/chrome-readme" \
    --window-size="${width},${height}" \
    --virtual-time-budget=9000 \
    --screenshot="${TMP_WIN}/${name}.png" "${BASE}${path}" >/dev/null 2>&1
  echo "  ✓ ${name}  ${width}x${height}  ${BASE}${path}"
}

echo "截图目标：$BASE  (梗详情用 /meme/${MEME_ID})"
shot "home"        "/"               1440 1180
shot "detail"      "/meme/${MEME_ID}" 1440 2000
shot "library"     "/library"        1440 1100
shot "trends"      "/trends"         1440 1100
shot "pipeline"    "/pipeline"       1440 1500
shot "manage"      "/manage"         1440 1100
shot "mobile-home" "/"                390  844

echo "缩放 + 转 JPEG（宽 1100，q90）-> docs/screenshots/"
PYTHONIOENCODING=utf-8 python - "$TMP" "$OUT" <<'PY'
import sys, os
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
target_w = 1100
total = 0
for f in sorted(os.listdir(src)):
    if not f.endswith(".png"):
        continue
    p = os.path.join(src, f)
    im = Image.open(p).convert("RGB")
    # 截图含大量视频封面（照片），JPEG q90 体积约为同图 PNG 的 1/3，肉眼无差别
    if im.width > target_w:
        im = im.resize((target_w, round(im.height * target_w / im.width)), Image.LANCZOS)
    out = os.path.join(dst, f[:-4] + ".jpg")
    im.save(out, "JPEG", quality=90, optimize=True, progressive=True)
    kb = os.path.getsize(out) / 1024
    total += kb
    print(f"  {os.path.basename(out):20s} {im.width}x{im.height}  {kb:.0f} KB")
print(f"  合计 {total/1024:.2f} MB")
PY

echo "完成，图片在 docs/screenshots/"
