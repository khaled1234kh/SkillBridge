#!/usr/bin/env bash
# SkillBridge — single-command startup for the whole app.
# Usage:
#   ./start.sh          # build + seed + launch backend (serving the React app)
#   ./start.sh --reset  # delete the database so it re-seeds fresh on next boot
#
# The app runs entirely locally (SQLite) and needs no cloud dependency. If you set
# ANTHROPIC_API_KEY or OPENAI_API_KEY, the four GenAI touchpoints make live API
# calls; otherwise they fall back to clear deterministic generation.

set -euo pipefail
cd "$(dirname "$0")"

APP_URL="${SKILLBRIDGE_URL:-http://localhost:8000}"
PORT="${SKILLBRIDGE_PORT:-8000}"

echo "==> SkillBridge setup"

# Python virtual environment (backend)
if [ ! -d ".venv" ]; then
  echo "==> Creating Python virtual environment"
  python3 -m venv .venv
fi
echo "==> Installing backend dependencies"
.venv/bin/pip install --quiet -r backend/requirements.txt

# Frontend dependencies
echo "==> Installing frontend dependencies"
(cd frontend && npm install --silent)

# Optional clean database
if [ "${1:-}" = "--reset" ] && [ -f backend/skillbridge.db ]; then
  echo "==> Removing existing database (will re-seed on next start)"
  rm -f backend/skillbridge.db
fi

# Build the React frontend so the backend can serve it
echo "==> Building frontend"
(cd frontend && npm run build)

echo ""
echo "==> SkillBridge ready"
echo "    Open: ${APP_URL}"
echo "    Demo accounts (password: demo1234):"
echo "      Student      -> aisha@student.edu"
echo "      Student      -> omar@student.edu"
echo "      Company      -> hr@northstar.com"
echo "      University   -> admin@univ.edu"
echo "    GenAI provider: $([ -n "${ANTHROPIC_API_KEY:-}${OPENAI_API_KEY:-}" ] && echo 'live API (key set)' || echo 'deterministic fallback (set ANTHROPIC_API_KEY or OPENAI_API_KEY for live generation)')"
echo ""

echo "==> Starting server on ${APP_URL}"
cd backend
exec ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
