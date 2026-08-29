#!/usr/bin/env bash
# Run all backend unit tests.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --quiet -r backend/requirements.txt
cd backend
exec ../.venv/bin/python -m pytest tests/ -v
