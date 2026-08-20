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
            # NB: "" is covered by test_env_bool_blank_uses_default_not_false —
            # blank means "use the default", which here happens to be False.
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {"UNIT_BOOL": raw}, clear=False):
                    self.assertEqual(project_settings.env_bool("UNIT_BOOL"), expected)

    def test_env_bool_blank_uses_default_not_false(self):
        """Regression: .env.example documents `TRUST_PROXY=` / `SECURE_SSL_REDIRECT=`
        / `SECURE_HSTS_PRELOAD=` as "blank means the default", and Railway stores
        empty strings for untouched vars. Treating "" as False turned those into
        opt-outs and made entrypoint.sh's `check --deploy --fail-level WARNING`
        release gate refuse to boot the image."""
        for raw in ("", "   ", "\t"):
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {"UNIT_BOOL": raw}, clear=False):
                    self.assertTrue(project_settings.env_bool("UNIT_BOOL", default=True))
                    self.assertFalse(project_settings.env_bool("UNIT_BOOL", default=False))

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


class DeployGateTests(SimpleTestCase):
    """entrypoint.sh gates the boot on `check --deploy --fail-level WARNING`, so
    any env shape that silently flips a security setting off becomes a
    crashloop. These run the real check in a subprocess against a prod-like env."""

    def _check_deploy(self, extra_env):
        repo = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        for key in ("DJANGO_TEST", "DEBUG", "TRUST_PROXY", "SECURE_SSL_REDIRECT",
                    "SECURE_HSTS_PRELOAD"):
            env.pop(key, None)
        env.update(
            {
                # >=50 chars and varied, or check --deploy raises W009 on its own.
                "SECRET_KEY": "x7Qvkd9wPzR3mNuT8bLfHjA2sYcEgVnXpQ4tZrWmKdBhJyGa6uCiSo",
                "ALLOWED_HOSTS": "mslevin.dev",
                "DEBUG": "False",
                "PYTHONPATH": str(repo),
                **extra_env,
            }
        )
        return subprocess.run(
            [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
            cwd=repo, env=env, capture_output=True, text=True, check=False,
        )

    def test_clean_prod_env_passes(self):
        result = self._check_deploy({})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_blank_security_env_vars_still_pass(self):
        """Regression: `.env.example` documents these as blank-for-default and
        Railway stores empty strings, but env_bool read "" as False, so
        SECURE_SSL_REDIRECT/HSTS_PRELOAD went off and the gate refused to boot
        (W008 + W021)."""
        result = self._check_deploy(
            {"TRUST_PROXY": "", "SECURE_SSL_REDIRECT": "", "SECURE_HSTS_PRELOAD": ""}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_gate_still_rejects_a_genuinely_insecure_env(self):
        """The gate must not have been softened into uselessness."""
        result = self._check_deploy({"SECURE_SSL_REDIRECT": "False"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("W008", result.stdout + result.stderr)

    def test_gate_catches_django_test_flag_leaking_into_prod(self):
        result = self._check_deploy({"DJANGO_TEST": "1"})
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        for warning in ("W008", "W012", "W016"):
            self.assertIn(warning, combined)


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

    def test_untrusted_peer_xff_ignored_for_trust_sensitive_calls(self):
        from PersonalHomePage.ratelimit import client_ip

        with self.settings(TRUST_PROXY=True, TRUSTED_PROXY_IPS=["192.0.2.0/24"]):
            request = self._request(remote="198.51.100.9", xff="203.0.113.7")
            # The limiter stays permissive (over-restricting it is a self-DoS)...
            self.assertEqual(client_ip(request), "203.0.113.7")
            # ...but an access-control caller refuses the header outright.
            self.assertEqual(
                client_ip(request, require_trusted_peer=True), "198.51.100.9"
            )

    def test_default_trusted_proxies_cover_private_peers(self):
        from PersonalHomePage.ratelimit import client_ip

        with self.settings(TRUST_PROXY=True, TRUSTED_PROXY_IPS=[]):
            private_peer = self._request(remote="172.17.0.1", xff="1.1.1.1, 203.0.113.7")
            self.assertEqual(
                client_ip(private_peer, require_trusted_peer=True), "203.0.113.7"
            )
            public_peer = self._request(remote="198.51.100.9", xff="203.0.113.7")
            self.assertEqual(
                client_ip(public_peer, require_trusted_peer=True), "198.51.100.9"
            )

    def test_invalid_trusted_proxy_entry_fails_fast(self):
        from django.core.exceptions import ImproperlyConfigured

        from PersonalHomePage.ratelimit import trusted_proxy_networks

        with self.settings(TRUSTED_PROXY_IPS=["banana"]):
            with self.assertRaises(ImproperlyConfigured):
                trusted_proxy_networks()

    def test_blocked_requests_do_not_write_to_the_cache(self):
        """An already-throttled flood should not cost one SQLite cache write
        per request."""
        from django.core.cache import cache
        from django.test import RequestFactory

        from PersonalHomePage.ratelimit import is_rate_limited

        cache.clear()
        request = RequestFactory().post("/", REMOTE_ADDR="9.9.9.9")
        for _ in range(3):
            self.assertFalse(is_rate_limited(request, key_prefix="unit", record=True))
        stored = cache.get("unit:9.9.9.9")
        self.assertEqual(len(stored), 3)
        for _ in range(5):
            self.assertTrue(is_rate_limited(request, key_prefix="unit", record=True))
        self.assertEqual(cache.get("unit:9.9.9.9"), stored)

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

    def test_spoofed_xff_does_not_grant_admin_access_under_trust_proxy(self):
        """Regression: production runs TRUST_PROXY=True (settings.py derives it
        from `not DEBUG`), and the old test only asserted safety with it off —
        a configuration production never uses. With TRUST_PROXY on and an
        untrusted socket peer, a single `X-Forwarded-For: <allowlisted ip>`
        header used to turn the allowlist off entirely."""
        with self.settings(
            ADMIN_IP_ALLOWLIST=["203.0.113.7"],
            TRUST_PROXY=True,
            TRUSTED_PROXY_IPS=["192.0.2.10"],  # our peer is 198.51.100.9, not this
        ):
            for spoof in ("203.0.113.7", "1.1.1.1, 203.0.113.7", "203.0.113.7, 203.0.113.7"):
                with self.subTest(xff=spoof):
                    response = self.client.get(
                        "/admin/login/",
                        REMOTE_ADDR="198.51.100.9",
                        HTTP_X_FORWARDED_FOR=spoof,
                    )
                    self.assertEqual(response.status_code, 404)

    def test_trusted_proxy_peer_may_still_vouch_for_admin_access(self):
        """The fix must not break the real deployment: when the socket peer IS
        the configured edge, its rightmost X-Forwarded-For entry still decides."""
        with self.settings(
            ADMIN_IP_ALLOWLIST=["203.0.113.7"],
            TRUST_PROXY=True,
            TRUSTED_PROXY_IPS=["192.0.2.0/24"],
        ):
            allowed = self.client.get(
                "/admin/login/",
                REMOTE_ADDR="192.0.2.10",
                HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.7",
            )
            self.assertEqual(allowed.status_code, 200)
            # ...and a client forging an entry to the LEFT of the real one
            # still loses, because only the rightmost entry is read.
            denied = self.client.get(
                "/admin/login/",
                REMOTE_ADDR="192.0.2.10",
                HTTP_X_FORWARDED_FOR="203.0.113.7, 8.8.8.8",
            )
            self.assertEqual(denied.status_code, 404)

    def test_bare_admin_path_is_404_when_not_allowlisted(self):
        """`/admin` (no trailing slash) must not 301 to `/admin/`: that
        confirms the admin exists to a client the allowlist is hiding it from."""
        with self.settings(ADMIN_IP_ALLOWLIST=["203.0.113.7"]):
            self.assertEqual(self.client.get("/admin").status_code, 404)
        # Without an allowlist it behaves normally (CommonMiddleware 301).
        self.assertEqual(self.client.get("/admin").status_code, 301)

    def test_admin_responses_carry_noindex(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_robots_txt_does_not_advertise_admin(self):
        """robots.txt naming /admin/ contradicted the middleware's stated goal
        of not advertising the admin's existence."""
        body = self.client.get("/robots.txt").content.decode()
        self.assertNotIn("/admin", body)

    def test_admin_login_posts_rate_limited(self):
        for _ in range(3):
            self.client.post(
                "/admin/login/", {"username": "x", "password": "y"}
            )
        response = self.client.post(
            "/admin/login/", {"username": "x", "password": "y"}
        )
        self.assertEqual(response.status_code, 429)

    def test_successful_admin_logins_do_not_consume_the_limit(self):
        """Only failed logins are counted, so the owner cannot lock themselves
        out by signing in a few times inside one minute."""
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_superuser(
            username="owner", email="o@example.com", password="Correct-Horse-9!"
        )
        for _ in range(4):
            response = self.client.post(
                "/admin/login/",
                {"username": "owner", "password": "Correct-Horse-9!", "next": "/admin/"},
            )
            self.assertEqual(response.status_code, 302)
            self.client.logout()

    def test_failed_admin_logins_still_throttle(self):
        for _ in range(3):
            self.client.post("/admin/login/", {"username": "owner", "password": "nope"})
        response = self.client.post(
            "/admin/login/", {"username": "owner", "password": "nope"}
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
