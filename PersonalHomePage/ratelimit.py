"""Tiny IP-keyed POST limiter shared by contact + blog comments."""

from time import monotonic

from django.core.cache import cache

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_POSTS = 3


def client_ip(request) -> str:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or "unknown"


def is_rate_limited(request, *, key_prefix: str, record: bool = False) -> bool:
    now = monotonic()
    cache_key = f"{key_prefix}:{client_ip(request)}"
    stamps = [ts for ts in (cache.get(cache_key) or []) if now - ts < _RATE_WINDOW_SECONDS]
    limited = len(stamps) >= _RATE_MAX_POSTS
    if record and not limited:
        stamps.append(now)
    cache.set(cache_key, stamps, timeout=_RATE_WINDOW_SECONDS)
    return limited
