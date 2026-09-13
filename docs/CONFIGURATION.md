# Configuration Reference

Every environment variable the platform reads, what it does, and what to set it to per
environment.

**Three `.env` files, three different readers:**

| File | Read by | When |
|------|---------|------|
| `.env` (repo root) | Docker Compose | `docker compose up` — interpolated *and* injected into the `api` container |
| `backend/.env` | pydantic-settings | the API and Alembic, when run **without** Docker |
| `frontend/.env` | Vite | build and dev server. Only `VITE_*` reaches the browser |

Precedence for the backend: **process environment → `backend/.env` → code default**. That is why
the same container image can be promoted across environments by changing env alone.

⚠ marks a value that must change before a real deployment.

---

## 1. Application

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development` \| `staging` \| `production` \| `test`. `staging`/`production` enable fail-fast validation — see [§9](#9-fail-fast-production-guards). |
| `APP_DEBUG` | `true` | ⚠ Must be `false` outside development. Implies `DEBUG` logging when `LOG_LEVEL` is left at `INFO`. |
| `PROJECT_NAME` | `Black House Commerce API` | Shown in the OpenAPI docs title. |
| `API_V1_STR` | `/api/v1` | Router prefix. Changing it requires matching `VITE_API_BASE_URL`. |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL`. |
| `LOG_FORMAT` | `text` | `json` for platform log aggregation, `text` for reading locally. |
| `RUN_INLINE_SWEEP` | `true` | Run the reservation sweep inside the API process. ⚠ Set **`false`** in production once `scripts/worker.py` is deployed. |
| `API_BASE_URL` | `http://localhost:8000` | Public origin of this API. Used to build webhook callbacks and absolute links. |
| `FRONTEND_URL` | `http://localhost:5173` | Storefront origin. Used in email links (`View your order`). |
| `SENTRY_DSN` | *(empty)* | Optional. Requires `pip install ".[observability]"`. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | 0.0–1.0. Start at `0.1` in production; performance tracing costs quota. |

### `SECRET_KEY` ⚠

```
SECRET_KEY=           # default: dev-only-insecure-secret
```

Signs JWT access tokens and hashes refresh-token digests. **This is the most sensitive value in
the system** — anyone holding it can forge a valid admin token.

- Minimum **32 characters**; `staging`/`production` refuse to boot below that.
- Generate: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- Use a **different key per environment**. Reusing the dev key in production means a leaked
  laptop compromises live sessions.
- **Rotating it invalidates every issued token** — all users must sign in again. Rotate on a
  schedule, immediately on suspicion of exposure, and after any staff member with production
  access leaves.

---

## 2. Database

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./blackhouse.db` | ⚠ PostgreSQL in every deployed environment. |
| `DATABASE_ECHO` | `false` | Logs every SQL statement. Extremely noisy; use only while debugging a query. |
| `DB_POOL_SIZE` | `10` | Persistent connections **per worker process**. |
| `DB_MAX_OVERFLOW` | `20` | Extra connections opened under burst, then closed. |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | How long a request waits for a free connection before failing. |
| `DB_POOL_RECYCLE_SECONDS` | `1800` | Recycle connections before a proxy or firewall drops them idle. |

### Connection string forms

```bash
# Local Postgres
DATABASE_URL=postgresql+psycopg://blackhouse:blackhouse@localhost:5432/blackhouse

# Inside Docker Compose — hostname is the service name, not localhost
DATABASE_URL=postgresql+psycopg://blackhouse:blackhouse@db:5432/blackhouse

# Managed provider over TLS (Neon, Supabase, RDS, Cloud SQL)
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require

# Managed provider through its pooler (recommended — see below)
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST-pooler:5432/DB?sslmode=require

# SQLite — development and tests only
DATABASE_URL=sqlite:///./blackhouse.db
```

The driver is **psycopg 3** (`postgresql+psycopg://`), not `psycopg2`. A connection string
copied from a provider's dashboard will usually say `postgresql://` — add `+psycopg` after the
scheme or SQLAlchemy will not find a driver.

### ⚠ Sizing the pool — read this before deploying

The API is synchronous, and Gunicorn runs **multiple worker processes**, each with its own pool.
Total connections consumed:

```
connections = workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
```

With the defaults (`WEB_CONCURRENCY=3`, pool 10 + overflow 20) that is **90 connections**. A
typical managed plan caps you far lower — Neon's free tier allows 100 total, a small RDS
instance 87, and a Supabase free tier around 60 *shared with every other service*.

So before you scale out:

