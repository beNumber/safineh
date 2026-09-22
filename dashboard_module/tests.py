from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_module.models import User, UserRole
from blog_module.models import Category as BlogCategory, Post
from news_module.models import Article, Category as NewsCategory


class FanousDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="fanous-student", password="pass12345", role=UserRole.STUDENT
        )
        blog_category = BlogCategory.objects.create(name="آموزش", slug="learning")
        news_category = NewsCategory.objects.create(name="اطلاعیه", slug="notice")
        self.post = Post.objects.create(
            title="مطلب تازه فانوس",
            slug="new-fanous-post",
            summary="خلاصه",
            body="متن",
            category=blog_category,
            author=self.user,
            status="published",
            published_at=timezone.now(),
        )
        self.article = Article.objects.create(
            title="خبر تازه فانوس",
            slug="new-fanous-news",
            category=news_category,
            summary="خلاصه خبر",
            content="متن خبر",
            status=Article.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.client.force_login(self.user)

    def test_dashboard_shows_role_greeting_and_new_content_notifications(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "دانش‌آموز پرتلاش فانوس")
        self.assertContains(response, self.post.title)
        self.assertContains(response, self.article.title)
        self.assertContains(response, 'id="notification-count"')

    def test_marking_notifications_read_clears_new_content_badge(self):
        response = self.client.post(reverse("notifications_read"))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, 'id="notification-count"')
