"""HTTP security + request-context middleware.

Two middlewares live here because both must run on *every* response, including
error responses produced by exception handlers:

* ``RequestContextMiddleware`` — assigns a correlation id, times the request, and
  emits one structured access-log line. The id is returned to the client as
  ``X-Request-ID`` so a support ticket can be traced to exact log lines.
* ``SecurityHeadersMiddleware`` — the defensive headers an e-commerce origin
  must send. Nginx adds its own copy at the edge; these protect the API when it
  is reached directly (staging, internal tooling, misconfigured DNS).

Content-Security-Policy is deliberately *report-only-friendly*: the storefront
loads Razorpay's checkout script and Google Fonts, so a strict CSP that blocks
them would break payments. The policy below allows exactly those and nothing else.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.exceptions import RateLimitedError
from app.core.logging import get_logger
from app.core.net import client_ip
from app.core.ratelimit import global_rate_limit

log = get_logger("http")

REQUEST_ID_HEADER = "X-Request-ID"

# Third parties the storefront legitimately loads at runtime. If you add a
# vendor (analytics, a second payment gateway, a font host), it must be added to
# the matching directive below or the browser will block it silently.
_CSP = "; ".join(
    [
        "default-src 'self'",
        # Razorpay's checkout modal; jsDelivr is the polyfill CDN Vite may emit.
        "script-src 'self' 'unsafe-inline' https://checkout.razorpay.com https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",  # DM Sans / Fraunces
        "font-src 'self' https://fonts.gstatic.com data:",
        # Product imagery: Cloudinary (recommended), S3, or the API's own
        # /static/uploads mount served from 'self'.
        "img-src 'self' data: blob: https://res.cloudinary.com https://*.s3.*.amazonaws.com",
        # lumberjack is Razorpay's telemetry endpoint; blocking it breaks checkout.
        "connect-src 'self' https://api.razorpay.com https://lumberjack.razorpay.com",
        "frame-src https://api.razorpay.com https://checkout.razorpay.com",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
        "upgrade-insecure-requests",
    ]
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Correlation id + structured access log + slow-request warning."""

    # Requests slower than this are logged at WARNING for latency hunting.
    SLOW_REQUEST_MS = 1_500

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        # Truncate client-supplied ids so they cannot be used to bloat logs.
        request_id = request_id[:64]
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000
            log.exception(
                "unhandled error",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(elapsed_ms, 1),
                },
            )
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        # Health checks are polled constantly by the platform — do not log them.
        if request.url.path not in {"/healthz", "/readyz", "/metrics"}:
            record = log.warning if elapsed_ms > self.SLOW_REQUEST_MS else log.info
            record(
                "%s %s -> %s (%.0fms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(elapsed_ms, 1),
                    "ip": client_ip(request),
                },
            )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Defensive headers on every response, including errors."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(self)"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.headers.setdefault("Content-Security-Policy", _CSP)

        # HSTS only makes sense over TLS, and must never be sent in development
        # over plain HTTP or the browser will refuse to load the local app.
        # NB: MutableHeaders has no .pop(); delete-by-key is the supported form.
        if settings.app_env in {"production", "staging"}:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
            )
        elif "strict-transport-security" in response.headers:
            del response.headers["Strict-Transport-Security"]

        # Never let a response be cached by a shared proxy when it may carry
        # per-user data; the catalog endpoints opt back in explicitly.
        if "Authorization" in request.headers or request.cookies:
            response.headers.setdefault("Cache-Control", "no-store, private")

        return response


# Paths that must never be rate limited. Health/readiness probes are polled
# every few seconds by the platform and by the load balancer; throttling them
# would cause the instance to be marked unhealthy and killed. Metrics are
# scraped on a fixed interval for the same reason.
_RATE_LIMIT_EXEMPT = frozenset(
    {"/healthz", "/readyz", "/metrics", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Blanket rate limit across every ``/api/`` route.

    Exists because the per-route ``rate_limit()`` dependency is opt-in: with
    only the auth endpoints decorated, the other ~90 handlers had no limit at
    all, so any of them could be hammered. A default-on middleware inverts that
    — new endpoints are protected unless explicitly exempted.

    Runs innermost in the stack (see ``create_app``) so that:
      * ``SecurityHeadersMiddleware`` still decorates the 429 it returns;
      * CORS preflight ``OPTIONS`` requests are answered by ``CORSMiddleware``
        upstream and never spend a caller's budget;
      * ``RequestContextMiddleware`` has already assigned ``X-Request-ID``, so
        a throttled request is still traceable in the logs.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if path in _RATE_LIMIT_EXEMPT or not path.startswith("/api/"):
            return await call_next(request)

        try:
            global_rate_limit(request)
        except RateLimitedError as exc:
            retry_after = str(exc.details.get("retry_after", 60))
            log.warning(
                "rate limited %s %s",
                request.method,
                path,
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "method": request.method,
                    "path": path,
                    "status": 429,
                    "ip": client_ip(request),
                },
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    }
                },
            )
            # RFC 9110: tell the client how long to wait. Without it, well-behaved
            # clients retry immediately and make the congestion worse.
            response.headers["Retry-After"] = retry_after
            request_id = getattr(request.state, "request_id", None)
            if request_id:
                response.headers[REQUEST_ID_HEADER] = request_id
            return response

        return await call_next(request)
