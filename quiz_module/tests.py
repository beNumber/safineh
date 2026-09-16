from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from auth_module.models import UserRole
from users_module.models import Access, FieldOfStudy, Grade, Province, School

from .forms import QuizForm
from .models import Quiz, QuizAnswer, QuizChoice, QuizQuestion
from .permissions import can_create_quiz
from .services import create_attempt, finalize_attempt


class QuizFeatureTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.admin = self.User.objects.create_user(username="admin-q", password="x", role=UserRole.ADMIN)
        self.consultant = self.User.objects.create_user(username="consultant-q", password="x", role=UserRole.CONSULTANT)
        self.student = self.User.objects.create_user(username="student-q", password="x", role=UserRole.STUDENT)
        self.province = Province.objects.create(name="kerman")
        self.school = School.objects.create(name="مدرسه آزمون", province=self.province)
        self.grade = Grade.objects.create(title="دهم", school=self.school)
        self.field = FieldOfStudy.objects.create(title="ریاضی", grade=self.grade)

    def test_consultant_needs_quiz_access(self):
        self.assertFalse(can_create_quiz(self.consultant))
        access = Access.objects.create(name=Access.Code.QUIZ)
        self.consultant.accesses.add(access)
        self.assertTrue(can_create_quiz(self.consultant))
        self.assertTrue(can_create_quiz(self.admin))

    def test_jalali_form_accepts_arbitrary_minute(self):
        form = QuizForm(data={
            "title": "آزمون ساعت دلخواه", "province": self.province.pk, "school": self.school.pk,
            "grade": self.grade.pk, "field": self.field.pk, "duration_minutes": 45, "max_attempts": 1,
            "opens_date": "1405/06/26", "opens_time": "07:13", "closes_date": "1405/06/26", "closes_time": "09:47",
            "release_date": "1405/06/26", "release_time": "10:02", "negative_ratio": "0.33",
            "shuffle_questions": "on", "shuffle_choices": "on", "publish_results": "on",
        })
        self.assertTrue(form.is_valid(), form.errors)
        quiz = form.save(commit=False)
        self.assertEqual(timezone.localtime(quiz.opens_at).strftime("%H:%M"), "07:13")
        self.assertEqual(timezone.localtime(quiz.closes_at).strftime("%H:%M"), "09:47")

    def test_negative_marking_and_auto_grading(self):
        now = timezone.now()
        quiz = Quiz.objects.create(
            title="آزمون تستی", creator=self.admin, status=Quiz.Status.APPROVED,
            opens_at=now - timedelta(minutes=5), closes_at=now + timedelta(hours=1),
            duration_minutes=30, negative_marking=True, negative_ratio=Decimal("0.25"),
        )
        question = QuizQuestion.objects.create(quiz=quiz, text="دو بعلاوه دو؟", points=4)
        QuizChoice.objects.create(question=question, text="۴", is_correct=True)
        wrong = QuizChoice.objects.create(question=question, text="۵", is_correct=False)
        QuizChoice.objects.create(question=question, text="۶")
        QuizChoice.objects.create(question=question, text="۷")
        attempt = create_attempt(quiz, self.student)
        QuizAnswer.objects.create(attempt=attempt, question=question, choice=wrong)
        result = finalize_attempt(attempt)
        self.assertEqual(result.wrong_count, 1)
        self.assertEqual(result.score, Decimal("0"))
        self.assertEqual(result.answers.get().points_earned, Decimal("-1"))

    def test_admin_quiz_pages_render(self):
        self.client.force_login(self.admin)
        response = self.client.get("/quizzes/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مدیریت آزمون‌ها")
        response = self.client.get("/quizzes/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ساعت شروع")
