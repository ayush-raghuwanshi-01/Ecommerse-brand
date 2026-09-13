"""Rate limiting + client-IP resolution.

The suite-wide default is ``APP_ENV=test``, which disables limiting so that
unrelated tests do not become order-dependent. Every test here therefore opts
back in explicitly via ``limited`` and resets the in-process buckets around
itself.
"""

import pytest

from app.core import ratelimit
from app.core.config import settings
from app.core.net import client_ip
from app.core.security import create_access_token

# A public, cheap endpoint that needs no auth and no seeded rows.
PROBE = "/api/v1/products"


@pytest.fixture(autouse=True)
def _reset_buckets():
    ratelimit.reset_buckets()
    yield
    ratelimit.reset_buckets()


@pytest.fixture()
def limited(monkeypatch):
    """Turn limiting on and give the global tier a tiny budget (3/min)."""
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_default_per_minute", 3)
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    return settings


def _mk_request(headers=None, client_host="203.0.113.9"):
    """Build a bare Request for unit-testing client_ip without a live server."""
    from starlette.datastructures import Headers
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": Headers(headers or {}).raw,
        "client": (client_host, 5555) if client_host else None,
    }
    return Request(scope)


# ── client_ip ────────────────────────────────────────────────────────────────


def test_client_ip_prefers_x_forwarded_for_when_trusted(limited):
    req = _mk_request({"X-Forwarded-For": "198.51.100.7, 10.0.0.1"})
    # Leftmost is the original client; 10.0.0.1 is the proxy it came through.
    assert client_ip(req) == "198.51.100.7"


def test_client_ip_ignores_xff_when_proxy_trust_disabled(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    req = _mk_request({"X-Forwarded-For": "198.51.100.7"}, client_host="203.0.113.9")
    assert client_ip(req) == "203.0.113.9"


def test_client_ip_rejects_malformed_xff(limited):
    req = _mk_request({"X-Forwarded-For": "not-an-ip"}, client_host="203.0.113.9")
    assert client_ip(req) == "203.0.113.9"


def test_client_ip_rejects_absurdly_long_xff(limited):
    # A 10k-char header must not become a 10k-char dict key / log field.
    req = _mk_request({"X-Forwarded-For": "9" * 10_000}, client_host="203.0.113.9")
    ip = client_ip(req)
    assert len(ip) <= 45
    assert ip == "203.0.113.9"


def test_client_ip_falls_back_to_x_real_ip(limited):
    req = _mk_request({"X-Real-IP": "198.51.100.22"}, client_host="10.0.0.1")
    assert client_ip(req) == "198.51.100.22"


def test_client_ip_accepts_ipv6(limited):
    req = _mk_request({"X-Forwarded-For": "2001:db8::1"})
    assert client_ip(req) == "2001:db8::1"


def test_client_ip_unknown_when_no_peer_and_no_headers(limited):
    req = _mk_request({}, client_host=None)
    assert client_ip(req) == "unknown"


# ── global middleware limit ──────────────────────────────────────────────────


def test_global_limit_returns_429_with_retry_after(client, limited):
    codes = [client.get(PROBE).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200], codes
    assert codes[3] == 429 and codes[4] == 429

    r = client.get(PROBE)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    # Envelope must match the app-wide error shape, not an ad-hoc body.
    body = r.json()["error"]
    assert body["code"] == "RATE_LIMITED"
    assert body["details"]["retry_after"] >= 1


def test_429_still_carries_request_id_and_security_headers(client, limited):
    for _ in range(4):
        r = client.get(PROBE)
    assert r.status_code == 429
    # RateLimitMiddleware is innermost, so these outer layers still decorate it.
    assert r.headers.get("X-Request-ID")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
def test_health_probes_are_exempt(client, limited, path):
    # Polled every few seconds by the platform; throttling them would get the
    # instance marked unhealthy and killed.
    for _ in range(10):
        assert client.get(path).status_code in (200, 503)


def test_non_api_paths_are_not_limited(client, limited):
    for _ in range(10):
        assert client.get("/docs").status_code == 200


def test_separate_ips_get_separate_budgets(client, limited):
    for _ in range(3):
        assert client.get(PROBE, headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert client.get(PROBE, headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 429
    # A different shopper behind a different address is unaffected.
    assert client.get(PROBE, headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 200


# ── identity keying ──────────────────────────────────────────────────────────


def test_authenticated_traffic_keyed_by_user_not_ip(limited):
    """Two shoppers behind one NAT address must not share a budget."""
    req_a = _mk_request(
        {
            "X-Forwarded-For": "198.51.100.5",
            "Authorization": "Bearer " + create_access_token(user_id="user-a", role="customer"),
        }
    )
    req_b = _mk_request(
        {
            "X-Forwarded-For": "198.51.100.5",  # same source IP
            "Authorization": "Bearer " + create_access_token(user_id="user-b", role="customer"),
        }
    )
    assert ratelimit.identity_key(req_a) == "u:user-a"
    assert ratelimit.identity_key(req_b) == "u:user-b"
    assert ratelimit.identity_key(req_a) != ratelimit.identity_key(req_b)


def test_same_user_from_two_ips_shares_one_budget(limited):
    token = create_access_token(user_id="user-a", role="customer")
    k1 = ratelimit.identity_key(
        _mk_request({"X-Forwarded-For": "1.1.1.1", "Authorization": f"Bearer {token}"})
    )
    k2 = ratelimit.identity_key(
        _mk_request({"X-Forwarded-For": "2.2.2.2", "Authorization": f"Bearer {token}"})
    )
    assert k1 == k2 == "u:user-a"


def test_anonymous_falls_back_to_ip_key(limited):
    assert ratelimit.identity_key(_mk_request({"X-Forwarded-For": "1.1.1.1"})) == "ip:1.1.1.1"


def test_forged_or_expired_token_falls_back_to_ip(limited):
    """A bad token must never buy a *larger* budget than an anonymous caller."""
    req = _mk_request({"X-Forwarded-For": "1.1.1.1", "Authorization": "Bearer not.a.real.jwt"})
    assert ratelimit.identity_key(req) == "ip:1.1.1.1"


def test_wrong_token_type_falls_back_to_ip(limited):
    """decode_access_token rejects non-access tokens; that must not raise here."""
    import jwt as pyjwt

    refresh = pyjwt.encode(
        {"sub": "user-a", "type": "refresh"}, settings.secret_key, algorithm=settings.jwt_algorithm
    )
    req = _mk_request({"X-Forwarded-For": "1.1.1.1", "Authorization": f"Bearer {refresh}"})
    assert ratelimit.identity_key(req) == "ip:1.1.1.1"


# ── strict per-route tier ────────────────────────────────────────────────────


def test_login_keeps_its_strict_per_route_limit(client, limited):
    """/auth/login is capped at 10/min regardless of the looser global tier."""
    monkeypatch_default = settings.rate_limit_default_per_minute
    settings.rate_limit_default_per_minute = 100_000  # isolate the per-route limit
    try:
        codes = [
            client.post("/api/v1/auth/login", json={"email": "x@y.z", "password": "whatever"}).status_code
            for _ in range(12)
        ]
    finally:
        settings.rate_limit_default_per_minute = monkeypatch_default
    assert codes.count(429) >= 2, codes
    assert codes[0] != 429


def test_per_route_limit_is_keyed_per_path(client, limited):
    """Budget on /auth/login must not be spent by hitting /auth/register."""
    settings.rate_limit_default_per_minute = 100_000
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "x@y.z", "password": "whatever"})
    # register has its own bucket, so it is still allowed
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "fresh@example.com",
            "password": "Password@123",
            "full_name": "F L",
            "phone": "9876500000",
        },
    )
    assert r.status_code != 429


