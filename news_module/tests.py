from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auth_module.models import Student
from users_module.models import FieldOfStudy, Grade, Province, School

from .models import Article, Category


class ArticleAudienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hormozgan = Province.objects.create(name="hormozgan")
        cls.kerman = Province.objects.create(name="kerman")
        cls.school = School.objects.create(province=cls.hormozgan, name="مدرسه ساحل")
        cls.other_school = School.objects.create(province=cls.kerman, name="مدرسه کویر")
        cls.grade = Grade.objects.create(school=cls.school, title="پایه دهم")
        cls.other_grade = Grade.objects.create(school=cls.other_school, title="پایه یازدهم")
        cls.field = FieldOfStudy.objects.create(grade=cls.grade, title="ریاضی")
        cls.category = Category.objects.create(name="اطلاعیه", slug="notice")

        user_model = get_user_model()
        cls.student_user = user_model.objects.create_user(username="student", password="pass12345")
        cls.staff_user = user_model.objects.create_user(username="staff", password="pass12345", is_staff=True)
        Student.objects.create(user=cls.student_user, field=cls.field)

        cls.public_article = cls.make_article("عمومی", "public")
        cls.province_article = cls.make_article("استانی", "province")
        cls.province_article.target_provinces.add(cls.hormozgan)
        cls.school_article = cls.make_article("مدرسه‌ای", "school")
        cls.school_article.target_schools.add(cls.school)
        cls.grade_article = cls.make_article("پایه‌ای", "grade")
        cls.grade_article.target_grades.add(cls.grade)
        cls.other_article = cls.make_article("نامرتبط", "other")
        cls.other_article.target_grades.add(cls.other_grade)

    @classmethod
    def make_article(cls, title, slug):
        return Article.objects.create(
            title=title,
            slug=slug,
            category=cls.category,
            summary=title,
            content=title,
            status=Article.Status.PUBLISHED,
            published_at=timezone.now(),
        )

    def test_anonymous_user_only_sees_public_articles(self):
        visible = Article.objects.published().visible_to(None)
        self.assertQuerySetEqual(visible, [self.public_article], ordered=False)

    def test_authenticated_user_without_profile_sees_public_articles(self):
        user = get_user_model().objects.create_user(username="no-profile", password="pass12345")
        visible = Article.objects.published().visible_to(user)
        self.assertQuerySetEqual(visible, [self.public_article], ordered=False)

    def test_student_sees_matching_audiences(self):
        visible = Article.objects.published().visible_to(self.student_user)
        self.assertSetEqual(
            set(visible),
            {self.public_article, self.province_article, self.school_article, self.grade_article},
        )

    def test_staff_can_preview_every_article(self):
        visible = Article.objects.visible_to(self.staff_user)
        self.assertEqual(visible.count(), 5)

    def test_unmatched_article_detail_returns_not_found(self):
        self.client.force_login(self.student_user)
        response = self.client.get(self.other_article.get_absolute_url())
        self.assertEqual(response.status_code, 404)
