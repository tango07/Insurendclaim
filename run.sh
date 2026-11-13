#!/usr/bin/env bash
# Starts backend (port 8000) and frontend (port 5173). Ctrl+C stops both.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --reload --port 8000 &
BACK=$!

cd "$ROOT/frontend"
npm install --no-audit --no-fund --silent
npm run dev &
FRONT=$!

trap 'kill $BACK $FRONT 2>/dev/null' EXIT INT TERM
echo "EPAM powered InsureNdClaim → http://localhost:5173  (API: http://127.0.0.1:8000/docs)"
wait
