# ─────────────────────────────────────────────────────────────────────────────
# Black House commerce backend — production image
#
#   docker build -t blackhouse-api ./backend
#   docker run -p 8000:8000 --env-file .env blackhouse-api
#
# The image runs Gunicorn supervising Uvicorn workers (see gunicorn_conf.py).
# Migrations run before the server accepts traffic, so a deploy cannot serve
# traffic against an unmigrated schema.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: build wheels ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Build deps for any package that ships only an sdist. Kept in this stage so the
# runtime image stays small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
# Extras are built into wheels here too, so the runtime stage can install them
# offline. Without the extras the image silently ships without Redis (rate
# limiting degrades to per-worker buckets) or prometheus-client (/metrics
# returns 503) - a gap that only shows up after deploy.
RUN pip wheel --wheel-dir /wheels ".[redis,observability]"


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/srv/.venv/bin:$PATH" \
    # Required for correct metrics with >1 worker; see gunicorn_conf.py.
    PROMETHEUS_MULTIPROC_DIR=/srv/metrics

WORKDIR /srv

# libpq5 only — the binary driver needs no compiler at runtime. curl is for the
# container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /srv --no-create-home app

COPY --from=builder /wheels /wheels
RUN python -m venv /srv/.venv \
    && pip install --no-index --find-links=/wheels "blackhouse-backend[redis,observability]" \
    && rm -rf /wheels

COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY gunicorn_conf.py ./

# Uploaded media when STORAGE_PROVIDER=local. In production this should be a
# mounted volume or, better, Cloudinary/S3 — local files do not survive a redeploy.
RUN mkdir -p /srv/storage/uploads /srv/metrics && chown -R app:app /srv

USER app

EXPOSE 8000

# Liveness: the process answers. Distinct from readiness below.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/healthz || exit 1

# Migrate, then serve. `alembic upgrade head` is idempotent and takes an advisory
# lock implicitly via its transaction, so concurrent replicas do not conflict.
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app -c gunicorn_conf.py"]