1. **Use your provider's pooler** (Supavisor, PgBouncer, RDS Proxy). Connect through the
   pooler hostname in `DATABASE_URL`.
2. **Reduce per-worker pool** so the product stays under the cap:
   `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=5` → 30 connections across 3 workers.
3. Add the standalone worker process to the count — it holds connections too.

Pooler caveat: in **transaction** pooling mode, prepared statements break. psycopg 3 does not use
them by default here, but if you add a driver that does, set
`prepare_threshold=0` on the connection.

### SQLite limitations

SQLite is supported for development and the test suite. It lacks `SELECT … FOR UPDATE`, so
`supports_row_locking()` returns `False` and the checkout falls back to conditional-`UPDATE`
guards. Those guards are genuinely safe for a single process, but **SQLite is not appropriate
once real orders exist** — there is no concurrent write throughput, no replication and no
point-in-time recovery.

---

## 3. Redis (optional)

| Variable | Default | Notes |
|---|---|---|
| `REDIS_URL` | *(empty)* | e.g. `redis://localhost:6379/0`. Empty = in-process rate limiting. |

Redis backs the **shared rate limiter** only. With it unset, each replica keeps its own in-memory
bucket, so a determined client gets `RATE_LIMIT_PER_MINUTE × replicas × workers` attempts. That is
acceptable for one replica and wrong for more. `/readyz` reports Redis as `ok`, `unavailable` or
`disabled` — unavailable degrades rather than failing readiness, because rate limiting is not
worth pulling a healthy replica out of rotation.

Requires `pip install ".[redis]"`.

**Set `REDIS_URL` in production.** Without it the limiter is per-worker, which means the effective
budget scales with the number of processes you are running — precisely the opposite of what you
want when you scale out to handle traffic.

### 3.1 Rate limiting tiers

Two tiers, deliberately (`app/core/ratelimit.py`):

| Tier | Limit | Keyed by | Applied to |
|---|---|---|---|
| Strict (opt-in) | `RATE_LIMIT_PER_MINUTE` or the per-route override | client IP **+ path** | `/auth/login`, `/auth/register`, `/auth/password-reset/request` |
| Blanket (default-on) | `RATE_LIMIT_DEFAULT_PER_MINUTE` | user id if authenticated, else client IP | every other `/api/` route |

The blanket tier exists because a decorator is opt-in: with only the auth endpoints decorated, the
other ~90 handlers had no limit at all. `RateLimitMiddleware` inverts that, so a newly added
endpoint is protected unless it is explicitly exempted.

The strict tier is keyed by IP rather than user id on purpose — credential stuffing and
password-reset abuse must be throttled per source address even when the caller is anonymous, and an
attacker holding many accounts should not get a fresh budget per account. Conversely the blanket
tier is keyed by user id so that shoppers behind one NAT address (corporate offices, hostels, mobile
carriers) do not collectively exhaust a single budget.

Exempt from all limiting: `/healthz`, `/readyz`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, and
anything outside `/api/` (including the `/static/uploads` mount). Throttling a health probe would
get a healthy instance marked unhealthy and killed.

Rejected requests return `429` with a `Retry-After` header and the standard
`{"error": {"code": "RATE_LIMITED", ...}}` envelope. `Retry-After` is in CORS `expose_headers` so a
browser client can actually read it.

The in-process fallback is memory-bounded (`_MAX_KEYS = 50_000`, LRU eviction) so a client minting
unbounded keys cannot grow the worker until it is OOM-killed.

### 3.2 Proxy trust and the real client IP

On every PaaS target the container is reached only through the platform load balancer, so the TCP
peer of each request is **the proxy, not the shopper**. Left unhandled this silently breaks two
things: every caller collapses into one rate-limit bucket, and the audit log records your own
infrastructure as the actor instead of the person who cancelled the order.

Two settings fix it, and both default correctly for a PaaS deploy:

* `FORWARDED_ALLOW_IPS` (default `*`) — tells Gunicorn/Uvicorn's `ProxyHeadersMiddleware` to rewrite
  `request.client.host` from `X-Forwarded-For` and the URL scheme from `X-Forwarded-Proto`. The
  scheme matters for the `Secure` cookie flag.
* `TRUST_PROXY_HEADERS` (default `true`) — `app/core/net.py:client_ip()` resolves the real address
  for the rate limiter, audit log and request log.

`X-Forwarded-For` is client-controlled, so this is only safe when the port is not internet-reachable
except through the trusted proxy — which is the case on Render, Railway and Fly. **If you ever expose
the container directly**, set `TRUST_PROXY_HEADERS=false` and pin `FORWARDED_ALLOW_IPS` to the
specific upstream address, or the header becomes a trivial rate-limit bypass.

