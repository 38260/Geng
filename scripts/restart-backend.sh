#!/usr/bin/env bash
# 重启本地后端（开发/验收用）。端口被别的服务占用时用 BACKEND_PORT 指定。
set -u
PORT="${BACKEND_PORT:-8010}"
DIR="$(cd "$(dirname "$0")/.." && pwd)"

powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force }" >/dev/null 2>&1
sleep 2

cd "$DIR/backend" || exit 1
PYTHONIOENCODING=utf-8 nohup python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning > /tmp/geng-backend.log 2>&1 &
sleep 6
curl -s -m 5 "http://127.0.0.1:$PORT/api/health" && echo && echo "backend on :$PORT"
