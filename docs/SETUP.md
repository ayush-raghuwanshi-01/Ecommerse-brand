# Setup Guide

From a fresh clone to a running storefront with a seeded database.

**Two paths:** [Docker](#path-a-docker-recommended) starts everything in one command and
matches production. [Local](#path-b-local-processes) runs the API and Vite directly, which is
what you want for day-to-day development because of hot reload.

If you only want to know whether your machine is ready, run:

```bash
scripts/setup.sh doctor
```

---

## Prerequisites

| Tool | Version | Check | Needed for |
|------|---------|-------|-----------|
| Python | **3.12+** | `python3 --version` | backend |
| Node.js | **20.11+** | `node --version` | frontend |
| npm | 10+ | `npm --version` | frontend |
| Docker + Compose v2 | any recent | `docker compose version` | Path A only |
| GNU Make | any | `make --version` | the shortcuts (optional) |

Python 3.12 is a hard requirement — `backend/pyproject.toml` declares
`requires-python = ">=3.12"` and pip will refuse to install on older versions. On Ubuntu/Debian:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.12 python3.12-venv
```

Elsewhere, [pyenv](https://github.com/pyenv/pyenv) is the least painful route:
`pyenv install 3.12.7 && pyenv local 3.12.7`.

> **Already have PostgreSQL?** Skip the database steps in Path B and point `DATABASE_URL` at it.

---

## Path A: Docker (recommended)

```bash
git clone <your-fork-url> && cd Ecommerse-brand

cp .env.example .env
# Edit .env and replace SECRET_KEY. Generate one:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

docker compose up --build -d
docker compose --profile tools run --rm seed     # load demo data
```

| Service | URL |
|---------|-----|
| Storefront | http://localhost:8080 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health | http://localhost:8000/healthz |
| Readiness (checks the DB) | http://localhost:8000/readyz |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

Useful commands:

```bash
docker compose logs -f api          # tail one service
docker compose ps                   # what is running
docker compose down                 # stop (data volumes are kept)
docker compose down -v              # stop and DELETE the database
make up / make down / make logs     # the same things via the Makefile
```

The `web` container is nginx serving the built storefront and proxying `/api` to the API
container, so the browser only ever talks to one origin — no CORS involved.

---

## Path B: Local processes

### 1. Bootstrap everything at once

```bash
scripts/setup.sh
```

This creates all three `.env` files with a freshly generated `SECRET_KEY`, builds the Python
venv, installs npm dependencies, runs migrations and seeds demo data. Add flags to skip parts:

```bash
scripts/setup.sh env            # only (re)create the .env files
SKIP_FRONTEND=1 scripts/setup.sh
PYTHON=/usr/bin/python3.12 scripts/setup.sh    # pick the interpreter explicitly
```

### 2. Or do it by hand

```bash
# ── Environment files ────────────────────────────────────────────────
SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# then put $SECRET into SECRET_KEY in both .env files

# ── Backend ──────────────────────────────────────────────────────────
cd backend
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip wheel
.venv/bin/pip install -e ".[dev,redis]"

# ── Database: either start Postgres… ─────────────────────────────────
docker compose up -d db redis          # from the repo root
# …or switch to SQLite for a zero-dependency run:
#   backend/.env → DATABASE_URL=sqlite:///./blackhouse.db

.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed_dev

# ── Frontend ─────────────────────────────────────────────────────────
cd ../frontend
npm ci
```

### 3. Run it

```bash
make dev                 # both, with prefixed logs; Ctrl-C stops both
```

Or in two terminals:

```bash
make backend-run         # API on :8000 with autoreload
make frontend-run        # Vite on :5173, proxies /api → :8000
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` and `/static` to the
backend, so the browser stays same-origin and you never touch CORS locally.

---

## Verifying the installation

```bash
curl -s localhost:8000/healthz          # {"status":"ok",...}
curl -s localhost:8000/readyz           # database check must say "ok"
curl -s "localhost:8000/api/v1/products?page_size=2"
cd backend && .venv/bin/pytest -q       # 154 tests, no external services needed
cd frontend && npm run typecheck && npm run lint && npm run build
```

The test suite runs against a throwaway SQLite database and needs no Postgres, Redis or
network access — it is safe to run at any time.

## Seeded logins

Development accounts, one per role, so you can exercise the permission model:

| Role | Email | Password | Can do |
|------|-------|----------|--------|
| admin | `admin@blackhouse.example` | `Admin@12345` | everything, incl. `/admin` settings and audit log |
| manager | `manager@blackhouse.example` | `Manager@12345` | approvals, refunds, returns, products, coupons |
| staff | `staff@blackhouse.example` | `Staff@12345` | create orders, fulfilment, inventory adjustments |
| customer | `customer@example.com` | `Customer@12345` | shop, cart, checkout, orders, returns |

Demo coupon: `WELCOME500` (₹500 off orders above ₹10,000). Free shipping above ₹15,000.

> These credentials exist **only** so development is possible. `scripts/seed_dev.py` must never
> run against a production database — it is guarded by `APP_ENV` and by refusing to run when an
> admin already exists.

## Payments without Razorpay keys

With `RAZORPAY_KEY_ID` empty the backend uses a built-in **mock gateway**. Checkout shows a
"Test gateway" dialog instead of the card form and `POST /payments/mock-capture/{order_id}`
completes the order. That endpoint refuses to work once real keys are configured, so it cannot
be used to fake a payment in production.

To test real Razorpay: put **test-mode** keys from the dashboard into `.env`, register a webhook
pointing at `https://<your-tunnel>/api/v1/webhooks/razorpay`, and set
`RAZORPAY_WEBHOOK_SECRET`. Locally, [ngrok](https://ngrok.com) or `cloudflared` will expose
port 8000 so Razorpay can reach it.

---

## Troubleshooting

**`pip install` fails with "requires a different Python"**
You are on Python < 3.12. Install 3.12 and point at it: `PYTHON=/usr/bin/python3.12 scripts/setup.sh`.

**`alembic upgrade head` → `connection refused` / `password authentication failed`**
Postgres is not running, or `DATABASE_URL` disagrees with the credentials in `.env`. Either
`docker compose up -d db redis`, or switch to `DATABASE_URL=sqlite:///./blackhouse.db` for a
dependency-free run.

**Port 8000 or 5173 already in use**
`API_PORT=8001 make backend-run` and `WEB_PORT=5174 make frontend-run`. If you change the API
port, also set `VITE_DEV_PROXY_TARGET=http://127.0.0.1:8001` in `frontend/.env`.

**Storefront loads but product images are broken**
Images come from `/static/uploads/...`. Re-run the seed (`make seed`) — it generates the
placeholder artwork. With `STORAGE_PROVIDER=cloudinary` you need valid credentials instead.

**The API returns CORS errors in the browser**
Your frontend origin is not in `CORS_ORIGINS`. This only happens when the browser talks to the
API on a different origin than the page — the Vite proxy and the nginx container both avoid it.
Add the origin as a JSON array: `CORS_ORIGINS=["http://localhost:5173"]`.

**The app refuses to start with "Unsafe configuration for APP_ENV=production"**
That is intentional. `APP_ENV=production` and `staging` fail fast on a default `SECRET_KEY`,
SQLite, `APP_DEBUG=true`, wildcard CORS, an unset webhook secret or local file storage. The
error lists every problem at once — fix them all. For local work use `APP_ENV=development`.

**Changes to `.env` seem ignored**
`Settings` is cached for the process lifetime. Restart the API; `--reload` does not watch `.env`.

**Everything works in Docker but not locally**
Compose overrides `DATABASE_URL`, `REDIS_URL` and `STORAGE_LOCAL_PATH` to use container
hostnames (`db`, `redis`). Those names do not resolve on your machine — your local `.env` must
use `localhost`.

---

## Where to go next

| I want to… | Read |
|------------|------|
| understand every environment variable | [`CONFIGURATION.md`](CONFIGURATION.md) |
| see the plan and what is left | [`ROADMAP.md`](ROADMAP.md) |
| understand the checkout transaction and data model | [`../backend/README.md`](../backend/README.md) |
| deploy to a real host | [`DEPLOYMENT.md`](DEPLOYMENT.md) |
