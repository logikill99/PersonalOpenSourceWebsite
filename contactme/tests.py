from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from contactme.models import Contact, Message


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

    def test_valid_post_saves_and_redirects(self):
        response = self.client.post("/contactme/", VALID_CONTACT, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

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
        self.assertNotIn(b"Error:", response.content)
        self.assertContains(response, "email delivery failed")
        self.assertEqual(Contact.objects.count(), 1)

    def test_rate_limit_blocks_burst_posts(self):
        payload = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "message": "burst",
        }
        for _ in range(3):
            self.client.post("/contactme/", payload)
        response = self.client.post("/contactme/", payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many messages")
        self.assertEqual(Message.objects.count(), 3)

    def test_invalid_posts_do_not_consume_rate_limit(self):
        for _ in range(4):
            self.client.post("/contactme/", {"first_name": "Ada"})
        response = self.client.post("/contactme/", VALID_CONTACT, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 1)

    def test_honeypot_discards_bot_post(self):
        response = self.client.post(
            "/contactme/",
            {
                "first_name": "Bot",
                "last_name": "McSpam",
                "email": "bot@example.com",
                "message": "buy cheap pills",
                "website": "https://spam.example",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Contact.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
