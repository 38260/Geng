#!/usr/bin/env bash
# 刷新真实数据：逐日重采全部正式梗（梗名太口语时自动退回别名）+ 重算指标。
#
#   ./scripts/refresh-data.sh            # 默认 30 天窗口
#   DAYS=14 ./scripts/refresh-data.sh    # 只刷最近 14 天
#   LIMIT=5 ./scripts/refresh-data.sh    # 只刷前 5 个梗，先看看效果
#
# 要多久：每个梗 ≈ 30 次搜索 × 1.4s（+ 别名兜底再来一轮），36 个梗大约 20~35 分钟。
# 采到空窗不会删掉上次结果（见 pipeline 的 kept_snapshots），所以随时可以中断。
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
DAYS="${DAYS:-30}"
LIMIT="${LIMIT:-}"

cd "$DIR/backend"
ARGS=(--source bilibili --days "$DAYS")
[ -n "$LIMIT" ] && ARGS+=(--limit "$LIMIT")

PYTHONIOENCODING=utf-8 python -m app.scripts.collect_data "${ARGS[@]}"

echo
PYTHONIOENCODING=utf-8 python - <<'PY'
from datetime import date
from sqlalchemy import func
from app.models import Meme, MemeDailyStats, HotnessSnapshot, SessionLocal

s = SessionLocal()
through = s.query(func.max(MemeDailyStats.stat_date)).scalar()
certified = s.query(Meme).filter(Meme.certified.is_(True)).count()
with_data = (
    s.query(func.count(func.distinct(MemeDailyStats.meme_id)))
    .filter(MemeDailyStats.video_count > 0)
    .scalar()
)
print(f"今天 {date.today()} ｜ 统计截至 {through} ｜ 正式梗 {certified} ｜ 有序列内容的梗 {with_data}")

rows = (
    s.query(Meme, HotnessSnapshot)
    .join(HotnessSnapshot, HotnessSnapshot.meme_id == Meme.id)
    .order_by(HotnessSnapshot.score.desc())
    .limit(5)
    .all()
)
print("当前热榜前 5：")
for meme, snap in rows:
    print(f"  {meme.name:12s} {snap.score:5.1f}")
PY
