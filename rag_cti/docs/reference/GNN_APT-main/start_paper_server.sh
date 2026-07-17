#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG="${SERVER_LOG:-$ROOT/../../artifacts/trail_inference/logs/server.log}"
mkdir -p "$(dirname "$LOG")"
cd "$ROOT"
export USE_PAPER_BASELINE=1
export PYTHONUNBUFFERED=1
exec .venv/bin/python -m uvicorn predict_paper_server:app \
  --host 127.0.0.1 --port 47823 >>"$LOG" 2>&1
