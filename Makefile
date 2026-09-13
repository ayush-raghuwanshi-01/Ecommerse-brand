# ══════════════════════════════════════════════════════════════════════════════
# Black House — monorepo task runner
#
#   make help          list everything
#   make setup         one-time bootstrap for local (non-Docker) development
#   make dev           backend + frontend together
#   make up            whole stack in Docker
#
# Requires: GNU make, Python 3.12+, Node 20+. `make up` needs Docker Compose v2.
# ══════════════════════════════════════════════════════════════════════════════

SHELL           := /bin/bash
.DEFAULT_GOAL   := help
COMPOSE         ?= docker compose
BACKEND         := backend
FRONTEND        := frontend
VENV            := $(BACKEND)/.venv
PY              := $(VENV)/bin/python
PIP             := $(VENV)/bin/pip
UVICORN         := $(VENV)/bin/uvicorn
ALEMBIC         := $(VENV)/bin/alembic
PYTEST          := $(VENV)/bin/pytest
RUFF            := $(VENV)/bin/ruff
NPM             ?= npm

# Local dev runs on SQLite unless you point it at a real PostgreSQL. The path is
# resolved from inside backend/ (every db target cd's there first).
DEV_DATABASE_URL ?= sqlite:///./blackhouse.db

.PHONY: help setup env install up down restart logs ps build \
        migrate revision seed psql \
        backend-install backend-run backend-test backend-lint backend-format \
        frontend-install frontend-run frontend-build frontend-preview \
        frontend-lint frontend-typecheck frontend-format \
        dev test lint format clean clean-all nuke

# ── Meta ──────────────────────────────────────────────────────────────────────
help: ## Show this help
	@printf '\n\033[1mBlack House — available targets\033[0m\n\n'
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@printf '\n'

# ── Bootstrap ─────────────────────────────────────────────────────────────────
setup: env install ## Create .env files, install both apps, migrate + seed (local dev)
	@printf '\n\033[32m✔ Setup complete.\033[0m Start everything with: \033[36mmake dev\033[0m\n\n'

env: ## Create root + backend + frontend .env files from the examples
	@bash scripts/setup.sh env

install: backend-install frontend-install ## Install Python and Node dependencies

# ── Docker (whole stack) ──────────────────────────────────────────────────────
up: env ## Build and start db + redis + api + web in Docker
	$(COMPOSE) up --build -d
	@printf '\n  storefront → http://localhost:8080\n  api docs   → http://localhost:8000/docs\n\n'

down: ## Stop the Docker stack (data volumes are kept)
	$(COMPOSE) down

restart: ## Restart the Docker stack
	$(COMPOSE) restart

logs: ## Tail logs from the Docker stack
	$(COMPOSE) logs -f --tail=100

ps: ## Show Docker stack status
	$(COMPOSE) ps

build: ## Build production artifacts for both apps
	$(MAKE) frontend-build
	@printf '  backend image: docker build -t blackhouse-api ./backend\n'

nuke: ## ⚠ Stop the Docker stack and DELETE all volumes (database included)
	$(COMPOSE) down -v --remove-orphans

# ── Database ──────────────────────────────────────────────────────────────────
migrate: ## Apply Alembic migrations (local venv)
	cd $(BACKEND) && DATABASE_URL="$(DEV_DATABASE_URL)" ../$(ALEMBIC) upgrade head

revision: ## Create a new migration: make revision m="add coupons index"
	cd $(BACKEND) && DATABASE_URL="$(DEV_DATABASE_URL)" ../$(ALEMBIC) revision --autogenerate -m "$(m)"

seed: ## Load demo data (idempotent; skips if an admin already exists)
	cd $(BACKEND) && DATABASE_URL="$(DEV_DATABASE_URL)" ../$(PY) -m scripts.seed_dev

psql: ## Open a psql shell against the Dockerised database
	$(COMPOSE) --profile tools run --rm psql

# ── Backend ───────────────────────────────────────────────────────────────────
backend-install: ## Create the Python venv and install backend + dev deps
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip wheel
	$(PIP) install -e "$(BACKEND)[dev]"

backend-run: ## Run the API with autoreload on :8000
	cd $(BACKEND) && DATABASE_URL="$(DEV_DATABASE_URL)" ../$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

backend-test: ## Run the pytest suite
	cd $(BACKEND) && DATABASE_URL="sqlite:///./test.db" ../$(PYTEST)

backend-lint: ## Ruff lint + format check
	cd $(BACKEND) && ../$(RUFF) check . && ../$(RUFF) format --check .

backend-format: ## Ruff autofix + format
	cd $(BACKEND) && ../$(RUFF) check --fix . && ../$(RUFF) format .

# ── Frontend ──────────────────────────────────────────────────────────────────
frontend-install: ## npm ci (falls back to npm install without a lockfile)
	cd $(FRONTEND) && ($(NPM) ci || $(NPM) install)

frontend-run: ## Vite dev server on :5173 (proxies /api → :8000)
	cd $(FRONTEND) && $(NPM) run dev

frontend-build: ## Type-check and build the production bundle
	cd $(FRONTEND) && $(NPM) run build

frontend-preview: ## Serve the built bundle locally
	cd $(FRONTEND) && $(NPM) run preview

frontend-lint: ## ESLint
	cd $(FRONTEND) && $(NPM) run lint

frontend-typecheck: ## tsc --noEmit across app + node projects
	cd $(FRONTEND) && $(NPM) run typecheck

frontend-format: ## Prettier write
	cd $(FRONTEND) && $(NPM) run format

# ── Aggregate ─────────────────────────────────────────────────────────────────
dev: ## Run backend (:8000) and frontend (:5173) together — Ctrl-C stops both
	@bash scripts/dev.sh

test: backend-test ## Run all test suites
	@printf '\033[33mℹ The frontend has no test runner yet — see docs/CODE_REVIEW.md\033[0m\n'

lint: backend-lint frontend-lint frontend-typecheck ## Lint + type-check everything

format: backend-format frontend-format ## Format everything

clean: ## Remove build artifacts (keeps dependencies and databases)
	rm -rf $(FRONTEND)/dist $(FRONTEND)/*.tsbuildinfo $(FRONTEND)/node_modules/.tmp
	find $(BACKEND) -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache $(BACKEND)/*.egg-info

clean-all: clean ## Also remove virtualenvs, node_modules and local databases
	rm -rf $(VENV) $(FRONTEND)/node_modules
	rm -f $(BACKEND)/*.db $(BACKEND)/*.db-shm $(BACKEND)/*.db-wal
