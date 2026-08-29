#!/usr/bin/env bash
# One-time environment setup (idempotent).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --quiet -r backend/requirements.txt
(cd frontend && npm install --silent)
echo "Setup complete."
