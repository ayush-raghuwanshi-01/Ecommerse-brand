"""Rate limiting for sensitive endpoints (login/register/reset).

Uses Redis when REDIS_URL is configured; otherwise an in-process TTL bucket
(single-instance dev/test). Redis is intentionally optional per architecture.
"""

import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from threading import Lock

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitedError

_redis = None
_redis_tried = False
_lock = Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


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


def rate_limit(limit: int | None = None, window_seconds: int = 60) -> Callable[[Request], None]:
    limit = limit or settings.rate_limit_per_minute

    def dependency(request: Request) -> None:
        if settings.app_env == "test":
            return  # rate limiting is infra behaviour; not exercised in unit tests
        key = f"rl:{request.client.host if request.client else 'unknown'}:{request.url.path}"
        now = time.time()
        client = _get_redis()
        if client is not None:  # pragma: no cover - infra dependent
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zadd(key, {f"{now}:{id(request)}": now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            count = pipe.execute()[2]
            if count > limit:
                raise RateLimitedError("Too many requests. Please slow down.")
            return
        with _lock:
            hits = [t for t in _buckets[key] if t > now - window_seconds]
            if len(hits) >= limit:
                _buckets[key] = hits
                raise RateLimitedError("Too many requests. Please slow down.")
            hits.append(now)
            _buckets[key] = hits

    return dependency


def reset_buckets() -> None:  # test helper
    with _lock:
        _buckets.clear()
