# Black House — Commerce Backend

Production-oriented **modular monolith** for Black House, a small-batch clothing
manufacturer & D2C brand (Bhopal, Madhya Pradesh, India).

| Layer     | Choice |
|-----------|--------|
| Language  | Python 3.12+ |
| Framework | FastAPI (OpenAPI at `/docs`) |
| ORM       | SQLAlchemy 2.x (typed models) |
| Migrations| Alembic |
| Database  | PostgreSQL (SQLite supported for dev/test mirrors) |
| Schemas   | Pydantic v2 |
| Auth      | JWT access (15 min) + rotating, revocable refresh tokens (7–30 d), Argon2id hashing |
| Payments  | Razorpay (cards/UPI/netbanking) + Cash on Delivery; mock gateway when keys absent |
| Cache/Jobs| Redis **optional** — shared rate limiting. Background work runs in `scripts/worker.py` (or in-process for single-container dev via `RUN_INLINE_SWEEP`) |
| Storage   | Object-storage abstraction: local (dev) / **Cloudinary** (recommended, signed uploads + CDN transforms) / S3-compatible |
| Email     | **Resend** in production; `log` provider for development. Templates render HTML + text for every lifecycle event |
| Tests     | Pytest — **154 tests, 88% coverage**: auth, catalog, checkout, inventory concurrency, payments, orders, returns, upload validation, notifications, storage |

Money is **integer paise** everywhere (`₹1,999 = 199900`). Prices are **GST-inclusive**;
the tax component is derived per line (`taxable = gross / (1 + gst%)`).

---

## Quick start (Docker)

Compose lives at the **repo root** now, so it can bring up the storefront alongside the API.

```bash
# from the repository root
cp .env.example .env            # fill SECRET_KEY; leave Razorpay keys empty for mock gateway
docker compose up --build -d    # postgres + redis + api (:8000) + web (:8080)
docker compose --profile tools run --rm seed
```

Backend only, with the API reachable from your host:

```bash
docker compose up -d db redis                     # just the infrastructure
docker compose up api                             # or the API container too
```

API docs: `http://localhost:8000/docs` · liveness: `/healthz` · readiness (checks the DB):
`/readyz`

## Quick start (no Docker)

```bash
# from the repository root — the Makefile wraps all of this
scripts/setup.sh          # .env files, venv, deps, migrate, seed
make backend-run          # API with autoreload on :8000

# …or by hand, from backend/:
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev,redis]"
export DATABASE_URL="sqlite:///./dev.db"
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed_dev
.venv/bin/uvicorn app.main:app --reload --port 8000
```

## Production

```bash
gunicorn app.main:app -c gunicorn_conf.py     # multiple supervised Uvicorn workers
python -m scripts.worker                       # reservation sweep + notification retries
```

`gunicorn_conf.py` sizes workers from `WEB_CONCURRENCY`, and the Dockerfile runs
`alembic upgrade head` before serving so a deploy cannot run new code against an old schema.
When the standalone worker is deployed, set `RUN_INLINE_SWEEP=false` so API replicas stop polling
the database themselves.

Deploy manifests: `fly.toml` and `railway.toml` here, `render.yaml` at the repo root.

## Architecture

```
backend/
├── app/
│   ├── main.py           # app factory, CORS, exception handlers, /healthz + /readyz
│   ├── core/             # config (fail-fast validation), security (JWT/Argon2), database,
│   │                     # exceptions, deps (role guards), middleware (security headers +
│   │                     # request id), uploads (magic-byte validation), logging (JSON/text),
│   │                     # ratelimit, pagination, types
│   ├── models/           # SQLAlchemy 2.0 typed models (32 tables)
│   ├── schemas/          # Pydantic v2 request/response contracts
│   ├── services/         # ALL business logic — routes stay thin
│   │   ├── order_service.py       # transactional checkout, edits, cancellations, sweep
│   │   ├── inventory_service.py   # reservations, movement ledger, restock alerts
│   │   ├── payment_service.py     # Razorpay/mock gateway, idempotent webhooks, retries
│   │   ├── refund_service.py      # manager-approved, gateway-executed, idempotent
│   │   ├── return_service.py      # 7-day window, exchanges, replacements, restock
│   │   ├── shipping_service.py    # ShippingProvider abstraction + PIN-code rules
│   │   ├── notification_service.py # channel registry: Resend, log, manual wa.me
│   │   ├── email_templates.py     # HTML + text render for every lifecycle event
│   │   ├── storage_service.py     # local / Cloudinary / S3 providers
│   │   └── ...
│   ├── api/v1/           # versioned routers (/api/v1/...)
│   └── tests/            # pytest suite (SQLite mirror, no external services)
├── scripts/
│   ├── seed_dev.py       # idempotent demo data + placeholder artwork
│   └── worker.py         # background: reservation sweep, notification retries
├── alembic/              # migrations
├── gunicorn_conf.py      # production worker sizing and timeouts
├── Dockerfile            # multi-stage, non-root, migrates before serving
└── fly.toml, railway.toml
```

### Roles

`customer < staff < manager < admin` (hierarchical guard `require_roles`).

* **staff** — view customers/orders, create WhatsApp/Instagram/store/phone orders, notes,
  fulfillment updates, tracking, inventory adjustments, view returns & bulk enquiries.
  Cannot refund, approve refunds, cancel after packing, change payment status, change roles.
