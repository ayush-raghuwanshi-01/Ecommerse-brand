# Black House — commerce platform

Monorepo for **Black House**, a small-batch outerwear brand (Bhopal, Madhya Pradesh): a D2C
storefront plus the commerce backend behind it.

```
Ecommerse-brand/
├── backend/          FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · Pydantic v2
├── frontend/         Vite · React 18 · TypeScript · react-router v7
├── docs/             setup, configuration, roadmap
├── scripts/          bootstrap and dev runners
├── docker-compose.yml   full stack: postgres + redis + api + web
├── Makefile          every command in one place
└── .env.example      root env for Compose (and the api container)
```

| | |
|---|---|
| **backend/** | Production-oriented modular monolith. JWT + Argon2id auth with rotating refresh tokens, hierarchical roles (`customer < staff < manager < admin`), transactional checkout with stock reservation, Razorpay + COD, returns/exchanges/refunds, coupons, shipping rules, restock alerts, and an append-only audit log. 32 tables, **154 tests, 88% coverage**. |
| **frontend/** | White-theme, conversion-focused storefront and staff/admin console in one app: offer bar + sticky nav, editorial hero, trust bar, category tiles, shop with filters/sort/search, PDP with size/variant pricing, buy-now, WhatsApp enquiry and related pieces, cart drawer with free-shipping progress, checkout with PIN-code validation, order tracking, returns, bulk enquiry, and a role-gated admin panel. |

Money is **integer paise** everywhere (`₹1,999 = 199900`). Prices are **GST-inclusive**; the tax
component is derived per line.

---

## Quick start

```bash
# Prerequisites: Python 3.12+, Node 20+, Docker (optional but recommended)
scripts/setup.sh doctor        # is this machine ready?
```

**With Docker** — the whole stack in one command:

```bash
cp .env.example .env           # then set SECRET_KEY
docker compose up --build -d
docker compose --profile tools run --rm seed
```

→ storefront http://localhost:8080 · API docs http://localhost:8000/docs

**Without Docker** — hot-reload development:

```bash
scripts/setup.sh               # .env files, venv, npm deps, migrate, seed
make dev                       # API :8000 + storefront :5173, Ctrl-C stops both
```

→ storefront http://localhost:5173 · API docs http://localhost:8000/docs

Full walkthrough, prerequisites and troubleshooting: **[`docs/SETUP.md`](docs/SETUP.md)**

### Seeded logins (development only)

| Role | Email | Password |
|------|-------|----------|
| admin | `admin@blackhouse.example` | `Admin@12345` |
| manager | `manager@blackhouse.example` | `Manager@12345` |
| staff | `staff@blackhouse.example` | `Staff@12345` |
| customer | `customer@example.com` | `Customer@12345` |

Demo coupon `WELCOME500` (₹500 off above ₹10,000); free shipping above ₹15,000. With no Razorpay
keys configured, checkout uses a built-in **mock gateway** so the full order flow works offline.

---

## Common commands

```bash
make help                 # list every target
make setup                # first-time local bootstrap
make dev                  # backend + frontend together
make up / down / logs     # Docker stack
make migrate / seed       # Alembic + demo data
make test                 # backend suite (154 tests, no services needed)
make lint                 # ruff + eslint + tsc
make clean / clean-all    # artifacts / artifacts + venvs + node_modules
```

Per app: `cd backend && pytest -q` · `cd frontend && npm run build`

---

## Documentation

| Document | What it covers |
|---|---|
| [`docs/SETUP.md`](docs/SETUP.md) | Prerequisites, both install paths, verification, troubleshooting |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | **Every** environment variable, DB pool sizing, per-environment matrix, secret handling |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Production-readiness plan: what is done, what is left, in what order |
| [`backend/README.md`](backend/README.md) | Architecture, checkout contract, order lifecycle, roles, API map |

---

## Status

The commerce engine is built and well tested. **This is not yet launch-ready** — the remaining
blockers are tracked honestly in [`docs/ROADMAP.md`](docs/ROADMAP.md), and the main ones are:
legal/policy pages (Razorpay KYC will reject the application without them), real product
photography, SEO/OG metadata for social sharing, frontend tests, and a load test proving the
1,000-concurrent target.