Malformed and over-long header values are rejected rather than trusted: they fall back to the socket
peer, so a client cannot poison a bucket key or inject arbitrary text into structured logs.

---

## 4. CORS

```bash
CORS_ORIGINS=["https://shop.blackhouse.example","http://localhost:5173"]
```

Accepts a JSON array **or** a comma-separated list (`https://a.com,https://b.com`).

⚠ Wildcards are rejected in `staging`/`production` because the API sends credentials
(`allow_credentials=True`) — `Access-Control-Allow-Origin: *` with credentials is invalid per
spec and browsers refuse it.

**You may not need this at all.** When the storefront is served by the nginx container (or the
Vite dev proxy), the browser sees one origin and CORS never applies. It matters only when the
frontend and API are on genuinely different hosts — e.g. the SPA on Vercel and the API on Render.

---

## 5. Authentication

| Variable | Default | Notes |
|---|---|---|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Short by design; the client refreshes transparently. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Rotating and revocable, with reuse detection. |
| `JWT_ALGORITHM` | `HS256` | Symmetric — every service sharing `SECRET_KEY` can mint tokens. |

---

## 6. Payments — Razorpay

| Variable | Default | Notes |
|---|---|---|
| `RAZORPAY_KEY_ID` | *(empty)* | Empty = **mock gateway**. |
| `RAZORPAY_KEY_SECRET` | *(empty)* | Empty = **mock gateway**. |
| `RAZORPAY_WEBHOOK_SECRET` | `whsec_dev` | ⚠ Must be set whenever keys are set. |

**Mock gateway.** With both keys empty, `payment_service` simulates authorisation and
`POST /api/v1/payments/mock-capture/{order_id}` completes an order. That endpoint raises
`CONFLICT` as soon as real keys are configured, so it cannot be used to fake a payment in
production. Use it for development and CI.

**Going live:**

1. Razorpay dashboard → Settings → API Keys. Use **test mode** first; live keys only after KYC
   is approved.
2. Dashboard → Webhooks → add `https://<api-host>/api/v1/webhooks/razorpay`, copy the secret
   into `RAZORPAY_WEBHOOK_SECRET`.
3. Subscribe to: `payment.captured`, `payment.failed`, `order.paid`, `refund.processed`,
   `refund.failed`.
4. Webhooks are signature-verified and idempotent via the `webhook_events` table. **Frontend
   success is never trusted** — in live mode the gateway is re-queried server-side.
5. KYC requires your live site to publish a refund policy, privacy policy, terms and a contact
   page. See [`ROADMAP.md`](ROADMAP.md) Phase 2 — approval will be rejected without them.

---

## 7. Email — Resend

| Variable | Default | Notes |
|---|---|---|
| `EMAIL_PROVIDER` | `log` | `log` (renders + logs, sends nothing) or `resend`. |
| `EMAIL_API_KEY` | *(empty)* | ⚠ Required when provider is `resend`. |
| `EMAIL_FROM` | `orders@blackhouse.example` | ⚠ Must be on a domain verified in Resend. |
| `EMAIL_REPLY_TO` | *(same as from)* | Set to a **monitored** inbox — customer replies must reach a human. |

The provider fails fast with an actionable message if `EMAIL_API_KEY` is empty or `EMAIL_FROM`
is not an address. Sends use explicit timeouts, retry once on `429`/`5xx`, and do **not** retry
on other `4xx` (an unverified domain will never succeed on attempt two).

**A failed email never fails a request.** The failure is recorded on the `notifications` row and
`scripts/worker.py` retries it later, capped at `MAX_NOTIFICATION_ATTEMPTS`.

Deliverability requires **SPF, DKIM and DMARC** records on the sending domain — Resend gives you
the exact values. Without them, order confirmations land in spam.

`SMS_PROVIDER` and `WHATSAPP_PROVIDER` remain unconfigured by decision: the business uses manual
`wa.me` links, generated from `WHATSAPP_BUSINESS_NUMBER` (digits only, international format) and
exposed at `GET /api/v1/orders/{id}/whatsapp-link`.

---

## 8. Object storage

| Variable | Default | Notes |
|---|---|---|
| `STORAGE_PROVIDER` | `local` | `local` \| `cloudinary` \| `s3`. ⚠ `local` is not durable across deploys. |
| `STORAGE_LOCAL_PATH` | `./storage/uploads` | Written to disk, served at `/static/uploads`. |
| `STORAGE_PUBLIC_BASE_URL` | `/static/uploads` | URL prefix for local objects. |
| `IMAGE_MAX_UPLOAD_BYTES` | `8388608` | 8 MB hard cap, enforced before buffering. |
| `IMAGE_QUALITY` | `80` | Cloudinary `q_` transform value. |
| `IMAGE_MIN_WIDTH` | `800` | Below this, a primary image logs a warning (does not block). |

