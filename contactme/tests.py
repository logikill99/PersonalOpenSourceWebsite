from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings


VALID_CONTACT = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "message": "hello from the test suite",
}


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="matt@example.com",
    DEFAULT_FROM_EMAIL="matt@example.com",
)
class ContactFormTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_valid_post_sends_email_and_redirects(self):
        response = self.client.post("/contactme/", VALID_CONTACT, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Ada Lovelace", body)
        self.assertIn("ada@example.com", body)
        self.assertIn("hello from the test suite", body)

    def test_no_contact_tables_exist(self):
        # PII policy: email-only, nothing persisted. The former
        # contactme_contact / contactme_message tables must be gone.
        tables = connection.introspection.table_names()
        self.assertNotIn("contactme_contact", tables)
        self.assertNotIn("contactme_message", tables)

    def test_email_failure_does_not_leak_exception(self):
        with patch(
            "contactme.views.send_mail",
            side_effect=OSError("smtp exploded"),
        ):
            response = self.client.post(
                "/contactme/",
                {
                    **VALID_CONTACT,
                    "message": "this should not echo smtp errors",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"smtp exploded", response.content)
        self.assertContains(response, "was not delivered")
        # The visitor's message must survive into the re-rendered form so a
        # retry does not lose it.
        self.assertContains(response, "this should not echo smtp errors")

    def test_zero_accepted_messages_is_a_delivery_failure(self):
        # send_mail can return 0 without raising (e.g. the SMTP backend with
        # an empty recipient list when EMAIL_HOST_USER is blank). That must
        # surface as the failure path, not the success redirect.
        with patch("contactme.views.send_mail", return_value=0):
            response = self.client.post(
                "/contactme/",
                {
                    **VALID_CONTACT,
                    "message": "zero accepted must not look sent",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "was not delivered")
        # Visitor input survives the re-render for retry.
        self.assertContains(response, "zero accepted must not look sent")

    def test_rate_limit_blocks_burst_posts(self):
        for _ in range(3):
            self.client.post("/contactme/", VALID_CONTACT)
        response = self.client.post("/contactme/", VALID_CONTACT)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many messages")
        self.assertEqual(len(mail.outbox), 3)

    def test_invalid_posts_do_not_consume_rate_limit(self):
        for _ in range(4):
            self.client.post("/contactme/", {"first_name": "Ada"})
        response = self.client.post("/contactme/", VALID_CONTACT, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_honeypot_discards_bot_post(self):
        response = self.client.post(
            "/contactme/",
            {
                **VALID_CONTACT,
                "website": "https://spam.example",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_oversized_message_rejected(self):
        response = self.client.post(
            "/contactme/",
            {**VALID_CONTACT, "message": "x" * 5001},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_header_injection_in_email_field_rejected(self):
        response = self.client.post(
            "/contactme/",
            {**VALID_CONTACT, "email": "ada@example.com\nBcc: spam@evil.example"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="matt@example.com",
    DEFAULT_FROM_EMAIL="matt@example.com",
)
class ContactCsrfTests(TestCase):
    """CSRF was entirely unverified by the suite: every other test uses the
    default test client, which disables CSRF checks. These use
    enforce_csrf_checks=True so a regression that drops CsrfViewMiddleware,
    marks the view csrf_exempt, or loosens CSRF_TRUSTED_ORIGINS is caught."""

    def setUp(self):
        from django.test import Client

        cache.clear()
        self.client = Client(enforce_csrf_checks=True)

    def _token(self):
        return self.client.get("/contactme/").cookies["csrftoken"].value

    def test_valid_token_is_accepted(self):
        token = self._token()
        response = self.client.post(
            "/contactme/", {**VALID_CONTACT, "csrfmiddlewaretoken": token}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_missing_token_is_rejected(self):
        self._token()
        response = self.client.post("/contactme/", VALID_CONTACT)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_forged_token_is_rejected(self):
        self._token()
        response = self.client.post(
            "/contactme/", {**VALID_CONTACT, "csrfmiddlewaretoken": "A" * 64}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_token_without_cookie_is_rejected(self):
        token = self._token()
        self.client.cookies.clear()
        response = self.client.post(
            "/contactme/", {**VALID_CONTACT, "csrfmiddlewaretoken": token}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_cross_origin_referer_is_rejected_over_https(self):
        token = self._token()
        response = self.client.post(
            "/contactme/",
            {**VALID_CONTACT, "csrfmiddlewaretoken": token},
            secure=True,
            HTTP_REFERER="https://evil.example/x",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_still_requires_csrf(self):
        """The honeypot short-circuit sits inside the view, so it must not be
        reachable without a token."""
        self._token()
        response = self.client.post(
            "/contactme/", {**VALID_CONTACT, "website": "https://spam.example"}
        )
        self.assertEqual(response.status_code, 403)
