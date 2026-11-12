#!/usr/bin/env bash
# Signal Forge WSL launcher. Run from any WSL terminal:
#   /home/aiall/projects/signal-forge/run_signal_forge.sh
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="$ROOT_DIR/.venv"
PY="$VENV_DIR/bin/python"
DB="$ROOT_DIR/signal-forge.db"
PORT="${SIGNAL_FORGE_PORT:-8765}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required. Install it in WSL, then run this script again." >&2
  exit 1
fi

if [[ ! -x "$PY" ]]; then
  echo "Creating local Python environment..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "Preparing Signal Forge..."
"$PY" -m pip install --disable-pip-version-check -q -e "$ROOT_DIR"

# A second launch should open the running cockpit, not fail with "address already in use".
if command -v curl >/dev/null 2>&1 && curl --silent --fail --max-time 1 "http://127.0.0.1:${PORT}/api/health" >/dev/null; then
  echo "Signal Forge is already running at http://127.0.0.1:${PORT}"
  if command -v wslview >/dev/null 2>&1; then wslview "http://127.0.0.1:${PORT}/"; else "$PYTHON_BIN" -m webbrowser "http://127.0.0.1:${PORT}/"; fi
  exit 0
fi

if [[ ! -f "$DB" ]]; then
  echo "Initialising GGP source registry..."
  "$PY" -m signal_forge --db "$DB" init-db
  "$PY" -m signal_forge --db "$DB" import-sources "$ROOT_DIR/config/sources.seed.yaml"
fi

echo "Signal Forge is opening at http://127.0.0.1:${PORT}"
echo "Press Ctrl+C to stop the local app."
exec "$PY" -m signal_forge --db "$DB" serve --host 127.0.0.1 --port "$PORT" --open
