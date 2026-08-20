import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from PersonalHomePage import settings as project_settings


class HealthCheckTests(TestCase):
    def test_health_ok(self):
        for path in ("/health/", "/healthcheck/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": "ok"})
                self.assertIn("application/json", response["Content-Type"])

    def test_health_does_not_query_db(self):
        with self.assertNumQueries(0):
            response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)


class SettingsHelperTests(SimpleTestCase):
    def test_env_bool_truthy_and_falsey(self):
        cases = {
            "1": True,
            "true": True,
            "YES": True,
            "On": True,
            "0": False,
            "false": False,
            "no": False,
            "off": False,
            "False": False,
            "": False,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {"UNIT_BOOL": raw}, clear=False):
                    self.assertEqual(project_settings.env_bool("UNIT_BOOL"), expected)

    def test_env_bool_unset_uses_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("UNIT_BOOL", None)
            self.assertTrue(project_settings.env_bool("UNIT_BOOL", default=True))
            self.assertFalse(project_settings.env_bool("UNIT_BOOL", default=False))

    def test_env_list_splits_and_strips(self):
        with patch.dict(os.environ, {"UNIT_LIST": "mslevin.dev, www.mslevin.dev,,"}):
            self.assertEqual(
                project_settings.env_list("UNIT_LIST"),
                ["mslevin.dev", "www.mslevin.dev"],
            )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("UNIT_LIST", None)
            self.assertEqual(
                project_settings.env_list("UNIT_LIST", default=["fallback"]),
                ["fallback"],
            )


