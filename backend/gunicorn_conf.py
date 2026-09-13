"""Gunicorn production configuration.

Run with:
    gunicorn app.main:app -c gunicorn_conf.py

Worker sizing
-------------
The API is synchronous (``def`` routes), so FastAPI runs each request in
Starlette's threadpool. That means one worker handles several concurrent
requests, and the useful worker count is modest:

    workers = (2 x CPU) + 1        # classic CPU-bound formula
    capped by WEB_CONCURRENCY     # what the platform gives us

At ~1,000 concurrent visitors the bottleneck is database connections, not CPU.
Each worker opens its own SQLAlchemy pool (DB_POOL_SIZE + DB_MAX_OVERFLOW), so
total connections = workers x (pool + overflow). A managed Postgres plan usually
caps connections far below what a naive worker count would demand — see
docs/CONFIGURATION.md for the arithmetic and the pooler recommendation.

The value is read from WEB_CONCURRENCY so the platform can set it per plan
without a code change, and defaults to 3 which suits a 2-vCPU container.
"""

import multiprocessing
import os

# ── Binding ──────────────────────────────────────────────────────────────────
# PaaS providers inject a dynamic port; honour it, fall back to 8000 locally.
_port = os.environ.get("PORT", "8000")
bind = f"0.0.0.0:{_port}"

# ── Workers ──────────────────────────────────────────────────────────────────
_default_workers = (multiprocessing.cpu_count() * 2) + 1
workers = int(os.environ.get("WEB_CONCURRENCY", min(_default_workers, 4)))
worker_class = "uvicorn.workers.UvicornWorker"

# Requests are short; a worker stuck past this is wedged (a leaked DB connection
# or a hung outbound HTTP call) and should be recycled rather than block a slot.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5

# Recycle workers periodically to bound memory growth from fragmentation.
# Jittered so every worker on a replica does not restart at the same instant.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "2000"))
max_requests_jitter = 200

# ── Resilience ───────────────────────────────────────────────────────────────
# Start serving before every worker is ready, so a slow first migration does not
# look like a failed boot to the platform's health check.
preload_app = os.environ.get("GUNICORN_PRELOAD", "false").lower() == "true"

# ── Logging ──────────────────────────────────────────────────────────────────
# Everything to stdout/stderr: PaaS log aggregation expects 12-factor streams,
# and writing to a file inside an ephemeral container just loses the logs.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
# The app emits its own structured access log with request ids; Gunicorn's would
# duplicate it and lacks the correlation id.
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(L)ss'

proc_name = "blackhouse-api"

# ── Proxy headers ────────────────────────────────────────────────────────────
# On every PaaS target (Render, Railway, Fly) the container is reached only
# through the platform's load balancer, so the TCP peer is the proxy rather than
# the shopper. Uvicorn's ProxyHeadersMiddleware rewrites request.client.host
# from X-Forwarded-For and the URL scheme from X-Forwarded-Proto when the peer is
# in this allow-list. Without it every caller shares one IP, which collapses
# rate limiting into a single site-wide bucket and records our own infra as the
# actor in the audit log.
#
# "*" trusts whatever the proxy sends. That is correct here because the port is
# not internet-reachable except via the platform LB. If you ever expose the
# container directly, set FORWARDED_ALLOW_IPS to the specific upstream address
# (and TRUST_PROXY_HEADERS=false) or X-Forwarded-For becomes a rate-limit bypass.
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")

# ── Prometheus multiprocess mode ─────────────────────────────────────────────
# With several workers, prometheus_client's default in-process counters mean a
# scrape is answered by whichever worker accepts it - so metrics undercount by
# the worker count and jump between scrapes. Setting this directory makes the
# client mmap counters to shared files that MultiProcessCollector aggregates
# across all live workers. See app/core/metrics.py.
#
# Must be set in the master *before* workers are forked (they inherit the env),
# and stale files must be cleared on boot: a recycled pid would otherwise
# resurrect a dead worker's counters.
_multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc")
os.environ["PROMETHEUS_MULTIPROC_DIR"] = _multiproc_dir


def on_starting(server):  # pragma: no cover - gunicorn hook
    """Runs once in the master, before any worker is forked."""
    from app.core.metrics import clear_multiproc_dir

    os.makedirs(_multiproc_dir, exist_ok=True)
    clear_multiproc_dir()
    server.log.info("prometheus multiprocess dir ready: %s", _multiproc_dir)


def when_ready(server):  # pragma: no cover - gunicorn hook
    server.log.info("blackhouse-api ready: bind=%s workers=%s timeout=%ss", bind, workers, timeout)


def post_fork(server, worker):  # pragma: no cover - gunicorn hook
    server.log.info("worker spawned pid=%s", worker.pid)
