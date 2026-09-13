#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# Black House — bootstrap for local (non-Docker) development.
#
#   scripts/setup.sh            # everything: env files, deps, migrate, seed
#   scripts/setup.sh env        # only (re)create the .env files
#   scripts/setup.sh doctor     # only report on prerequisites, change nothing
#
# Knobs:
#   PYTHON=/path/to/python3.12  pick the interpreter explicitly
#   ALLOW_OLD_PYTHON=1          install anyway on Python < 3.12 (best effort)
#   SKIP_FRONTEND=1             backend only
#   SKIP_BACKEND=1              frontend only
# ═════════════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

C_RESET=$'\033[0m'; C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_CYAN=$'\033[36m'
ok()   { printf '%s✔%s %s\n' "$C_GREEN" "$C_RESET" "$1"; }
warn() { printf '%s⚠%s %s\n' "$C_YELLOW" "$C_RESET" "$1"; }
fail() { printf '%s✖%s %s\n' "$C_RED" "$C_RESET" "$1" >&2; }
step() { printf '\n%s▸ %s%s\n' "$C_CYAN" "$1" "$C_RESET"; }

MIN_PY_MAJOR=3
MIN_PY_MINOR=12
MIN_NODE_MAJOR=20

# ── Interpreter discovery ────────────────────────────────────────────────────
pick_python() {
  if [[ -n "${PYTHON:-}" ]]; then echo "$PYTHON"; return; fi
  for candidate in python3.14 python3.13 python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then echo "$candidate"; return; fi
  done
  echo ""
}

PY_BIN="$(pick_python)"

check_python() {
  if [[ -z "$PY_BIN" ]]; then
    fail "No Python interpreter found. Install Python 3.12+ from https://python.org"
    return 1
  fi
  local version major minor
  version="$("$PY_BIN" -c 'import platform; print(platform.python_version())' 2>/dev/null || echo 0.0.0)"
  major="${version%%.*}"
  minor="$(echo "$version" | cut -d. -f2)"
  if (( major < MIN_PY_MAJOR || (major == MIN_PY_MAJOR && minor < MIN_PY_MINOR) )); then
    fail "Found Python $version, but the backend requires >= ${MIN_PY_MAJOR}.${MIN_PY_MINOR}."
    echo "    Install a newer interpreter (pyenv, apt, brew, or python.org) and re-run,"
    echo "    or point at one explicitly:  PYTHON=/usr/bin/python3.12 scripts/setup.sh"
    echo "    Best-effort override:        ALLOW_OLD_PYTHON=1 scripts/setup.sh"
    if [[ "${ALLOW_OLD_PYTHON:-0}" != "1" ]]; then return 1; fi
    warn "ALLOW_OLD_PYTHON=1 — continuing; dependency resolution may fail."
  else
    ok "Python $version ($PY_BIN)"
  fi
  return 0
}

check_node() {
  if ! command -v node >/dev/null 2>&1; then
    fail "Node.js not found. Install Node ${MIN_NODE_MAJOR}+ from https://nodejs.org (or via nvm)."
    return 1
  fi
  local version major
  version="$(node --version)"
  major="${version#v}"; major="${major%%.*}"
  if (( major < MIN_NODE_MAJOR )); then
    fail "Node $version is too old; ${MIN_NODE_MAJOR}+ required."
    return 1
  fi
  ok "Node $version, npm $(npm --version)"
  return 0
}

check_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    ok "Docker $(docker --version | awk '{print $3}' | tr -d ',') + Compose v2"
  else
    warn "Docker/Compose not available — the Docker path (make up) will not work here."
  fi
}

# ── .env bootstrapping ───────────────────────────────────────────────────────
new_secret() {
  if [[ -n "$PY_BIN" ]]; then
    "$PY_BIN" - <<'PY' 2>/dev/null && return
import secrets
print(secrets.token_urlsafe(48))
PY
  fi
  # Fallback without Python: 48 bytes of base64 from the OS CSPRNG.
  head -c 48 /dev/urandom | base64 | tr -d '\n=+/' | cut -c1-64
}

# Create <target> from <template>, substituting the SECRET_KEY placeholder.
create_env() {
  local template="$1" target="$2" secret="$3"
  if [[ -f "$target" ]]; then
    warn "$target already exists — leaving it untouched."
    return 0
  fi
  if [[ ! -f "$template" ]]; then
    fail "Missing template $template"
    return 1
  fi
  sed "s|^SECRET_KEY=.*|SECRET_KEY=${secret}|" "$template" > "$target"
  ok "Created $target"
}

