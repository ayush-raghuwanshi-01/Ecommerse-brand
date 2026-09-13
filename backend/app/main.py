"""FastAPI application factory: modular monolith entrypoint."""

import asyncio
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.metrics import PROMETHEUS_AVAILABLE
from app.core.metrics import render as render_metrics
from app.core.middleware import (
    MetricsMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.services import order_service

log = get_logger("main")

# Single source of truth for the version reported by /healthz, /readyz and the
# OpenAPI document. Bump on release, or read from git in CI.
APP_VERSION = "1.1.0"

SWEEP_INTERVAL_SECONDS = 60


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info(
        "starting %s (env=%s, log_format=%s, inline_sweep=%s)",
        settings.project_name,
        settings.app_env,
        settings.log_format,
        settings.run_inline_sweep,
    )

    async def _sweep_loop():
        while True:
            await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
            try:
                from app.core.database import SessionLocal

                db = SessionLocal()
                try:
                    released = order_service.sweep_expired_reservations(db)
                    db.commit()
                    if released:
                        log.info("swept %s expired reservation(s)", released)
                finally:
                    db.close()
            except asyncio.CancelledError:  # pragma: no cover
                raise
            except Exception as exc:  # pragma: no cover
                log.warning("sweep failed: %s", exc)

    # In production the standalone worker (scripts/worker.py) owns this duty and
    # RUN_INLINE_SWEEP is false, so N API replicas do not all poll the database.
    task = asyncio.create_task(_sweep_loop()) if settings.run_inline_sweep else None
    if task is None:
        log.info("inline sweep disabled — expecting the standalone worker to run it")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version=APP_VERSION,
        description=(
            "Black House commerce backend — modular monolith. "
            "India-first D2C + staff orders, GST-inclusive paise pricing, Razorpay/COD, "
            "returns, coupons, restock alerts, audit logging."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    # Middleware order matters: Starlette builds the stack so that the LAST
    # added middleware is OUTERMOST (it runs first on the way in). Reading the
    # resulting onion from outside in:
    #
    #   CORS -> RequestContext -> SecurityHeaders -> RateLimit -> router
    #
    #  * CORS outermost so even an error response carries the ACAO header and a
    #    preflight OPTIONS is answered without touching anything downstream.
    #  * RequestContext next so every request - including a CORS-rejected or
    #    rate-limited one - is timed and carries an X-Request-ID.
    #  * SecurityHeaders outside RateLimit so the 429 it generates still gets
    #    the defensive headers.
    #  * RateLimit innermost: it must not spend a caller's budget on a preflight,
    #    and anything it rejects still flows back out through the three above.
    #  * RateLimit outside Metrics so latency series reflect handler time, and
    #    throttled requests are counted separately by rate_limit_rejected_total
    #    rather than polluting the per-route latency histogram.
    #  * Metrics innermost of all: routing has resolved scope["route"] by then,
    #    which is what lets the `path` label be the route template instead of the
    #    concrete URL (see app/core/metrics.py on cardinality).
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Idempotency-Key", "X-Request-ID", "Retry-After"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_str)

    if settings.storage_provider == "local":
        from pathlib import Path

        Path(settings.storage_local_path).mkdir(parents=True, exist_ok=True)
        app.mount("/static/uploads", StaticFiles(directory=settings.storage_local_path), name="uploads")

    @app.get("/healthz", tags=["meta"])
    def healthz():
        """Liveness: the process is up and answering.

        Deliberately touches no dependencies — a database outage must not make
        the platform restart an otherwise healthy process (which would only make
        the outage worse). Use /readyz for traffic gating.
        """
        return {"status": "ok", "service": "blackhouse-backend", "version": APP_VERSION}

    @app.get("/readyz", tags=["meta"])
    def readyz():
        """Readiness: can this replica actually serve a request right now?

        Returns 503 when the database is unreachable so the load balancer stops
        sending traffic here instead of failing customer requests.
        """
        from sqlalchemy import text

        from app.core.database import SessionLocal

        checks: dict[str, str] = {}
        healthy = True
        try:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
                checks["database"] = "ok"
            finally:
                db.close()
        except Exception as exc:
            healthy = False
            checks["database"] = f"error: {type(exc).__name__}"

        # Redis is optional — degraded rate limiting is not a reason to pull a
        # replica out of rotation, so it is reported but never fails readiness.
        if settings.redis_url:
            from app.core.ratelimit import redis_status

            status = redis_status()
            checks["redis"] = status
            if status != "ok":
                log.warning("redis unavailable (%s); rate limiting falls back in-process", status)

        body = {
            "status": "ok" if healthy else "degraded",
            "service": "blackhouse-backend",
            "version": APP_VERSION,
            "environment": settings.app_env,
            "checks": checks,
        }
        return JSONResponse(status_code=200 if healthy else 503, content=body)

    @app.get("/metrics", tags=["meta"], include_in_schema=False)
    def metrics(request: Request):
        """Prometheus scrape endpoint.

        Hidden from the OpenAPI schema: it is an operational endpoint for a
        scraper, not part of the commerce API surface.

        Three failure modes are handled explicitly rather than crashing:
          * ``METRICS_ENABLED=false`` -> 404, so the endpoint does not exist as
            far as an unauthenticated prober is concerned;
          * ``prometheus-client`` not installed (it is in the ``observability``
            extra) -> 503 with an actionable message, because silently serving
            an empty 200 would look like a healthy target with no traffic;
          * ``METRICS_TOKEN`` set and not matched -> 401.
        """
        if not settings.metrics_enabled:
            return JSONResponse(
                status_code=404, content={"error": {"code": "NOT_FOUND", "message": "Not found."}}
            )

        if not PROMETHEUS_AVAILABLE:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "METRICS_UNAVAILABLE",
                        "message": (
                            "Metrics are not enabled in this build. "
                            'Install with: pip install ".[observability]"'
                        ),
                        "details": {},
                    }
                },
            )

        expected = settings.metrics_token
        if expected:
            supplied = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
            # compare_digest: a plain == leaks the token length through timing.
            if not secrets.compare_digest(supplied, expected):
                return JSONResponse(
                    status_code=401,
                    content={"error": {"code": "UNAUTHENTICATED", "message": "Invalid metrics token."}},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        body, content_type = render_metrics()
        # never-store: metrics are a point-in-time sample and must not be cached
        # by an intermediary, or a scraper would read stale counters.
        return Response(content=body, media_type=content_type, headers={"Cache-Control": "no-store"})

    return app


app = create_app()
