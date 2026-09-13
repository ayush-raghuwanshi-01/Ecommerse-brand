"""FastAPI application factory: modular monolith entrypoint."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
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

    return app


app = create_app()