* **manager** — everything staff + product/variant/inventory/coupon/order management,
  approve/reject cancellations, returns, exchanges, refunds; reports; audit logs.
* **admin** — everything + users/roles, business settings, payment/shipping/return-policy config.

Every manager/admin mutation writes an append-only `audit_logs` row (actor, role, action,
entity, before/after, IP, user-agent).

### Checkout contract (single DB transaction)

1. authenticate → 2. load cart → 3. lock/validate inventory rows (conditional UPDATE guard,
`SELECT … FOR UPDATE` on PostgreSQL) → 4. validate product/variant status → 5. validate stock
→ 6. detect price drift (409 `PRICE_CHANGED` so the customer re-confirms) → 7. validate coupon
→ 8. validate PIN code → 9–13. subtotal / GST / discount / shipping → 14. create order +
snapshot items → 15. payment record → 16. reserve stock → 17. commit → 18. payment session.

* `Idempotency-Key` header prevents duplicate orders on double submit.
* Stock is **reserved** at order creation, **committed** on payment capture (prepaid) or on
  staff confirmation (COD), **released** on cancellation/expiry (30-min TTL sweep worker).
* Webhooks are signature-verified and idempotent (`webhook_events` table); frontend success
  is never trusted — the gateway is re-queried in live mode.
* Payment retry is allowed ~2 min after a failed attempt (`payment_retry_cooldown_seconds`).

### Order lifecycle

`pending_payment → confirmed → processing → packed → shipped → delivered → completed`
with `cancel_requested / cancelled / return_* / returned` branches.
Payment status is tracked **separately** (`created, pending, pending_cod, authorized, paid,
failed, expired, partially_refunded, refunded`).

### Returns & refunds

7-day window from delivery (configurable). Types: refund / size exchange / product exchange /
replacement. Company pays return shipping for damaged/wrong/defective items. Sale items are
returnable for exchange/replacement, not cash refunds. Refund eligibility begins at courier
pickup; completion after inspection. Only manager/admin approve refunds; processing is
idempotent and refunds go back through the original gateway payment.

### Extensibility built in (not implemented yet)

* `warehouses` table + `product_variants.warehouse_id` → multi-warehouse inventory.
* `currency`, tax-region-ready pricing service, country field on addresses → international.
* `ShippingProvider` ABC → courier aggregators with real-time tracking & reverse pickup.
* Storage abstraction → S3/Cloudinary; notification channels → WhatsApp Business API/SMS.
* `product_variants.color` reserved for future colour variants.

## API map (`/api/v1`)

`auth` · `users` · `customers` · `addresses` · `products` (+variants, images, upload) ·
`categories` · `collections` · `carts` · `checkout` (pincode-check, preview, orders) ·
`orders` (+cancel-request, cancel-decision, edit, notes, collect-cod, whatsapp-link) ·
`payments` (session, verify, retry) · `webhooks/razorpay` · `shipments` · `inventory`
(adjustments ledger) · `returns` (+refunds/decide) · `coupons` · `restock-alerts` ·
`bulk-enquiries` · `notifications` · `staff/orders` · `admin` (settings, shipping-rules,
reports, audit-logs, maintenance sweep)

Errors are uniform:

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "…", "details": {} } }
```

## Testing

```bash
cd backend && pytest -q          # 154 tests, SQLite mirror, no external services
cd backend && pytest --cov=app   # 88% coverage
```

Covers: registration/login/refresh rotation + reuse detection, role guards, password reset;
catalog visibility & pre-order windows; disabled variants; size pricing; cart price drift;
coupon matrix; PIN-code blocking; oversell prevention under 5-way concurrency; reservation
release & expiry sweep; webhook success/failure/bad-signature/duplicate; retry cooldown;
refund approval matrix; staff orders; cancellation policy; controlled order edits + audit;
return window, sale-item restriction, damaged-item handling, restock-on-inspection;
restock alerts exactly-once; bulk enquiry pipeline.

> CI runs the suite on Python 3.12. The sandboxed dev mirror may execute it on 3.11 due to
> egress restrictions; the codebase is 3.11∪3.12-compatible and the supported runtime is 3.12+.

## Assumptions to confirm with the business before launch

1. Razorpay account/webhook secret provisioning per environment.
2. Transactional email provider (currently `log` provider — records + logs only).
3. SMS provider selection (interface only today).
4. WhatsApp: automated messages need WhatsApp Business Platform access; until then staff
   use generated `wa.me` links (manual channel, exposed via `/orders/{id}/whatsapp-link`).
5. COD stock is reserved at order acceptance and committed at staff confirmation.
6. Sale items: exchange/replacement only (store credit deferred).
7. Refund eligibility at pickup, completion after inspection.
8. Customers may request cancellation before packing; manager approval always required after.
9. “Upcoming” = visible as coming soon; purchasable only when pre-order is enabled + window open.
10. Staff offline payments: COD + manual collection tracking only until the business confirms
    cash/UPI/bank-transfer handling.
11. Courier provider undecided → manual tracking; reverse pickup modelled via return shipments.
12. GST seeded at 5% per product (apparel slab post-2025 rationalisation) — configurable per
    product/variant.
13. Shipping: state/PIN-range rates + free-shipping threshold (₹15,000 seeded), 5–8 day estimate.
14. Out-of-stock products stay visible only when restock info exists.
15. Notifications default to email + internal; per-customer channel preferences deferred.
