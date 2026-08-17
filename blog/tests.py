from django.core.cache import cache
from django.test import TestCase

from blog.models import Category, Comment, Post


class BlogViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.post = Post.objects.create(title="Hello", body="<h3>Idea</h3> body")
        self.post.categories.add(Category.objects.create(name="project"))

    def test_missing_post_is_404(self):
        response = self.client.get("/blog/post/99999/")
        self.assertEqual(response.status_code, 404)

    def test_index_strips_html_from_excerpt(self):
        response = self.client.get("/blog/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Idea")
        self.assertNotContains(response, "<h3>Idea</h3>")

    def test_comment_honeypot_discards(self):
        response = self.client.post(
            f"/blog/post/{self.post.pk}/",
            {"author": "Bot", "body": "spam", "website": "https://spam.example"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 0)

    def test_comment_rate_limit_after_valid_posts(self):
        for _ in range(3):
            self.client.post(
                f"/blog/post/{self.post.pk}/",
                {"author": "Ada", "body": "hi"},
            )
        response = self.client.post(
            f"/blog/post/{self.post.pk}/",
            {"author": "Ada", "body": "still going"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many comments")
        self.assertEqual(Comment.objects.count(), 3)