class SettingsFailClosedTests(SimpleTestCase):
    def test_secret_key_required_even_when_debug_true(self):
        repo = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        env.pop("SECRET_KEY", None)
        env["DEBUG"] = "True"
        env["ALLOWED_HOSTS"] = "localhost"
        env["PYTHONPATH"] = str(repo)
        result = subprocess.run(
            [sys.executable, "-c", "import PersonalHomePage.settings"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY", result.stderr)


class EmailBackendOverrideTests(SimpleTestCase):
    """Regression: EMAIL_BACKEND was assigned from env, then unconditionally
    overwritten to SMTP further down settings.py, so the env override never
    took effect."""

    def _backend_with_env(self, extra_env):
        repo = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        env.update(
            {
                "SECRET_KEY": "unit-test-key",
                "ALLOWED_HOSTS": "localhost",
                "PYTHONPATH": str(repo),
                **extra_env,
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import PersonalHomePage.settings as s; print(s.EMAIL_BACKEND)",
            ],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def test_env_override_wins(self):
        backend = self._backend_with_env(
            {"EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend"}
        )
        self.assertEqual(backend, "django.core.mail.backends.console.EmailBackend")

    def test_default_is_smtp(self):
        env = {"EMAIL_BACKEND": ""}
        backend = self._backend_with_env(env)
        self.assertEqual(backend, "django.core.mail.backends.smtp.EmailBackend")


class RateLimitClientIPTests(TestCase):
    """The limiter key must not be spoofable via X-Forwarded-For."""

    def _request(self, remote="9.9.9.9", xff=None):
        from django.test import RequestFactory

        extra = {"REMOTE_ADDR": remote}
        if xff is not None:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        return RequestFactory().get("/", **extra)

    def test_untrusted_proxy_ignores_xff_entirely(self):
        from PersonalHomePage.ratelimit import client_ip

        with self.settings(TRUST_PROXY=False):
            request = self._request(xff="1.2.3.4")
            self.assertEqual(client_ip(request), "9.9.9.9")

    def test_trusted_proxy_uses_rightmost_xff_entry(self):
        from PersonalHomePage.ratelimit import client_ip

        with self.settings(TRUST_PROXY=True):
            # Client forged "6.6.6.6"; Railway appended the real 5.5.5.5.
            request = self._request(xff="6.6.6.6, 5.5.5.5")
            self.assertEqual(client_ip(request), "5.5.5.5")

    def test_garbage_xff_falls_back_to_remote_addr(self):
        from PersonalHomePage.ratelimit import client_ip

        with self.settings(TRUST_PROXY=True):
            for garbage in ("not-an-ip", "", "1.2.3.4; DROP TABLE", "a, b"):
                request = self._request(xff=garbage)
                self.assertEqual(client_ip(request), "9.9.9.9", garbage)

    def test_spoofed_xff_cannot_bypass_contact_rate_limit(self):
        from django.core.cache import cache

        cache.clear()
        payload = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "message": "burst",
        }
        with self.settings(
            TRUST_PROXY=False,
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            EMAIL_HOST_USER="matt@example.com",
        ):
            for i in range(3):
                self.client.post(
                    "/contactme/", payload, HTTP_X_FORWARDED_FOR=f"10.0.0.{i}"
                )
            response = self.client.post(
                "/contactme/", payload, HTTP_X_FORWARDED_FOR="10.0.0.99"
            )
        self.assertContains(response, "Too many messages")

    def test_database_cache_backend_is_active(self):
        # Guards against a silent fallback to LocMemCache, which is
        # per-process and would multiply the limit by the worker count.
        from django.conf import settings as live_settings

        self.assertEqual(
            live_settings.CACHES["default"]["BACKEND"],
            "django.core.cache.backends.db.DatabaseCache",
        )


class SecurityHeaderTests(TestCase):
    """Response headers every page must carry, DEBUG or not."""

    def test_baseline_headers_on_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(
            response["Referrer-Policy"], "strict-origin-when-cross-origin"
        )

    def test_csp_header_present_and_sane(self):
        response = self.client.get("/")
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("https://cdn.jsdelivr.net", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("form-action 'self'", csp)
        # Enforced, not report-only.
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)
        # The primary XSS hole CSP closes here: no inline script allowed.
        self.assertNotIn("unsafe-inline", csp)

    def test_session_cookie_flags(self):
        from django.conf import settings as live_settings

        self.assertTrue(live_settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(live_settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(live_settings.CSRF_COOKIE_SAMESITE, "Lax")


class AdminAccessMiddlewareTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_admin_open_when_allowlist_unset(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def test_allowlisted_ip_gets_admin(self):
        with self.settings(ADMIN_IP_ALLOWLIST=["127.0.0.1", "10.0.0.0/8"]):
            response = self.client.get("/admin/login/")
            self.assertEqual(response.status_code, 200)
            response = self.client.get("/admin/login/", REMOTE_ADDR="10.1.2.3")
            self.assertEqual(response.status_code, 200)

    def test_non_allowlisted_ip_gets_404(self):
        with self.settings(ADMIN_IP_ALLOWLIST=["203.0.113.7"]):
            response = self.client.get("/admin/login/")
            self.assertEqual(response.status_code, 404)
            # Non-admin pages unaffected.
            self.assertEqual(self.client.get("/").status_code, 200)

    def test_spoofed_xff_does_not_grant_admin_access(self):
        with self.settings(
            ADMIN_IP_ALLOWLIST=["203.0.113.7"], TRUST_PROXY=False
        ):
            response = self.client.get(
                "/admin/login/", HTTP_X_FORWARDED_FOR="203.0.113.7"
            )
            self.assertEqual(response.status_code, 404)

    def test_admin_login_posts_rate_limited(self):
        for _ in range(3):
            self.client.post(
                "/admin/login/", {"username": "x", "password": "y"}
            )
        response = self.client.post(
            "/admin/login/", {"username": "x", "password": "y"}
        )
        self.assertEqual(response.status_code, 429)

    def test_invalid_allowlist_entry_fails_fast(self):
        from django.core.exceptions import ImproperlyConfigured
        from django.test import override_settings

        from PersonalHomePage.middleware import AdminAccessMiddleware

        with override_settings(ADMIN_IP_ALLOWLIST=["not-an-ip"]):
            with self.assertRaises(ImproperlyConfigured):
                AdminAccessMiddleware(lambda r: None)


class ProxySettingsSmokeTests(SimpleTestCase):
    def test_csrf_origins_derived_from_allowed_hosts(self):
        self.assertTrue(hasattr(project_settings, "CSRF_TRUSTED_ORIGINS"))
        self.assertIsInstance(project_settings.CSRF_TRUSTED_ORIGINS, list)
