#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# Black House — run the backend and the storefront together.
#
#   scripts/dev.sh              # both
#   scripts/dev.sh backend      # API only  (http://localhost:8000/docs)
#   scripts/dev.sh frontend     # Vite only (http://localhost:5173)
#
# Ctrl-C stops both. Logs are interleaved and prefixed.
# ═════════════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

C_API=$'\033[35m'; C_WEB=$'\033[36m'; C_RESET=$'\033[0m'

# ── Preflight ────────────────────────────────────────────────────────────────
[[ -f backend/.env ]] || {
  echo "backend/.env is missing. Run: scripts/setup.sh env" >&2
  exit 1
}

if [[ ! -x backend/.venv/bin/uvicorn ]]; then
  echo "Backend virtualenv not found. Run: make backend-install" >&2
  exit 1
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "frontend/node_modules not found. Run: make frontend-install" >&2
  exit 1
fi

# ── Process management ───────────────────────────────────────────────────────
PIDS=()
shutdown() {
  trap - EXIT INT TERM
  printf '\n%sShutting down…%s\n' "$C_RESET" "$C_RESET"
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap shutdown EXIT INT TERM

prefix() {  # prefix <label> <colour> — tag every line so interleaved logs stay readable
  local label="$1" colour="$2"
  while IFS= read -r line; do
    printf '%s[%s]%s %s\n' "$colour" "$label" "$C_RESET" "$line"
  done
}

start_backend() {
  (
    cd backend
    set -a; . ./.env 2>/dev/null || true; set +a
    exec ../backend/.venv/bin/uvicorn app.main:app \
      --reload --host 0.0.0.0 --port "$API_PORT"
  ) 2>&1 | prefix "api" "$C_API" &
  PIDS+=("$!")
}

start_frontend() {
  (
    cd frontend
    export VITE_DEV_PROXY_TARGET="http://127.0.0.1:${API_PORT}"
    exec npm run dev -- --port "$WEB_PORT"
  ) 2>&1 | prefix "web" "$C_WEB" &
  PIDS+=("$!")
}

mode="${1:-all}"
printf '%sBlack House dev%s — mode: %s\n' "$C_RESET" "$C_RESET" "$mode"

case "$mode" in
  backend)  start_backend ;;
  frontend) start_frontend ;;
  all|"")   start_backend; sleep 2; start_frontend ;;
  *) echo "Usage: scripts/dev.sh [all|backend|frontend]" >&2; exit 2 ;;
esac

printf '\n  storefront  → http://localhost:%s\n' "$WEB_PORT"
printf '  api docs    → http://localhost:%s/docs\n' "$API_PORT"
printf '  health      → http://localhost:%s/healthz\n\n' "$API_PORT"

wait -n
