"""Prometheus metrics.

Design notes
------------
**Multi-worker correctness.** Gunicorn runs several Uvicorn workers, and by
default ``prometheus_client`` keeps counters in process memory — so each worker
has its own, and a scrape is answered by whichever worker accepts the
connection. The result is metrics that silently undercount by a factor of the
worker count and jump around between scrapes. Setting
``PROMETHEUS_MULTIPROC_DIR`` makes the client mmap counters to shared files, and
``MultiProcessCollector`` aggregates every live worker at scrape time.
``gunicorn_conf.py`` sets that variable and clears stale files on boot.

**Label cardinality.** ``path`` is the *route template* (``/api/v1/products/{id}``),
never the concrete URL. Using the concrete URL would create one time series per
product id, per order number — an unbounded series explosion that can take down
a Prometheus server. Requests that match no route are all bucketed as
``unmatched``, which also closes the related attack where someone requests
random URLs to mint unbounded series.

**Optional dependency.** ``prometheus-client`` lives in the ``observability``
extra. The endpoint degrades to a 503 with an actionable message rather than
crashing at import time, so the app still runs on a minimal install.
"""

import os

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

try:  # optional dependency (pip install ".[observability]")
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        multiprocess,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on installed extras
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

# Latency buckets tuned for a synchronous commerce API: most reads should be
# well under 100ms, checkout and payment calls can take seconds, and the
# Gunicorn timeout is 60s so nothing useful lives beyond that.
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)

# Sentinel label for anything that did not match a route. Keeps series bounded.
UNMATCHED = "unmatched"

if PROMETHEUS_AVAILABLE:
    http_requests_total = Counter(
        "http_requests_total",
        "HTTP requests served, by method, route template and status class.",
        ["method", "path", "status"],
    )
    http_request_duration_seconds = Histogram(
        "http_request_duration_seconds",
        "Request latency in seconds.",
        ["method", "path"],
        buckets=_LATENCY_BUCKETS,
    )
    rate_limit_rejected_total = Counter(
        "rate_limit_rejected_total",
        "Requests rejected with 429, by route template and limiting tier.",
        ["path", "tier"],
    )
    # livesum: each worker has its own SQLAlchemy pool, so summing across live
    # workers yields the real total connection count - the number that has to
    # stay under the managed Postgres plan's cap. See docs/CONFIGURATION.md.
    db_pool_connections = Gauge(
        "db_pool_connections",
        "SQLAlchemy pool state, summed across workers.",
        ["state"],
        multiprocess_mode="livesum",
    )
    unhandled_exceptions_total = Counter(
        "unhandled_exceptions_total",
        "Requests that ended in a 5xx, by route template.",
        ["path"],
    )


def route_label(request) -> str:
    """Stable, bounded ``path`` label for a request.

    Returns the *route template* rather than the concrete URL, so requesting a
    thousand different product ids produces one series, not a thousand. Requests
    matching no route collapse to ``UNMATCHED`` — otherwise random URLs would
    mint unbounded series (a cardinality attack that can take down Prometheus).

    The API prefix is re-attached because this FastAPI version resolves included
    routers lazily: ``api_router`` is mounted with ``prefix="/api/v1"``, but the
    underlying route object still reports ``path="/products"``, with the prefix
    living in the include context instead. Labelling on that alone would produce
    ``/products``, which is ambiguous and would collide if another router ever
    used the same sub-path. The guard is written so that if a future version does
    bake the prefix into ``route.path``, it is not added twice.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if not path:
        return UNMATCHED

    prefix = settings.api_v1_str
    if prefix and request.url.path.startswith(prefix) and not path.startswith(prefix):
        return prefix + path
    return path


def is_multiprocess() -> bool:
    return bool(os.environ.get("PROMETHEUS_MULTIPROC_DIR"))


def clear_multiproc_dir() -> None:
    """Remove stale mmap files from a previous run.

    Must be called once in the Gunicorn master *before* workers fork. Files left
    behind by a crashed worker are keyed by pid; a recycled pid would otherwise
    resurrect the dead process's counters and corrupt every metric.
    """
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not path or not PROMETHEUS_AVAILABLE:
        return
    try:
        os.makedirs(path, exist_ok=True)
        for entry in os.listdir(path):
            if entry.endswith(".db"):
                os.remove(os.path.join(path, entry))
        log.info("prometheus multiprocess dir cleared", extra={"path": path})
    except OSError as exc:  # pragma: no cover - depends on filesystem perms
        log.warning("could not clear PROMETHEUS_MULTIPROC_DIR: %s", exc)


def render() -> tuple[bytes, str]:
    """Return ``(body, content_type)`` for a scrape.

    Builds a *fresh* registry per call in multiprocess mode: the collector reads
    the shared mmap files at scrape time, so it must not be registered once at
    import and reused.
    """
    if not PROMETHEUS_AVAILABLE:  # pragma: no cover - depends on extras
        raise RuntimeError("prometheus_client is not installed")

    if is_multiprocess():
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST

    from prometheus_client import REGISTRY

    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def observe_pool() -> None:
    """Refresh the DB pool gauges from the live engine.

    Called on every request so each worker's mmap value stays current; with
    ``livesum`` the scrape then reports the fleet-wide total.

    ``checkedout`` approaching ``size + max_overflow`` is the single most useful
    saturation signal for this app — at ~1,000 concurrent visitors the database
    connection budget, not CPU, is the binding constraint (see gunicorn_conf.py
    and docs/CONFIGURATION.md for the workers x pool arithmetic).

    Note on ``overflow()``: SQLAlchemy's implementation is a *counter* that
    starts at ``-size`` and increments for each connection created, so it reads
    negative until the pool has filled (verified empirically: a fresh pool of
    size 5 reports ``overflow() == -5``, and ``-4`` after one connection). It is
    not "connections currently in overflow". Clamping at zero makes the series
    mean what an operator expects and what an alert rule would assume.
    """
    if not PROMETHEUS_AVAILABLE:
        return
    try:
        from app.core.database import engine

        pool = engine.pool
        db_pool_connections.labels(state="checkedout").set(pool.checkedout())
        # Not every pool class implements overflow() (e.g. StaticPool).
        raw_overflow = getattr(pool, "overflow", lambda: 0)()
        db_pool_connections.labels(state="overflow").set(max(0, raw_overflow))
        db_pool_connections.labels(state="checkedin").set(pool.checkedin())
        db_pool_connections.labels(state="size").set(pool.size())
    except Exception:  # pragma: no cover - metrics must never break a request
        log.debug("could not read pool stats", exc_info=True)


def metrics_enabled() -> bool:
    """Whether /metrics should serve data.

    Exposing counters publicly leaks traffic shape and internal route names, so
    the endpoint can be switched off entirely, or gated behind a bearer token.
    """
    return settings.metrics_enabled and PROMETHEUS_AVAILABLE
