#!/usr/bin/env bash
# SkillBridge single-command startup.
#
# Local mode is the default so a fresh clone works on Windows, macOS, Linux,
# and CI without requiring Docker Desktop. Docker remains available with
# --docker when the engine is installed and running.
set -euo pipefail
cd "$(dirname "$0")"

RESET=0
MODE="${SKILLBRIDGE_MODE:-local}"
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=1 ;;
    --local) MODE=local ;;
    --docker) MODE=docker ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ "$MODE" = "docker" ]; then
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo "Docker is not available or not running; falling back to local startup." >&2
    MODE=local
  fi
fi

if [ "$MODE" = "docker" ]; then
  if [ "$RESET" -eq 1 ]; then
    echo "==> Removing SkillBridge containers and data volumes"
    docker compose down --volumes --remove-orphans
  fi
  echo "==> Building and starting SkillBridge container"
  docker compose up --build -d
  echo "==> Waiting for the backend health endpoint"
  for _ in $(seq 1 60); do
    if command -v curl >/dev/null 2>&1 && curl -fsS http://localhost:8000/api/universities >/dev/null 2>&1; then
      echo ""
      echo "SkillBridge is running in Docker."
      echo "  App: http://localhost:8000"
      echo "  Logs:     docker compose logs -f"
      exit 0
    fi
    sleep 2
  done
  echo "SkillBridge container did not become ready. Showing status and logs:" >&2
  docker compose ps >&2
  docker compose logs --tail=80 >&2
  exit 1
fi

if [ "$RESET" -eq 1 ]; then
  rm -f backend/skillbridge.db
fi

resolve_python() {
  if [ -n "${PYTHON_BIN:-}" ]; then
    printf '%s\n' "$PYTHON_BIN"
    return 0
  fi
  for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  for candidate in \
    "/c/Users/khale/AppData/Local/Programs/Python/Python312/python.exe" \
    "/mnt/c/Users/khale/AppData/Local/Programs/Python/Python312/python.exe" \
    "$USERPROFILE/AppData/Local/Programs/Python/Python312/python.exe" \
    "/usr/bin/python3"; do
    if [ -n "$candidate" ] && [ -e "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

resolve_venv_python() {
  local venv_dir="${1:-.venv}"
  local candidate=""
  for candidate in \
    "$venv_dir/Scripts/python.exe" \
    "$venv_dir/Scripts/python" \
    "$venv_dir/bin/python" \
    "$venv_dir/bin/python3"; do
    if [ -x "$candidate" ]; then
      if [ "${candidate#/}" = "$candidate" ]; then
        candidate="$PWD/$candidate"
      fi
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(resolve_python)" || {
  echo "Python 3 is required to run SkillBridge. Install Python 3.10+ and try again." >&2
  exit 1
}

VENV_DIR="${VENV_DIR:-.venv}"
if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creating Python virtual environment"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PY="$(resolve_venv_python "$VENV_DIR")" || {
  echo "Virtual environment was created but no Python executable was found under $VENV_DIR." >&2
  exit 1
}

echo "==> Installing backend dependencies"
"$VENV_PY" -m pip install --quiet -r backend/requirements.txt

echo "==> Installing frontend dependencies"
(cd frontend && npm install --silent)

echo "==> Building frontend for local serving"
(cd frontend && npm run build)

port_in_use() {
  "$PYTHON_BIN" - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(('127.0.0.1', port))
    print('in-use')
except OSError:
    print('free')
finally:
    s.close()
PY
}

PORT="${SKILLBRIDGE_PORT:-8000}"
if [ -z "${SKILLBRIDGE_PORT:-}" ] && [ "$(port_in_use "$PORT")" = "in-use" ]; then
  for candidate in 8001 8002 8003 8004 8005 9000; do
    if [ "$(port_in_use "$candidate")" = "free" ]; then
      PORT="$candidate"
      echo "==> Port 8000 is already in use; using http://localhost:${PORT} instead"
      break
    fi
  done
fi

APP_URL="http://localhost:${PORT}"

echo ""
echo "==> SkillBridge ready"
echo "    Open: ${APP_URL}"
echo ""
echo "==> Starting server on ${APP_URL}"
cd backend
exec "$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
