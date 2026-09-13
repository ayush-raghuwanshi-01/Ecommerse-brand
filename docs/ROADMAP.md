# Black House — Production Readiness Roadmap

**Target:** deployable D2C commerce platform · ~1,000 concurrent visitors · PaaS-hosted
**Agreed stack:** Railway/Render/Fly · managed PostgreSQL · Resend email · Cloudinary images ·
manual WhatsApp (wa.me) · Razorpay + COD

Legend: `[ ]` todo · `[~]` in progress · `[x]` done and verified

---

## Phase 0 — Structure & configuration ✅ DONE

- [x] Two-folder monorepo (`frontend/`, `backend/`) with `git mv` history preserved
- [x] Build artifacts removed from git; `tsc -b` emit leak fixed at the root cause
- [x] Typed env contracts: `frontend/.env.example`, `src/vite-env.d.ts`, `backend/.env.example`
- [x] Fail-fast config validation (refuses default SECRET_KEY / SQLite / debug / wildcard CORS in prod)
- [x] Root `docker-compose.yml`, `Makefile`, `scripts/setup.sh`, `scripts/dev.sh`
- [x] Frontend `Dockerfile` + `nginx.conf` (SPA fallback, `/api` proxy, security headers)
- [x] Seed bug fixed: product images 404'd because files were never created

## Phase 1 — Security hardening 🔒 BLOCKER

- [ ] **Upload validation** — MIME allowlist + magic-byte sniffing; reject `.svg`/`.html` (stored XSS)
- [ ] **API security headers** — CSP, `nosniff`, `X-Frame-Options`, HSTS, Referrer-Policy
- [ ] **Refresh token → HttpOnly cookie** — remove from `localStorage`; add CSRF protection
- [ ] **Rate limiting** — extend from 4 auth routes to checkout, coupon, bulk-enquiry, uploads
- [ ] **SECRET_KEY** — enforce ≥32 bytes everywhere; document rotation
- [ ] Fix `F821` undefined-name reference in `app/models/order.py:122`
- [ ] Dependency audit (`pip-audit`, `npm audit`) + pinned lockfiles

## Phase 2 — Legal & trust pages ⚖️ BLOCKER (Razorpay KYC will reject without these)

- [ ] Privacy Policy · Terms & Conditions · Refund & Return Policy · Shipping Policy
- [ ] Contact page with address, email, phone, GSTIN
- [ ] Cookie/consent notice
- [ ] `frontend/public/` — `robots.txt`, `sitemap.xml`, favicon, OG share images
- [ ] Rendered server-side or prerendered so crawlers and Razorpay's reviewer see them

## Phase 3 — Transactional email (Resend) 📧 BLOCKER

- [ ] `ResendEmailProvider` implementing the existing `ChannelProvider` ABC
- [ ] HTML templates: order confirmed, payment received, payment failed, shipped, delivered,
      return approved, refund processed, password reset, COD confirmation
- [ ] Retry/backoff + delivery-status recording; never block a checkout on email failure
- [ ] Unsubscribe/compliance headers; verified sender domain

## Phase 4 — Image pipeline (Cloudinary + S3) 🖼️ BLOCKER

- [ ] `CloudinaryStorage` — signed upload, responsive transforms, WebP/AVIF auto-format
- [ ] Finish `S3Storage` — presigned direct uploads, CDN base URL, correct ACLs
- [ ] Frontend `<ProductImage>` with `srcset`/`sizes` + lazy loading + blur placeholder
- [ ] Replace seed placeholders with a real photography ingestion script

## Phase 5 — Scale to 1,000 concurrent 📈 BLOCKER (PaaS = multi-replica)

- [ ] **Sweep worker → Postgres advisory lock** — currently an in-process asyncio task; N replicas
      means N concurrent sweeps double-releasing stock
- [ ] Connection pooling for a managed pooler (Supavisor/PgBouncer): `pool_pre_ping`, sane
      `pool_size`, prepared-statement caveats
- [ ] Catalog response caching (ETag / Redis) — product + collection reads dominate traffic
- [ ] Redis-backed rate limiting verified across replicas
- [ ] Gunicorn/Uvicorn worker sizing guidance per PaaS plan
- [ ] **k6/Locust load test** proving 1,000 concurrent with p95 targets; run in CI
- [ ] Index audit on hot query paths (`products.status`, `orders.customer_id`, reservation sweep)

