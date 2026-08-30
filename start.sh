#!/usr/bin/env bash
# SkillBridge single-command startup.
#
# Local mode is the default so a fresh clone works on Windows, macOS, Linux,
# and CI without requiring Docker Desktop. Docker remains optional via --docker.
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
  echo "==> Building and starting SkillBridge containers"
  docker compose up --build -d
  for _ in $(seq 1 60); do
    if command -v curl >/dev/null 2>&1 && curl -fsS http://localhost:8000/api/universities >/dev/null 2>&1; then
      echo "SkillBridge is running in Docker."
      echo "  Frontend: http://localhost:3000"
      echo "  Backend:  http://localhost:8000"
      exit 0
    fi
    sleep 2
  done
  echo "SkillBridge containers did not become ready." >&2
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
      printf '%s\n' "$(command -v "$candidate")"
      return 0
    fi
  done

  return 1
}

ensure_python_venv_support() {
  if "$PYTHON_BIN" -c "import ensurepip" >/dev/null 2>&1; then
    return 0
  fi

  if command -v apt-get >/dev/null 2>&1; then
    echo "==> Installing Python venv support for WSL/Ubuntu"
    if command -v sudo >/dev/null 2>&1; then
      sudo apt-get update
      sudo apt-get install -y python3-venv python3-pip
    else
      apt-get update
      apt-get install -y python3-venv python3-pip
    fi
  fi

  if "$PYTHON_BIN" -c "import ensurepip" >/dev/null 2>&1; then
    return 0
  fi

  echo "Python venv support is missing. On Ubuntu/WSL, run:" >&2
  echo "  sudo apt update && sudo apt install -y python3-venv python3-pip" >&2
  return 1
}

resolve_venv_python() {
  local venv_dir="${1:-.venv}"
  local candidate=""
  for candidate in \
    "$venv_dir/bin/python3" \
    "$venv_dir/bin/python" \
    "$venv_dir/Scripts/python.exe" \
    "$venv_dir/Scripts/python"; do
    if [ -f "$candidate" ] && [ -x "$candidate" ]; then
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

if ! ensure_python_venv_support; then
  exit 1
fi

VENV_DIR="${VENV_DIR:-.venv}"
if [ ! -d "$VENV_DIR" ] || ! resolve_venv_python "$VENV_DIR" >/dev/null 2>&1; then
  echo "==> Creating Python virtual environment"
  rm -rf "$VENV_DIR"
  if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
    echo "Unable to create the Python virtual environment." >&2
    echo "On Ubuntu/WSL, run: sudo apt update && sudo apt install -y python3-venv python3-pip" >&2
    exit 1
  fi
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

PORT="${SKILLBRIDGE_PORT:-8000}"
port_available() {
  if command -v powershell.exe >/dev/null 2>&1; then
    if powershell.exe -NoProfile -Command "(Get-NetTCPConnection -LocalPort $1 -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0" 2>/dev/null | grep -qi 'True'; then
      printf '%s\n' 'in-use'
    else
      printf '%s\n' 'free'
    fi
    return 0
  fi

  "$PYTHON_BIN" - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(('127.0.0.1', port))
    print('free')
except OSError:
    print('in-use')
finally:
    s.close()
PY
}

if [ -z "${SKILLBRIDGE_PORT:-}" ]; then
  if [ "$(port_available "$PORT")" = "in-use" ]; then
    for candidate in 8001 8002 8003 8004 8005 9000; do
      if [ "$(port_available "$candidate")" = "free" ]; then
        PORT="$candidate"
        echo "==> Port 8000 is already in use; using http://localhost:${PORT} instead"
        break
      fi
    done
  fi
fi

if [ "$(port_available "$PORT")" = "in-use" ]; then
  echo "No free local port was available in the fallback range. Please set SKILLBRIDGE_PORT to a free port." >&2
  exit 1
fi

APP_URL="http://localhost:${PORT}"

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
exec "$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
