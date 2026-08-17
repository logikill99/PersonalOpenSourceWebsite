from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import TestCase
from django.urls import reverse


class HomePageSmokeTests(TestCase):
    def test_home_renders(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Home")

    def test_static_style_resolves(self):
        path = staticfiles_storage.url("style.css")
        self.assertTrue(path.startswith("/static/"))
        self.assertIn("style.css", path)