## Phase 6 — Observability 🔭 BLOCKER

- [ ] Sentry (backend + frontend) with release tracking and source maps
- [ ] Structured JSON logging with request/correlation IDs propagated to every log line
- [ ] `/metrics` Prometheus endpoint: request latency histogram, checkout funnel, stock levels,
      payment outcomes, sweep lag
- [ ] Alerting rules: payment failure rate, webhook 4xx/5xx, sweep lag, p95 latency, 5xx budget
- [ ] Uptime + synthetic checkout monitor

## Phase 7 — SEO & shareability 🔍

- [ ] SSR or prerender for OG tags — `Seo` currently sets `document.title` in `useEffect`, so
      WhatsApp/Facebook scrapers see nothing (critical: WhatsApp is the discovery channel)
- [ ] JSON-LD structured data: `Product`, `Offer`, `AggregateRating`, `Organization`, `BreadcrumbList`
- [ ] Canonical URLs, dynamic `sitemap.xml`, per-product OG images
- [ ] Core Web Vitals budget: the 1 MB Three.js chunk is lazy-loaded but still needs LCP/CLS review

## Phase 8 — Quality gates ✅

- [ ] Clear the 182 backend lint errors (81 E501, 42 F401, 26 UP042, 22 I001, 4 F841, 3 UP017,
      2 E741, 1 F821) and add `ruff` to CI so it cannot regress
- [ ] Frontend tests — currently **zero**: Vitest + Testing Library for cart, checkout, auth flows
- [ ] Backend coverage: 85% → 90%+, with explicit tests for the new providers
- [ ] Contract test: frontend `lib/types.ts` validated against generated OpenAPI schema
- [ ] E2E smoke test (Playwright): browse → add to cart → checkout → mock payment → order page

## Phase 9 — CI/CD & deployment 🚀

- [ ] `frontend-ci.yml` — typecheck, lint, test, build
- [ ] Backend CI — add ruff, coverage gate, migration-drift check
- [ ] PaaS deploy config: `railway.json` / `render.yaml` / `fly.toml`
- [ ] Separate web and worker processes (sweep, email dispatch) with independent scaling
- [ ] Zero-downtime migration strategy (expand → migrate → contract)
- [ ] Staging environment mirroring production, seeded from a scrubbed snapshot
- [ ] Automated Postgres backups + **tested** restore procedure + PITR
- [ ] Rollback runbook and health-check-gated deploys

## Phase 10 — Documentation 📚

- [ ] `docs/SETUP.md` — first clone to running stack, every prerequisite
- [ ] `docs/CONFIGURATION.md` — every env var, both apps, per-environment matrix
- [ ] `docs/ARCHITECTURE.md` — data model, checkout transaction, state machines, ADRs
- [ ] `docs/API.md` — endpoint reference, error taxonomy, auth, idempotency, pagination
- [ ] `docs/DEPLOYMENT.md` — PaaS walkthrough, DNS, TLS, secrets, scaling, cost
- [ ] `docs/RUNBOOK.md` — on-call: stuck payments, failed webhooks, oversell, restore from backup
- [ ] `docs/CODE_REVIEW.md` — the findings audit with severity and status
- [ ] Rewrite root + `backend/README.md` (both currently reference the deleted compose file)

## Phase 11 — Pre-launch checklist 🏁

- [ ] Razorpay KYC documents + live-mode keys + webhook registered on the production URL
- [ ] GST configuration verified with an accountant; invoice generation legal review
- [ ] Load test signed off at 2× target headroom
- [ ] Backup restore rehearsed end-to-end
- [ ] Security review: OWASP ASVS L2 pass
- [ ] Legal pages reviewed by counsel
- [ ] Domain, TLS, DNS, and email deliverability (SPF/DKIM/DMARC) verified

---

## Business inputs still needed from you

These cannot be inferred from code — they gate Phases 2, 3 and 11:

1. **Registered business name, address, GSTIN** — required on the legal pages and invoices
2. **Domain name** — for CORS, cookies, canonical URLs, sitemap, email sender
3. **Return/refund policy terms** — the code implements a 7-day window; is that the real policy?
   Who pays return shipping for each case?
4. **Shipping partners + rates** — currently manual tracking with seeded state/PIN rates
5. **Support contact** — email, phone, hours (Razorpay checks that a human is reachable)
6. **Product photography** — real images, or should the placeholder pipeline stay for now?