# ── in-process bucket bounding ───────────────────────────────────────────────


def test_buckets_are_pruned_when_over_cap(monkeypatch, limited):
    """Unbounded key growth would let a client OOM the worker."""
    monkeypatch.setattr(ratelimit, "_MAX_KEYS", 50)
    ratelimit.reset_buckets()
    now = 1_000_000.0
    # 400 keys, all long-expired (timestamps far in the past relative to `now`).
    for i in range(400):
        ratelimit._buckets[f"gl:ip:10.0.{i // 250}.{i % 250}"] = [now - 7200]
    with ratelimit._lock:
        ratelimit._prune(now)
    assert len(ratelimit._buckets) <= 50


def test_prune_keeps_recent_keys(monkeypatch, limited):
    monkeypatch.setattr(ratelimit, "_MAX_KEYS", 50)
    ratelimit.reset_buckets()
    import time as _time

    now = _time.time()
    for i in range(60):
        ratelimit._buckets[f"gl:u:user-{i}"] = [now]  # all fresh
    with ratelimit._lock:
        ratelimit._prune(now)
    # Over cap with nothing expired -> LRU eviction still brings it under.
    assert len(ratelimit._buckets) <= 50


def test_is_active_respects_kill_switch(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    assert ratelimit.is_active() is True
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    assert ratelimit.is_active() is False


def test_is_active_off_in_test_env(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    assert ratelimit.is_active() is False


def test_redis_status_reports_disabled_without_url(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "")
    assert ratelimit.redis_status() == "disabled"


def test_middleware_does_not_touch_excluded_paths_outside_api(client, limited):
    """The storefront's static asset mount must not consume API budget."""
    for _ in range(6):
        client.get("/static/uploads/does-not-exist.png")
    assert client.get(PROBE).status_code == 200