### Cloudinary (recommended)

```bash
STORAGE_PROVIDER=cloudinary
# One line from the dashboard's "Product Environment Settings":
CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>
STORAGE_BUCKET=products          # becomes the Cloudinary folder
```

Or the discrete form: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.
`CLOUDINARY_URL` wins if both are set.

Uploads are **signed server-side** — never expose an unsigned upload preset, or anyone can write
into your media account. Delivery URLs get `f_auto,q_80,dpr_auto,w_<n>` transforms so WebP/AVIF
negotiation and retina scaling happen at the CDN edge.

### S3-compatible

```bash
STORAGE_PROVIDER=s3
STORAGE_BUCKET=blackhouse-media
STORAGE_REGION=ap-south-1
STORAGE_ACCESS_KEY=...            # ⚠
STORAGE_SECRET_KEY=...            # ⚠
STORAGE_CDN_BASE_URL=https://cdn.blackhouse.example   # optional but recommended
STORAGE_ENDPOINT_URL=https://blr1.digitaloceanspaces.com  # only for non-AWS stores
```

Requires `pip install ".[s3]"`. Leave `STORAGE_ENDPOINT_URL` empty for AWS S3 itself; set it for
DigitalOcean Spaces, Wasabi or MinIO. Use a scoped IAM key with `PutObject`/`GetObject`/
`DeleteObject` on this bucket only — never a root credential.

### Upload validation

Independent of provider, `app/core/uploads.py` identifies format from **magic bytes**, never from
the client's `Content-Type` or filename. JPEG, PNG, WebP and AVIF are accepted; **SVG, HTML and
XML are rejected outright** because they can carry script and are served from the API's own
origin. The stored extension is derived from the detected bytes.

---

## 9. Fail-fast production guards

`app/core/config.py` raises at import time — the process refuses to boot — when
`APP_ENV=production` or `staging` and any of these hold:

| Condition | Why it is refused |
|---|---|
| `SECRET_KEY` is a known placeholder or shorter than 32 chars | Anyone with it can forge admin tokens |
| `DATABASE_URL` points at SQLite | No concurrency, replication or point-in-time recovery |
| `APP_DEBUG=true` | Leaks internals |
| `CORS_ORIGINS` contains `*` or is empty | Invalid with credentials; browsers reject it |
| `RAZORPAY_WEBHOOK_SECRET` unset | Gateway callbacks cannot be trusted |
| `STORAGE_PROVIDER=local` | Files are lost on every redeploy |

Additionally, in **any** environment: configuring Razorpay keys without a webhook secret is
refused, since signatures could not be verified.

Every problem is reported together in one message, so you fix them in a single pass rather than
discovering them one restart at a time.

---

## 10. Commerce defaults

These seed the `business_settings` table on first run. **Afterwards an admin can change them at
runtime** via `PATCH /api/v1/admin/settings` without a redeploy — the environment value is only
the initial default.

| Variable | Default | Notes |
|---|---|---|
| `WAREHOUSE_CITY` / `_STATE` / `_COUNTRY` | Bhopal / Madhya Pradesh / IN | Origin for shipping rules. |
| `DEFAULT_CURRENCY` | `INR` | Money is integer paise everywhere (`₹1,999 = 199900`). |
| `RESERVATION_TTL_MINUTES` | `30` | Unpaid prepaid orders release stock after this. |
| `PAYMENT_RETRY_COOLDOWN_SECONDS` | `120` | Minimum wait before retrying a failed payment. |
| `RETURN_WINDOW_DAYS` | `7` | From delivery. Quoted in the delivery email. |
| `LOW_STOCK_THRESHOLD` | `3` | Triggers the low-inventory notification. |
| `FREE_SHIPPING_THRESHOLD_PAISE` | *(empty)* | Empty = no free shipping. Seed sets ₹15,000 = `1500000`. |
| `DEFAULT_SHIPPING_CHARGE_PAISE` | `9900` | ₹99 fallback when no rule matches. |
| `PINCODE_MODE` | `denylist` | `denylist` = serviceable except blocked ranges; `allowlist` = only listed. Seeded rules assume `denylist`. |
| `STAFF_CAN_CANCEL_BEFORE_PACKING` | `true` | After packing, manager approval is always required. |
| `ORDER_NUMBER_PREFIX` | `BH` | e.g. `BH-1042`. |
| `RATE_LIMIT_PER_MINUTE` | `30` | Strict per-route tier (login, register, password reset). Keyed by IP + path. |
| `RATE_LIMIT_DEFAULT_PER_MINUTE` | `120` | Blanket tier applied by middleware to every other `/api/` route. Keyed by user id when authenticated, else IP. |
| `RATE_LIMIT_ENABLED` | `true` | Master kill switch. Set `false` to disable all limiting (useful during a load test). |
| `TRUST_PROXY_HEADERS` | `true` | Read the real client IP from `X-Forwarded-For`. Must stay `true` behind a PaaS proxy; set `false` if the container is directly exposed. |
| `FORWARDED_ALLOW_IPS` | `*` | Gunicorn/Uvicorn trusted-proxy allow-list. See §3. |

