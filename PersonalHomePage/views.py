"""Lightweight health check endpoint for load balancers and uptime monitors.

No database queries, no template rendering — just a plain JSON 200 so
Railway/whatever can confirm the process is alive without hammering SQLite.
"""
from django.http import JsonResponse


def health_check(request):
    """Return HTTP 200 {"status": "ok"} unconditionally."""
    return JsonResponse({"status": "ok"})
