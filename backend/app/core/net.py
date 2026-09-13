"""Client network identity resolution.

Why this module exists
----------------------
Behind a PaaS load balancer (Render, Railway, Fly) the TCP peer of every
request is the *platform's proxy*, not the shopper. ``request.client.host``
therefore returns the same address for all traffic, which silently breaks two
things:

* **Rate limiting** — every user collapses into one bucket, so either the whole
  site starts returning 429 under normal load, or the limit is meaningless.
* **Audit logging** — we record our own infrastructure as the actor instead of
  the person who cancelled the order or approved the refund. That defeats the
  purpose of the audit trail in a return dispute.

The real client address arrives in ``X-Forwarded-For``. Taking it is only safe
when the app genuinely sits behind a trusted proxy, so it is gated behind
``TRUST_PROXY_HEADERS``.

Spoofing trade-off
------------------
``X-Forwarded-For`` is client-controlled: a direct caller can prepend any
address they like. When the app is *only* reachable through the platform
proxy, the proxy appends the true peer address and the leftmost entry is the
original client — this is the standard deployment and the default here. If you
ever expose the container directly to the internet, set
``TRUST_PROXY_HEADERS=false`` and accept the proxy-IP limitation, or put a
trusted reverse proxy in front. Do not leave it ``true`` on a directly exposed
port: rate limits become trivially evadable.
"""

import ipaddress

from fastapi import Request

from app.core.config import settings

# Longest string we are willing to treat as an address. Guards the log/rate-limit
# key from being bloated by an absurd header value.
_MAX_IP_LEN = 45  # len("0000:0000:0000:0000:0000:ffff:255.255.255.255")

UNKNOWN_IP = "unknown"

_FORWARDED_FOR = "x-forwarded-for"
_REAL_IP = "x-real-ip"


def _is_valid_ip(candidate: str) -> bool:
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return True


def client_ip(request: Request) -> str:
    """Return the best-effort real client IP for ``request``.

    Never raises and never returns ``None``: callers use the result as a
    dictionary key and a log field, so a stable ``"unknown"`` sentinel is more
    useful than an exception. A malformed header is ignored rather than
    trusted — otherwise a client could poison rate-limit buckets or inject
    arbitrary text into structured logs.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get(_FORWARDED_FOR)
        if forwarded:
            # Leftmost = original client; the rest are proxies it passed through.
            candidate = forwarded.split(",")[0].strip()[:_MAX_IP_LEN]
            if _is_valid_ip(candidate):
                return candidate
        # Some proxies set only X-Real-IP.
        real_ip = request.headers.get(_REAL_IP)
        if real_ip:
            candidate = real_ip.strip()[:_MAX_IP_LEN]
            if _is_valid_ip(candidate):
                return candidate

    if request.client and request.client.host:
        return request.client.host
    return UNKNOWN_IP
