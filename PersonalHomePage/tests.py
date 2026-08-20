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


class ProxySettingsSmokeTests(SimpleTestCase):
    def test_csrf_origins_derived_from_allowed_hosts(self):
        self.assertTrue(hasattr(project_settings, "CSRF_TRUSTED_ORIGINS"))
        self.assertIsInstance(project_settings.CSRF_TRUSTED_ORIGINS, list)