setup_env() {
  step "Environment files"
  local secret
  secret="$(new_secret)"
  printf '  Generated a fresh SECRET_KEY (%s chars).\n' "${#secret}"

  create_env ".env.example"         ".env"         "$secret"
  create_env "backend/.env.example" "backend/.env" "$secret"
  create_env "frontend/.env.example" "frontend/.env" "$secret"

  cat <<'NOTE'

  Both .env files default to *development* settings:
    • SQLite-free — the backend .env points at PostgreSQL on localhost:5432.
      Start it with `docker compose up -d db redis`, or edit DATABASE_URL to
      `sqlite:///./blackhouse.db` for a zero-dependency run.
    • Razorpay keys empty → the built-in mock gateway handles payments.
      Add test keys from the Razorpay dashboard when you integrate for real.

NOTE
}

# ── Dependency installation ──────────────────────────────────────────────────
install_backend() {
  step "Backend — Python virtualenv + dependencies"
  if [[ ! -d backend/.venv ]]; then
    "$PY_BIN" -m venv backend/.venv
    ok "Created backend/.venv"
  else
    warn "backend/.venv already exists — reusing it."
  fi
  backend/.venv/bin/pip install --upgrade pip wheel >/dev/null
  local pip_extra=()
  [[ "${ALLOW_OLD_PYTHON:-0}" == "1" ]] && pip_extra+=(--ignore-requires-python)
  backend/.venv/bin/pip install "${pip_extra[@]}" -e "backend[dev,redis]"
  ok "Backend dependencies installed"
}

install_frontend() {
  step "Frontend — npm dependencies"
  pushd frontend >/dev/null
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
  popd >/dev/null
  ok "Frontend dependencies installed"
}

# ── Database ─────────────────────────────────────────────────────────────────
db_url_from_env() {
  grep -E '^DATABASE_URL=' backend/.env 2>/dev/null | head -1 | cut -d= -f2- || true
}

prepare_database() {
  step "Database — migrations + demo data"
  local url; url="$(db_url_from_env)"
  if [[ "$url" == postgresql* ]]; then
    if ! (exec 3<>"/dev/tcp/${url##*@}"/1) 2>/dev/null; then
      warn "PostgreSQL at ${url##*@} is not reachable."
      echo "    Start it:  docker compose up -d db redis"
      echo "    Or use SQLite for a quick local run:"
      echo "      sed -i.bak 's|^DATABASE_URL=.*|DATABASE_URL=sqlite:///./blackhouse.db|' backend/.env"
      return 0
    fi
  fi
  ( cd backend && ../backend/.venv/bin/alembic upgrade head )
  ok "Migrations applied"
  ( cd backend && ../backend/.venv/bin/python -m scripts.seed_dev )
  ok "Demo data seeded (idempotent)"
}

# ── Entrypoints ──────────────────────────────────────────────────────────────
doctor() {
  step "Prerequisites"
  local status=0
  check_python || status=1
  check_node   || status=1
  check_docker
  printf '\n'
  [[ -f .env ]]         && ok ".env exists"         || warn ".env missing (run: scripts/setup.sh env)"
  [[ -f backend/.env ]] && ok "backend/.env exists" || warn "backend/.env missing"
  [[ -f frontend/.env ]]&& ok "frontend/.env exists"|| warn "frontend/.env missing"
  [[ -d backend/.venv ]]&& ok "backend venv exists" || warn "backend venv missing (make backend-install)"
  [[ -d frontend/node_modules ]] && ok "node_modules exists" || warn "node_modules missing (make frontend-install)"
  return $status
}

main() {
  local cmd="${1:-all}"
  case "$cmd" in
    env)
      [[ -n "$PY_BIN" ]] || true
      setup_env
      ;;
    doctor)
      doctor
      ;;
    all|"")
      printf '\n%sBlack House — local development bootstrap%s\n' "$C_CYAN" "$C_RESET"
      step "Prerequisites"
      check_python
      [[ "${SKIP_FRONTEND:-0}" == "1" ]] || check_node
      check_docker
      setup_env
      [[ "${SKIP_BACKEND:-0}"  == "1" ]] || install_backend
      [[ "${SKIP_FRONTEND:-0}" == "1" ]] || install_frontend
      [[ "${SKIP_BACKEND:-0}"  == "1" ]] || prepare_database

      step "Done"
      cat <<'NEXT'
  Start the stack:

      make dev                 # backend :8000 + storefront :5173 together
      # or in separate terminals
      make backend-run         # http://localhost:8000/docs
      make frontend-run        # http://localhost:5173

  Seeded logins (development only):

      admin@blackhouse.example     Admin@12345
      manager@blackhouse.example   Manager@12345
      staff@blackhouse.example     Staff@12345
      customer@example.com         Customer@12345

  Full guide: docs/SETUP.md · configuration reference: docs/CONFIGURATION.md
NEXT
      ;;
    *)
      fail "Unknown command: $cmd (use: all | env | doctor)"
      exit 2
      ;;
  esac
}

main "$@"
