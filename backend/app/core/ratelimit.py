"""Rate limiting.

Two tiers, deliberately:

* **Per-route (strict)** — the ``rate_limit()`` dependency, applied to
  abuse-prone endpoints: login, register, password reset. Low limits, keyed by
  client IP *and* path so one endpoint's budget cannot be spent by another.
* **Global (blanket)** — ``global_rate_limit()``, called by
  ``RateLimitMiddleware`` for every other ``/api/`` route. This is what makes a
  newly added endpoint protected by default rather than only if its author
  remembered the decorator.

Identity keying
---------------
Authenticated traffic is keyed by user id, not IP. Shoppers behind a shared
NAT (corporate offices, college hostels, mobile carriers) all present the same
source address; keying them together would throttle a whole building for one
person's refresh loop. Anonymous traffic falls back to the client IP resolved
by :mod:`app.core.net`.

Storage
-------
Redis when ``REDIS_URL`` is set (required for multi-worker/multi-replica
correctness — an in-process counter is per-worker, so the effective limit is
``limit x workers``). Otherwise an in-process sliding-window bucket, which is
correct for single-instance dev/test. The in-process path is memory-bounded:
see ``_prune``.
"""

import time
from collections import defaultdict
from collections.abc import Callable
from threading import Lock

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitedError
from app.core.logging import get_logger
from app.core.net import client_ip

log = get_logger(__name__)

_redis = None
_redis_tried = False
_lock = Lock()
_buckets: dict[str, list[float]] = defaultdict(list)

# Safety valve for the in-process fallback. Each key holds a short list of
# timestamps, so this is modest memory, but without a ceiling a determined
# client could mint unbounded keys (one per path x spoofed IP) and grow the
# process until it is OOM-killed. When exceeded we prune expired entries and,
# if still over, drop the oldest-touched keys.
_MAX_KEYS = 50_000


def _get_redis():
    global _redis, _redis_tried
    if _redis_tried:
        return _redis
    _redis_tried = True
    if settings.redis_url:
        try:
            import redis  # optional dependency

            _redis = redis.from_url(settings.redis_url, socket_timeout=1)
            _redis.ping()
        except Exception:  # pragma: no cover - infra dependent
            log.warning("rate limiting: Redis unreachable, falling back to in-process buckets")
            _redis = None
    return _redis


def redis_status() -> str:
    """Report Redis reachability for the readiness probe.

    Returns ``"disabled"`` when no URL is configured (the in-process limiter is
    then the intended behaviour, not a fault), ``"ok"``, or ``"unavailable"``.
    Never raises — a health check that throws is worse than no health check.
    """
    if not settings.redis_url:
        return "disabled"
    try:
        return "ok" if _get_redis() is not None else "unavailable"
    except Exception:  # pragma: no cover - infra dependent
        return "unavailable"


def _prune(now: float) -> None:
    """Bound in-process bucket memory. Caller must hold ``_lock``."""
    if len(_buckets) <= _MAX_KEYS:
        return
    expired = [k for k, hits in _buckets.items() if not hits or hits[-1] <= now - 3600]
    for k in expired:
        _buckets.pop(k, None)
    if len(_buckets) > _MAX_KEYS:
        # Still over: evict least-recently-active keys until back under the cap.
        by_age = sorted(_buckets.items(), key=lambda kv: kv[1][-1] if kv[1] else 0)
        for k, _ in by_age[: len(_buckets) - _MAX_KEYS]:
            _buckets.pop(k, None)
        log.warning("rate limiting: in-process buckets over cap, evicted stale keys")


def _hit(key: str, limit: int, window_seconds: int) -> None:
    """Record one request against ``key``; raise if the budget is exhausted.

    Raises :class:`RateLimitedError` carrying ``retry_after`` so callers can set
    a standards-compliant ``Retry-After`` header.
    """
    now = time.time()
    client = _get_redis()

    if client is not None:  # pragma: no cover - infra dependent
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zadd(key, {f"{now}:{id(key)}:{time.monotonic_ns()}": now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        count = pipe.execute()[2]
        if count > limit:
            raise RateLimitedError(
                "Too many requests. Please slow down.",
                details={"retry_after": window_seconds},
            )
        return

    with _lock:
        hits = [t for t in _buckets[key] if t > now - window_seconds]
        if len(hits) >= limit:
            _buckets[key] = hits
            retry_after = max(1, int(hits[0] + window_seconds - now) + 1)
            _prune(now)
            raise RateLimitedError(
                "Too many requests. Please slow down.",
                details={"retry_after": retry_after},
            )
        hits.append(now)
        _buckets[key] = hits
        _prune(now)


def is_active() -> bool:
    """Whether limiting should run at all.

    Disabled in the test suite (limiting is infrastructure behaviour that would
    only make unrelated tests flaky) and whenever ``RATE_LIMIT_ENABLED=false``.
    """
    if not settings.rate_limit_enabled:
        return False
    return settings.app_env != "test"


def identity_key(request: Request) -> str:
    """Stable per-caller key: authenticated user id, else client IP.

    The JWT is decoded but *not* verified against the database here — this runs
    in middleware on every request, and a DB round-trip per request purely to
    pick a bucket key would be a poor trade. An invalid or forged token simply
    fails to decode and falls back to IP keying, which is the safe outcome: the
    worst case is that an attacker shares the IP bucket, never that they get a
    larger budget. Signature verification still happens in the real auth
    dependency before any handler runs.
    """
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            try:
                from app.core.security import decode_access_token

                payload = decode_access_token(token)
                subject = payload.get("sub")
                if subject:
                    return f"u:{subject}"
            except Exception:
                pass  # unauthenticated / malformed -> fall through to IP keying
    return f"ip:{client_ip(request)}"


def rate_limit(limit: int | None = None, window_seconds: int = 60) -> Callable[[Request], None]:
    """Strict per-route limiter for abuse-prone endpoints.

    Keyed by IP *and* path (not by user id) on purpose: credential-stuffing and
    password-reset abuse must be throttled per source address even when the
    caller is anonymous, and an attacker with many accounts should not get a
    fresh budget per account.
    """
    limit = limit or settings.rate_limit_per_minute

    def dependency(request: Request) -> None:
        if not is_active():
            return
        _hit(f"rl:{client_ip(request)}:{request.url.path}", limit, window_seconds)

    return dependency


def global_rate_limit(request: Request) -> None:
    """Blanket limiter applied by ``RateLimitMiddleware`` to all /api/ routes."""
    if not is_active():
        return
    _hit(
        f"gl:{identity_key(request)}",
        settings.rate_limit_default_per_minute,
        60,
    )


def reset_buckets() -> None:  # test helper
    with _lock:
        _buckets.clear()
