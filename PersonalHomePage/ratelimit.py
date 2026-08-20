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
- "Rightmost is trustworthy" holds only if a proxy actually appended an
  entry. A request that reaches gunicorn WITHOUT passing through the edge
  carries whatever X-Forwarded-For the attacker typed, and its rightmost
  entry is therefore attacker-chosen. TRUSTED_PROXY_IPS closes that: the
  socket peer (REMOTE_ADDR) must itself be a known proxy before anything
  it forwards is believed. This is the same rule nginx spells
  `set_real_ip_from` and gunicorn spells `forwarded-allow-ips`.
- The rightmost entry must parse as an IP address; garbage falls back to
  REMOTE_ADDR rather than becoming an attacker-chosen cache key.

Why two strictness levels: for the *limiter*, mis-trusting a header costs
at most some extra posts, while over-restricting collapses every visitor
into one bucket (a self-DoS). For *access control* (the admin allowlist)
the trade runs the other way, so AdminAccessMiddleware calls this with
require_trusted_peer=True and fails closed. See middleware.py.

Storage: the default cache is DB-backed (see settings.CACHES), so the
counter is shared across gunicorn workers and survives worker recycling.
The read-modify-write below is not atomic; two concurrent requests can
each slip one extra timestamp in. Accepted: worst case is a couple of
extra posts per window, not a per-worker multiplication of the limit.
"""

import ipaddress
import logging
from time import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.cache import cache

logger = logging.getLogger(__name__)

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_POSTS = 3

# Peers we will believe an X-Forwarded-For from when TRUSTED_PROXY_IPS is
# not configured. A container behind a platform edge (Railway, Fly, an
# ingress controller) sees the edge on a private/loopback address; a client
# talking straight to the port from the internet does not.
_DEFAULT_TRUSTED_PROXY_IPS = (
    '127.0.0.0/8',
    '::1/128',
    '10.0.0.0/8',
    '172.16.0.0/12',
    '192.168.0.0/16',
    '100.64.0.0/10',   # CGNAT, used by several PaaS internal networks
    'fc00::/7',        # IPv6 unique local
    'fe80::/10',       # IPv6 link local
)

_trusted_cache: tuple[tuple[str, ...], tuple] | None = None


def parse_networks(entries, *, setting_name: str):
    """Parse IP/CIDR strings, failing fast on anything malformed."""
    networks = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            raise ImproperlyConfigured(
                f'{setting_name} entry {entry!r} is not a valid IP or CIDR.'
            )
    return tuple(networks)


def trusted_proxy_networks():
    """Networks whose members may vouch for a client IP via X-Forwarded-For.

    Re-read per call so override_settings works in tests; memoised on the
    raw tuple so the steady-state cost is a comparison.
    """
    global _trusted_cache
    entries = tuple(
        getattr(settings, 'TRUSTED_PROXY_IPS', None) or _DEFAULT_TRUSTED_PROXY_IPS
    )
    if _trusted_cache is None or _trusted_cache[0] != entries:
        _trusted_cache = (entries, parse_networks(entries, setting_name='TRUSTED_PROXY_IPS'))
    return _trusted_cache[1]


def _peer_is_trusted_proxy(remote: str) -> bool:
    try:
        ip = ipaddress.ip_address(remote)
    except ValueError:
        return False
    return any(ip in network for network in trusted_proxy_networks())


def client_ip(request, *, require_trusted_peer: bool = False) -> str:
    """Best-effort client IP.

    require_trusted_peer=True refuses to read X-Forwarded-For unless the
    socket peer is inside TRUSTED_PROXY_IPS, so a header alone can never
    decide an access-control question.
    """
    remote = request.META.get("REMOTE_ADDR") or "unknown"
    if not getattr(settings, "TRUST_PROXY", False):
        return remote
    if require_trusted_peer and not _peer_is_trusted_proxy(remote):
        logger.warning(
            'Ignoring X-Forwarded-For for a trust-sensitive decision: peer %s '
            'is not in TRUSTED_PROXY_IPS. Using REMOTE_ADDR instead.',
            remote,
        )
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
    # Only write when we actually add a stamp. Writing on every call (the
    # previous behavior) meant an already-blocked flood still cost one
    # SQLite cache write per request, and pointlessly extended the TTL.
    if record and not limited:
        stamps.append(now)
        cache.set(cache_key, stamps, timeout=_RATE_WINDOW_SECONDS)
    return limited
