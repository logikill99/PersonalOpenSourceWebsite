"""Optional IP allowlist + login rate limiting for the Django admin.

Threat model: /admin/ is public by default on a personal site. The password
is the real gate, but an exposed login form invites credential stuffing.
- ADMIN_IP_ALLOWLIST (comma-separated IPs or CIDRs) restricts /admin/ to
  known addresses; everyone else gets a 404 so the admin's existence is not
  advertised. Unset = open (accepted risk, documented in LOG.md).
- Admin login POSTs share the site-wide rate limiter (3/minute/IP) so
  password guessing is throttled even when the allowlist is off.

Invalid allowlist entries fail fast at startup (ImproperlyConfigured)
rather than silently degrading to an open admin.
"""

import ipaddress

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, HttpResponse

from PersonalHomePage.ratelimit import client_ip, is_rate_limited


def _parse_allowlist(entries):
    networks = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            raise ImproperlyConfigured(
                f'ADMIN_IP_ALLOWLIST entry {entry!r} is not a valid IP or CIDR.'
            )
    return networks


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

    def _allowed(self, request, networks) -> bool:
        try:
            ip = ipaddress.ip_address(client_ip(request))
        except ValueError:
            return False
        return any(ip in network for network in networks)

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            networks = self.networks()
            if networks and not self._allowed(request, networks):
                raise Http404
            if request.method == 'POST' and request.path == '/admin/login/':
                if is_rate_limited(request, key_prefix='admin-login', record=True):
                    return HttpResponse(
                        'Too many login attempts. Try again in a minute.',
                        status=429,
                        content_type='text/plain',
                    )
        return self.get_response(request)
