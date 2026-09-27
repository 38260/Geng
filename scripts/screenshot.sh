#!/usr/bin/env bash
# 视觉验收：把每个页面截成 Desktop / Mobile 两张图，便于和 docs/design/reference-ui.png 对比。
#
#   ./scripts/screenshot.sh                 # 默认打 http://localhost:5173
#   BASE=http://localhost:4173 ./scripts/screenshot.sh
#
# 依赖：本机 Chrome（headless）。输出在 .shots/（已被 .gitignore 忽略）。
set -euo pipefail

BASE="${BASE:-http://localhost:5173}"
OUT="${OUT:-.shots}"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"

mkdir -p "$OUT"
OUT_DIR="$(pwd -W)/$OUT"   # Chrome 需要 Windows 形式的绝对路径

capture() {
  local name="$1" path="$2" width="$3" height="$4"
  local url="${BASE}${path}"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
    --force-device-scale-factor=1 \
    --window-size="${width},${height}" \
    --virtual-time-budget=9000 \
    --screenshot="${OUT_DIR}/${name}.png" "$url" >/dev/null 2>&1
  echo "  ✓ ${name}  (${width}x${height})  ${url}"
}

echo "截图目标：$BASE"
capture "desktop-home"        "/"            1440 1500
capture "desktop-home-top"    "/"            1440 900
capture "desktop-detail"      "/meme/1"      1440 1600
capture "desktop-library"     "/library"     1440 1200
capture "desktop-trends"      "/trends"      1440 1200
capture "desktop-settings"    "/settings"    1440 1100
capture "mobile-home"         "/"            390  1400
capture "mobile-detail"       "/meme/1"      390  1500
echo "完成，图片在 $OUT/"
