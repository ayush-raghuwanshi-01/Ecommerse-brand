"""FastAPI application factory: modular monolith entrypoint."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.services import order_service

log = get_logger("main")

SWEEP_INTERVAL_SECONDS = 60


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("starting %s (env=%s)", settings.project_name, settings.app_env)

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

    task = asyncio.create_task(_sweep_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version="1.0.0",
        description=(
            "Black House commerce backend — modular monolith. "
            "India-first D2C + staff orders, GST-inclusive paise pricing, Razorpay/COD, "
            "returns, coupons, restock alerts, audit logging."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Idempotency-Key"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_str)

    if settings.storage_provider == "local":
        from pathlib import Path

        Path(settings.storage_local_path).mkdir(parents=True, exist_ok=True)
        app.mount("/static/uploads", StaticFiles(directory=settings.storage_local_path), name="uploads")

    @app.get("/healthz", tags=["meta"])
    def healthz():
        return {"status": "ok", "service": "blackhouse-backend", "version": "1.0.0"}

    return app


app = create_app()
