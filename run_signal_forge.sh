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
REGISTRY="$ROOT_DIR/config/sources.yaml"
SEED="$ROOT_DIR/config/sources.seed.yaml"
INTERVAL="${SIGNAL_FORGE_INTERVAL:-900}"
PIDFILE="$ROOT_DIR/.signal-forge-watch.pid"
LOG_DIR="$ROOT_DIR/logs"

start_collector() {
  if [[ -f "$PIDFILE" ]]; then
    local old
    old="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
      return
    fi
  fi
  mkdir -p "$LOG_DIR"
  PYTHONUNBUFFERED=1 "$PY" -m signal_forge --db "$DB" watch --sources "$REGISTRY" --interval "$INTERVAL" >> "$LOG_DIR/collector.log" 2>&1 &
  echo $! > "$PIDFILE"
}

stop_collector() {
  if [[ -f "$PIDFILE" ]]; then
    local old
    old="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [[ -n "$old" ]]; then kill "$old" 2>/dev/null || true; fi
    rm -f "$PIDFILE"
  fi
}

if command -v curl >/dev/null 2>&1 && curl --silent --fail --max-time 1 "http://127.0.0.1:${PORT}/api/health" >/dev/null; then
  echo "Signal Forge is already running at http://127.0.0.1:${PORT}"
  if [[ ! -f "$REGISTRY" ]]; then cp "$SEED" "$REGISTRY"; fi
  start_collector
  if command -v cmd.exe >/dev/null 2>&1; then cmd.exe /c start "" "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 || true
  elif command -v wslview >/dev/null 2>&1; then wslview "http://127.0.0.1:${PORT}/" || true
  else "$PYTHON_BIN" -m webbrowser "http://127.0.0.1:${PORT}/" || true
  fi
  exit 0
fi

if [[ ! -f "$REGISTRY" ]]; then
  cp "$SEED" "$REGISTRY"
fi

echo "Preparing the source file and vault..."
"$PY" -m signal_forge --db "$DB" init-db
"$PY" -m signal_forge --db "$DB" sync-sources "$REGISTRY"

start_collector
trap stop_collector EXIT INT TERM

echo "Source file: $REGISTRY"
echo "Collector checks that file every ${INTERVAL}s. Log: $LOG_DIR/collector.log"
echo "Signal Forge is opening at http://127.0.0.1:${PORT}"
echo "Press Ctrl+C to stop the local app."
"$PY" -m signal_forge --db "$DB" serve --host 127.0.0.1 --port "$PORT" --sources "$REGISTRY" --open
