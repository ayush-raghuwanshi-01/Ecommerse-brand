# Ecommerse-brand — Black House

Monorepo for **Black House**, a small-batch outerwear brand (Bhopal, Madhya Pradesh):

| Path   | What it is |
|--------|-----------|
| `backend/` | Production-oriented commerce backend — FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · Pydantic v2 · JWT + Argon2 · Razorpay/COD · returns · coupons · audit logs. See [`backend/README.md`](backend/README.md). |
| `/` (root) | Vite + React + Three.js brand storefront (landing experience). Will be rewired to consume `/api/v1` next. |

## Run the backend

```bash
cd backend
docker compose up --build      # postgres + redis + api (:8000, /docs)
# or without Docker:
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
DATABASE_URL="sqlite:///./dev.db" .venv/bin/alembic upgrade head
DATABASE_URL="sqlite:///./dev.db" .venv/bin/python -m scripts.seed_dev
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Tests: `cd backend && pytest -q` (55 tests).
