#!/usr/bin/env bash
# 生成 README 用的项目实拍图（README「〇、界面速览」引用的就是这里产出的图）。
#
#   bash scripts/readme_shots.sh
#   BASE=http://127.0.0.1:4173 bash scripts/readme_shots.sh
#
# 两条通道：
#   桌面页 → Chrome 无头 --window-size 抓 1440 宽，再缩到 1100 落地（JPEG q90）
#   窄屏页 → 必须走 CDP 真机视口模拟（scripts/mobile_shot.mjs）
#            用 --window-size 只是把桌面窗口压窄，<meta viewport> 不生效，
#            贴边元素会被裁掉——那正是第一版窄屏图难看的原因。
#
# 依赖：运行中的前后端 + 本机 Chrome + Node 18+
set -euo pipefail

# Git Bash 会把以 "/" 开头的参数改写成 Windows 路径，必须关掉
export MSYS_NO_PATHCONV=1

BASE="${BASE:-http://127.0.0.1:5173}"
MEME_ID="${MEME_ID:-51}"
MOBILE_H="${MOBILE_H:-1014}"   # 窄屏截到「今日热榜」第一行卡片底部（390 宽实测：卡片行 673→1014）
CDP_PORT="${CDP_PORT:-9333}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
NODE="${NODE:-node}"
TMP="$ROOT/.shots/readme"
OUT="$ROOT/docs/screenshots"

cd "$ROOT"
rm -f "$TMP"/*.png          # 清掉上一轮的中间图，免得被下面的压缩步骤当成新图
mkdir -p "$TMP" "$OUT"
TMP_WIN="$(pwd -W)/.shots/readme"
OUT_WIN="$(pwd -W)/docs/screenshots"
UDD="$(pwd -W)/.shots/chrome-readme"
UDD_CDP="$(pwd -W)/.shots/chrome-cdp"   # CDP 实例单独一个 profile，避免和上面抢 user-data-dir 锁

shot() {
  local name="$1" path="$2" width="$3" height="$4"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
    --force-device-scale-factor=1 \
    --user-data-dir="$UDD" \
    --window-size="${width},${height}" \
    --virtual-time-budget=9000 \
    --screenshot="${TMP_WIN}/${name}.png" "${BASE}${path}" >/dev/null 2>&1
  echo "  ✓ ${name}  ${width}x${height}  ${BASE}${path}"
}

echo "① 桌面页（1440 宽抓图）→ $BASE"
shot "home"     "/"                1440 1180
shot "detail"   "/meme/${MEME_ID}" 1440 2000
shot "library"  "/library"         1440 1100
shot "trends"   "/trends"          1440 1100
shot "pipeline" "/pipeline"        1440 1500
shot "manage"   "/manage"          1440 1100

echo "② 缩放 + 转 JPEG（宽 1100，q90）→ docs/screenshots/"
PYTHONIOENCODING=utf-8 python - "$TMP_WIN" "$OUT_WIN" <<'PY'
import sys, os
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
target_w = 1100
total = 0
for f in sorted(os.listdir(src)):
    if not f.endswith(".png"):
        continue
    im = Image.open(os.path.join(src, f)).convert("RGB")
    # 截图含大量视频封面（照片），JPEG q90 体积约为同图 PNG 的 1/3，肉眼无差别
    if im.width > target_w:
        im = im.resize((target_w, round(im.height * target_w / im.width)), Image.LANCZOS)
    out = os.path.join(dst, f[:-4] + ".jpg")
    # 直接覆盖已存在的目标文件在部分受保护/只读环境下会被拒，先删干净再落盘
    if os.path.exists(out):
        os.remove(out)
    im.save(out, "JPEG", quality=90, optimize=True, progressive=True)
    kb = os.path.getsize(out) / 1024
    total += kb
    print(f"  {os.path.basename(out):20s} {im.width}x{im.height}  {kb:.0f} KB")
print(f"  合计 {total/1024:.2f} MB")
PY

echo "③ 窄屏页（CDP 真机视口 390x${MOBILE_H} @2x）"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
  --remote-debugging-port="$CDP_PORT" --user-data-dir="$UDD_CDP" about:blank >/dev/null 2>&1 &
CDP_PID=$!
trap 'kill $CDP_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do
  curl -s --noproxy '*' "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done
# 已存在的文件在本环境禁止原地写，先删掉再让脚本新建
rm -f "$OUT/mobile-home.jpg"
"$NODE" scripts/mobile_shot.mjs "${BASE}/" 390 "$MOBILE_H" "$OUT_WIN/mobile-home.jpg" "$CDP_PORT"
kill $CDP_PID 2>/dev/null || true

echo "完成，图片在 docs/screenshots/"
