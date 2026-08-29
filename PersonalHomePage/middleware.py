"""Optional IP allowlist + login rate limiting for the Django admin.

Threat model: /admin/ is public by default on a personal site. The password
is the real gate, but an exposed login form invites credential stuffing.
- ADMIN_IP_ALLOWLIST (comma-separated IPs or CIDRs) restricts /admin/ to
  known addresses; everyone else gets a 404 so the admin's existence is not
  advertised. Unset = open (accepted risk, documented in LOG.md).
- Admin login POSTs share the site-wide rate limiter (3/minute/IP) so
  password guessing is throttled even when the allowlist is off. Only
  FAILED logins are counted, so Matt cannot lock himself out by signing in
  a few times in a minute.
- The allowlist is an access-control decision, so the client IP behind it
  is resolved with require_trusted_peer=True: X-Forwarded-For is believed
  only when the socket peer is a configured proxy (TRUSTED_PROXY_IPS).
  Without that, a single `X-Forwarded-For: <allowlisted ip>` header from
  anyone who can reach the port turns the allowlist off.
- Admin responses carry X-Robots-Tag: noindex so crawlers stay out without
  robots.txt having to name the path.

Invalid allowlist entries fail fast at startup (ImproperlyConfigured)
rather than silently degrading to an open admin.
"""

import ipaddress

from django.conf import settings
from django.http import Http404, HttpResponse

from PersonalHomePage.ratelimit import client_ip, is_rate_limited, parse_networks

ADMIN_PREFIX = '/admin/'
ADMIN_LOGIN_PATH = '/admin/login/'


def _parse_allowlist(entries):
    return parse_networks(entries, setting_name='ADMIN_IP_ALLOWLIST')


class AdminAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Validate at boot so a typo'd allowlist refuses to start instead of
        # silently leaving the admin open (or locking Matt out mid-flight).
        self._cached_entries = tuple(getattr(settings, 'ADMIN_IP_ALLOWLIST', []))
        self._networks = _parse_allowlist(self._cached_entries)

    def networks(self):
        # Re-read per request so override_settings (tests) is honored; the
        # tuple compare makes the steady-state cost a no-op.
        entries = tuple(getattr(settings, 'ADMIN_IP_ALLOWLIST', []))
        if entries != self._cached_entries:
            self._networks = _parse_allowlist(entries)
            self._cached_entries = entries
        return self._networks

    @staticmethod
    def _is_admin_path(path: str) -> bool:
        # `/admin` without the slash must be covered too: CommonMiddleware
        # would otherwise 301 it to `/admin/` and confirm the admin exists
        # to a client the allowlist is supposed to be hiding it from.
        return path == ADMIN_PREFIX.rstrip('/') or path.startswith(ADMIN_PREFIX)

    def _allowed(self, request, networks) -> bool:
        try:
            ip = ipaddress.ip_address(client_ip(request, require_trusted_peer=True))
        except ValueError:
            return False
        return any(ip in network for network in networks)

    def __call__(self, request):
        if not self._is_admin_path(request.path):
            return self.get_response(request)

        networks = self.networks()
        if networks and not self._allowed(request, networks):
            raise Http404

        is_login_post = request.method == 'POST' and request.path == ADMIN_LOGIN_PATH
        if is_login_post and is_rate_limited(request, key_prefix='admin-login'):
            return self._throttled()

        response = self.get_response(request)

        # Count the attempt only if it failed. Django's admin answers a
        # successful login with a redirect and re-renders the form (200) on
        # bad credentials, so this throttles guessing without throttling
        # the owner's own successful sign-ins.
        if is_login_post and response.status_code not in (301, 302):
            is_rate_limited(request, key_prefix='admin-login', record=True)

        response.headers.setdefault('X-Robots-Tag', 'noindex, nofollow')
        return response

    @staticmethod
    def _throttled():
        response = HttpResponse(
            'Too many login attempts. Try again in a minute.',
            status=429,
            content_type='text/plain',
        )
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response
