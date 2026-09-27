#!/usr/bin/env bash
# 视觉比对回路：截一页 -> 缩到参考稿画板宽度 -> 并排 + 50% 叠图。
#
#   ./scripts/ui_shot.sh home "/”            # 默认打演示数据前端
#   PORT=5173 ./scripts/ui_shot.sh detail "/meme/1"
#
# 产物：.shots/v-<name>.png / .shots/cmp-<name>.png / .shots/blend-<name>.png
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:5173}"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
NAME="${1:?用法: ui_shot.sh <home|detail|settings> [path] [w] [h]}"
PATH_PART="${2:-/}"
W="${3:-1440}"
H="${4:-1515}"

cd "$ROOT"
mkdir -p .shots
OUT_DIR="$(pwd -W)/.shots"

"$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
  --force-device-scale-factor=1 --window-size="${W},${H}" \
  --virtual-time-budget=9000 \
  --screenshot="${OUT_DIR}/v-${NAME}.png" "${BASE}${PATH_PART}" >/dev/null 2>&1

PYTHONIOENCODING=utf-8 python scripts/ui_compare.py ".shots/v-${NAME}.png" "$NAME"
