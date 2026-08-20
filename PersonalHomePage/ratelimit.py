"""Tiny IP-keyed POST limiter shared by contact + blog comments.

Threat model / proxy trust:

- In production the app sits behind exactly one trusted proxy (Railway's
  edge), which APPENDS the real client IP to X-Forwarded-For. Anything a
  client puts in that header itself ends up further LEFT, so only the
  rightmost entry is trustworthy. Taking the leftmost (the old behavior)
  let an attacker rotate fake IPs to bypass the limit or poison another
  visitor's bucket.
- When TRUST_PROXY is off (local dev, tests), X-Forwarded-For is entirely
  attacker-controlled noise and is ignored: REMOTE_ADDR is the socket peer.
- The rightmost entry must parse as an IP address; garbage falls back to
  REMOTE_ADDR rather than becoming an attacker-chosen cache key.

Storage: the default cache is DB-backed (see settings.CACHES), so the
counter is shared across gunicorn workers and survives worker recycling.
The read-modify-write below is not atomic; two concurrent requests can
each slip one extra timestamp in. Accepted: worst case is a couple of
extra posts per window, not a per-worker multiplication of the limit.
"""

import ipaddress
from time import time

from django.conf import settings
from django.core.cache import cache

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_POSTS = 3


def client_ip(request) -> str:
    remote = request.META.get("REMOTE_ADDR") or "unknown"
    if not getattr(settings, "TRUST_PROXY", False):
        return remote
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR") or ""
    if not forwarded:
        return remote
    candidate = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return remote


def is_rate_limited(request, *, key_prefix: str, record: bool = False) -> bool:
    now = time()
    cache_key = f"{key_prefix}:{client_ip(request)}"
    stamps = [ts for ts in (cache.get(cache_key) or []) if now - ts < _RATE_WINDOW_SECONDS]
    limited = len(stamps) >= _RATE_MAX_POSTS
    if record and not limited:
        stamps.append(now)
    cache.set(cache_key, stamps, timeout=_RATE_WINDOW_SECONDS)
    return limited
