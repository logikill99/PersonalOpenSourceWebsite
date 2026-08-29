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

    def test_new_comment_is_held_for_moderation(self):
        response = self.client.post(
            f"/blog/post/{self.post.pk}/",
            {"author": "Ada", "body": "great post"},
            follow=True,
        )
        self.assertContains(response, "awaiting moderation")
        comment = Comment.objects.get()
        self.assertFalse(comment.approved)
        # Unapproved comment must not be publicly visible.
        self.assertNotContains(response, "great post")

    def test_approved_comment_is_displayed(self):
        Comment.objects.create(
            author="Ada", body="approved words", post=self.post, approved=True
        )
        Comment.objects.create(
            author="Bot", body="held words", post=self.post, approved=False
        )
        response = self.client.get(f"/blog/post/{self.post.pk}/")
        self.assertContains(response, "approved words")
        self.assertNotContains(response, "held words")

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


class CommentCsrfTests(TestCase):
    """See ContactCsrfTests: the default test client disables CSRF, so comment
    posting had no CSRF coverage at all."""

    def setUp(self):
        from django.test import Client

        cache.clear()
        self.post = Post.objects.create(title="Hello", body="body")
        self.client = Client(enforce_csrf_checks=True)

    def _token(self):
        return self.client.get(f"/blog/post/{self.post.pk}/").cookies["csrftoken"].value

    def test_valid_token_is_accepted(self):
        token = self._token()
        response = self.client.post(
            f"/blog/post/{self.post.pk}/",
            {"author": "Ada", "body": "hi", "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 1)

    def test_missing_token_is_rejected(self):
        self._token()
        response = self.client.post(
            f"/blog/post/{self.post.pk}/", {"author": "Mallory", "body": "spam"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Comment.objects.count(), 0)

    def test_cross_origin_referer_is_rejected_over_https(self):
        token = self._token()
        response = self.client.post(
            f"/blog/post/{self.post.pk}/",
            {"author": "Mallory", "body": "spam", "csrfmiddlewaretoken": token},
            secure=True,
            HTTP_REFERER="https://evil.example/x",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Comment.objects.count(), 0)


class CommentEscapingTests(TestCase):
    """Autoescaping must hold independently of the moderation gate: an approved
    comment is the one place visitor-supplied text reaches the page."""

    def setUp(self):
        cache.clear()
        self.post = Post.objects.create(title="Hello", body="body")

    def test_approved_comment_html_is_escaped(self):
        Comment.objects.create(
            post=self.post,
            author="<img src=x onerror=alert(1)>",
            body="<script>alert(document.domain)</script><svg/onload=alert(2)>",
            approved=True,
        )
        body = self.client.get(f"/blog/post/{self.post.pk}/").content.decode()
        self.assertNotIn("<img src=x onerror=alert(1)>", body)
        self.assertNotIn("<script>alert(document.domain)</script>", body)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", body)
        self.assertIn("&lt;script&gt;", body)

    def test_extra_post_fields_cannot_self_approve_a_comment(self):
        self.client.post(
            f"/blog/post/{self.post.pk}/",
            {"author": "Mallory", "body": "spam", "approved": "true", "id": "999"},
        )
        self.assertFalse(Comment.objects.get().approved)
