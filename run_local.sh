#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -x "$ROOT/backend/.venv/bin/python" || ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Run ./setup_local.sh first."
  exit 1
fi
cleanup() { kill "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
cd "$ROOT/backend"
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 & API_PID=$!
cd "$ROOT/frontend"
npm run dev -- --host 127.0.0.1 & WEB_PID=$!
printf 'RailFlow AI starting. Dashboard: http://127.0.0.1:5173  |  API docs: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop both servers.\n'
wait "$WEB_PID"
