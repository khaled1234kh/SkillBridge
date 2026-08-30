#!/usr/bin/env bash
# One-time environment setup (idempotent).
set -euo pipefail
cd "$(dirname "$0")/.."

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

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="$(resolve_python)" || {
  echo "Python 3 is required to run SkillBridge." >&2
  exit 1
}

if ! ensure_python_venv_support; then
  exit 1
fi

if [ ! -d "$VENV_DIR" ] || ! resolve_venv_python "$VENV_DIR" >/dev/null 2>&1; then
  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
VENV_PY="$(resolve_venv_python "$VENV_DIR")" || {
  echo "Virtual environment is incomplete." >&2
  exit 1
}
"$VENV_PY" -m pip install --quiet -r backend/requirements.txt
(cd frontend && npm install --silent)
echo "Setup complete."
