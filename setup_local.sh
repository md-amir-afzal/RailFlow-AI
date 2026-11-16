#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
command -v python3 >/dev/null || { echo "Python 3.10+ is required."; exit 1; }
command -v node >/dev/null || { echo "Node.js 20+ is required."; exit 1; }
command -v npm >/dev/null || { echo "npm is required."; exit 1; }
cd "$ROOT/backend"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cd "$ROOT/frontend"
npm install
printf '\nSetup complete. Start the project with ./run_local.sh\n'
