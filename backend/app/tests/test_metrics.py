"""Prometheus metrics: label cardinality, endpoint gating, pool gauges.

The most important property under test is *bounded cardinality*. A metrics
endpoint that labels on concrete URLs mints one time series per product id and
per order number, which grows without limit and can take down the Prometheus
server. These tests assert that distinct ids collapse onto one template series.
"""

import pytest

from app.core import metrics
from app.core.config import settings

pytestmark = pytest.mark.skipif(
    not metrics.PROMETHEUS_AVAILABLE,
    reason='prometheus-client not installed (pip install ".[observability]")',
)


@pytest.fixture(autouse=True)
def _single_process(monkeypatch):
    """Force single-process collection so counter assertions are deterministic.

    In multiprocess mode counters are mmapped per pid and aggregated at scrape
    time, which is correct in production but makes exact-value assertions in a
    test process meaningless.
    """
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    yield


def _scrape(client) -> str:
    r = client.get("/metrics")
    assert r.status_code == 200
    return r.text


# ── route_label / cardinality ────────────────────────────────────────────────


def test_path_label_is_route_template_not_concrete_url(client):
    """Three different slugs must produce ONE series, not three."""
    for slug in ("linen-shirt", "cotton-kurta", "wool-shawl"):
        client.get(f"/api/v1/products/{slug}")

    body = _scrape(client)
    template = 'path="/api/v1/products/{slug}"'
    matching = [
        line for line in body.splitlines() if line.startswith("http_requests_total") and template in line
    ]
    assert matching, "expected a single template series"

    # No series may contain a concrete slug.
    for slug in ("linen-shirt", "cotton-kurta", "wool-shawl"):
        assert slug not in body, f"concrete slug {slug!r} leaked into a label"


def test_path_label_includes_api_prefix(client):
    """This FastAPI keeps the prefix in the include context, not route.path."""
    client.get("/api/v1/products")
    body = _scrape(client)
    assert 'path="/api/v1/products"' in body
    # ...and it must not be doubled.
    assert 'path="/api/v1/api/v1/products"' not in body


def test_unmatched_routes_collapse_to_one_label(client):
    """Random URLs must not mint unbounded series (cardinality attack)."""
    for i in range(5):
        client.get(f"/totally-random-{i}")

    body = _scrape(client)
    unmatched = [line for line in body.splitlines() if 'path="unmatched"' in line]
    assert unmatched, "expected unmatched bucket"
    for i in range(5):
        assert f"totally-random-{i}" not in body


def test_route_label_without_route_in_scope_is_unmatched():
    from starlette.requests import Request

    req = Request({"type": "http", "method": "GET", "path": "/x", "headers": []})
    assert metrics.route_label(req) == metrics.UNMATCHED


def test_route_label_does_not_double_prefix():
    """Forward-compatible if a future FastAPI bakes the prefix into route.path."""
    from starlette.requests import Request

    class FakeRoute:
        path = "/api/v1/products"

    req = Request(
        {"type": "http", "method": "GET", "path": "/api/v1/products", "headers": [], "route": FakeRoute()}
    )
    assert metrics.route_label(req) == "/api/v1/products"


# ── endpoint gating ──────────────────────────────────────────────────────────


def test_metrics_endpoint_serves_prometheus_text(client):
    client.get("/api/v1/products")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    # Must be a real exposition format, with our custom families present.
    assert "# TYPE http_requests_total counter" in r.text
    assert "http_request_duration_seconds_bucket" in r.text
    assert r.headers["Cache-Control"] == "no-store"


def test_metrics_hidden_from_openapi_schema(client):
    schema = client.get("/openapi.json").json()
    assert "/metrics" not in schema.get("paths", {}), (
        "operational endpoint should not be in the public API surface"
    )


def test_metrics_disabled_returns_404(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", False)
    # 404 rather than 403: do not confirm the endpoint exists to a prober.
    assert client.get("/metrics").status_code == 404


def test_metrics_token_required_when_set(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", True)
    monkeypatch.setattr(settings, "metrics_token", "s3cret-token")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"})
    assert ok.status_code == 200


def test_metrics_open_when_no_token_set(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", True)
    monkeypatch.setattr(settings, "metrics_token", "")
    assert client.get("/metrics").status_code == 200


def test_metrics_exempt_from_rate_limiting(client, monkeypatch):
    """A scrape must never be throttled, or dashboards go blind under load."""
    from app.core import ratelimit

    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_default_per_minute", 2)
    ratelimit.reset_buckets()
    try:
        codes = [client.get("/metrics").status_code for _ in range(6)]
    finally:
        ratelimit.reset_buckets()
    assert codes == [200] * 6, codes


# ── pool gauges ──────────────────────────────────────────────────────────────


def test_pool_gauge_overflow_is_never_negative(client):
    """SQLAlchemy's overflow() counts from -size; the series must read sensibly."""
    client.get("/api/v1/products")  # triggers observe_pool()
    body = _scrape(client)
    values = {}
    for line in body.splitlines():
        if line.startswith("db_pool_connections{"):
            state = line.split('state="')[1].split('"')[0]
            values[state] = float(line.rsplit(" ", 1)[1])
    assert values, "no db_pool_connections samples"
    for state, value in values.items():
        assert value >= 0, f"{state} reported {value}; gauges must not be negative"


def test_observe_pool_never_raises(monkeypatch):
    """Metrics collection must not be able to break a request."""
    import app.core.database as dbmod

    class Boom:
        pool = property(lambda self: (_ for _ in ()).throw(RuntimeError("pool exploded")))

    monkeypatch.setattr(dbmod, "engine", Boom())
    metrics.observe_pool()  # must swallow the error


def test_observe_pool_noop_without_prometheus(monkeypatch):
    monkeypatch.setattr(metrics, "PROMETHEUS_AVAILABLE", False)
    metrics.observe_pool()  # must not raise


# ── multiprocess plumbing ────────────────────────────────────────────────────


def test_is_multiprocess_reflects_env(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    assert metrics.is_multiprocess() is False
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/x")
    assert metrics.is_multiprocess() is True


def test_clear_multiproc_dir_removes_stale_files(tmp_path, monkeypatch):
    """A recycled pid must not resurrect a dead worker's counters."""
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    (tmp_path / "counter_1234.db").write_text("stale")
    (tmp_path / "keep.txt").write_text("not a metric file")
    metrics.clear_multiproc_dir()
    assert not (tmp_path / "counter_1234.db").exists()
    assert (tmp_path / "keep.txt").exists(), "only .db mmap files should be removed"


def test_clear_multiproc_dir_creates_missing_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "prom"
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(target))
    metrics.clear_multiproc_dir()
    assert target.is_dir()


def test_clear_multiproc_dir_noop_when_unset(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    metrics.clear_multiproc_dir()  # must not raise


def test_render_multiprocess_builds_fresh_registry(tmp_path, monkeypatch):
    """The collector must be constructed per scrape, not registered once."""
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    body, content_type = metrics.render()
    assert isinstance(body, bytes)
    assert content_type.startswith("text/plain")