Prices are **GST-inclusive**; the tax component is derived per line as
`taxable = gross / (1 + gst%)`. Seeded GST is 5% (the apparel slab) and is configurable per
product and variant.

---

## 11. Frontend (`VITE_*`)

⚠ **Anything prefixed `VITE_` is inlined into the JavaScript bundle at build time and is
public.** Never put a secret here. Values that authorise actions (the Razorpay key id, tokens)
are handed out by the backend at request time.

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | Keep relative when a proxy forwards `/api` — that is the same-origin, CORS-free setup. Use an absolute URL only if the API is on another host. |
| `VITE_DEV_PROXY_TARGET` | `http://127.0.0.1:8000` | Where the dev server forwards `/api` and `/static`. Node-side only. |
| `VITE_DEV_ALLOWED_HOSTS` | *(empty)* | Comma-separated extra hosts. Empty = accept any, which is what preview tunnels need. |
| `VITE_DEV_PORT` | `5173` | |
| `VITE_BRAND_NAME` | `Black House` | |
| `VITE_BRAND_TAGLINE` | `Small-batch outerwear` | |
| `VITE_CONTACT_EMAIL` | `hello@blackhouse.example` | |
| `VITE_WHATSAPP_NUMBER` | `910000000000` | Digits only. Empty hides WhatsApp links instead of producing a broken one. |
| `VITE_SUPPORT_PHONE` | *(empty)* | |
| `VITE_GA_MEASUREMENT_ID` | *(empty)* | Reserved; not yet wired. |
| `VITE_SENTRY_DSN` | *(empty)* | Reserved; not yet wired. |
| `VITE_APP_ENV` | Vite's `MODE` | Label only — never a security guard. |

Because these are baked in at build time, **a frontend image is environment-specific**. The
Docker build accepts them as `--build-arg`; the nginx container reads `BACKEND_ORIGIN` at
*runtime* so the proxy target can still change without a rebuild.

---

## 12. Per-environment matrix

| Variable | development | staging | production |
|---|---|---|---|
| `APP_ENV` | `development` | `staging` | `production` |
| `APP_DEBUG` | `true` | `false` | `false` |
| `LOG_FORMAT` | `text` | `json` | `json` |
| `LOG_LEVEL` | `INFO` | `INFO` | `INFO` |
| `SECRET_KEY` | generated | **unique, ≥32** | **unique, ≥32** |
| `DATABASE_URL` | SQLite or local PG | managed PG | managed PG + pooler |
| `REDIS_URL` | empty | set | set |
| `CORS_ORIGINS` | localhost | staging origin | **exact production origin** |
| `RUN_INLINE_SWEEP` | `true` | `false` | `false` (worker runs it) |
| `EMAIL_PROVIDER` | `log` | `resend` | `resend` |
| `STORAGE_PROVIDER` | `local` | `cloudinary` | `cloudinary` |
| Razorpay keys | empty (mock) | **test mode** | **live mode** |
| `SENTRY_TRACES_SAMPLE_RATE` | `0` | `0.5` | `0.1` |
| `WEB_CONCURRENCY` | — | 2 | sized to plan ÷ connection cap |

---

## 13. Handling secrets

- `.env`, `.env.*` are git-ignored. The `!.env.example` negations keep the templates tracked.
- On a PaaS, set secrets in the dashboard (`sync: false` in `render.yaml`, `fly secrets set`).
  Never commit a real value, even temporarily — it stays in git history forever.
- If a secret has ever been pushed, treat it as compromised and rotate it. `git filter-repo`
  rewrites history but does not un-leak the value.
- Use a **different `SECRET_KEY` per environment**, and a scoped IAM key rather than a root
  credential for object storage.
