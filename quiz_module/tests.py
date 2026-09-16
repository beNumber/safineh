from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_module.models import ProvinceTrustee, Student, User, UserRole
from users_module.models import Access, FieldOfStudy, Grade, Province, School

from .forms import JalaliDateTimeField
from .models import Quiz, QuizAnswer, QuizAttempt, QuizChoice, QuizQuestion
from .views import _finish


class QuizFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        province = Province.objects.create(name="hormozgan")
        cls.school = School.objects.create(province=province, name="مدرسه آزمون")
        cls.grade = Grade.objects.create(school=cls.school, title="دهم")
        cls.field = FieldOfStudy.objects.create(grade=cls.grade, title="ریاضی")
        cls.student = User.objects.create_user(username="student", password="pass", role=UserRole.STUDENT)
        cls.other_student = User.objects.create_user(username="other", password="pass", role=UserRole.STUDENT)
        Student.objects.create(user=cls.student, field=cls.field)
        Student.objects.create(user=cls.other_student, field=cls.field)
        cls.creator = User.objects.create_user(username="admin", password="pass", role=UserRole.ADMIN)
        cls.consultant = User.objects.create_user(username="consultant", password="pass", role=UserRole.CONSULTANT)
        cls.trustee = User.objects.create_user(username="trustee", password="pass", role=UserRole.PROVINCE_TRUSTEE)
        ProvinceTrustee.objects.create(user=cls.trustee, province=province)

    def make_quiz(self, **overrides):
        now = timezone.now()
        values = {
            "title": "آزمون آزمایشی", "creator": self.creator,
            "starts_at": now - timedelta(minutes=5), "ends_at": now + timedelta(hours=2),
            "duration_minutes": 60, "status": Quiz.Status.PUBLISHED,
        }
        values.update(overrides)
        return Quiz.objects.create(**values)

    def make_mcq(self, quiz, order=1, score=Decimal("4")):
        question = QuizQuestion.objects.create(quiz=quiz, question_type=QuizQuestion.Type.MCQ, text="۲ + ۲؟", score=score, order=order)
        choices = [
            QuizChoice.objects.create(question=question, text=str(value), is_correct=value == 4, order=index)
            for index, value in enumerate([2, 3, 4, 5], 1)
        ]
        return question, choices

    def test_direct_student_assignment_is_respected(self):
        quiz = self.make_quiz()
        quiz.students.add(self.student)
        self.assertTrue(quiz.student_is_targeted(self.student))
        self.assertFalse(quiz.student_is_targeted(self.other_student))

    def test_autosave_rejects_choice_from_another_question(self):
        quiz = self.make_quiz()
        question, _ = self.make_mcq(quiz)
        other_question, other_choices = self.make_mcq(quiz, order=2)
        attempt = QuizAttempt.objects.create(
            quiz=quiz, student=self.student, expires_at=timezone.now() + timedelta(minutes=30),
            question_order=[question.pk, other_question.pk], max_score=8,
        )
        self.client.force_login(self.student)
        response = self.client.post(reverse("quiz_module:autosave", args=[attempt.pk, question.pk]), {"choice": other_choices[0].pk, "bookmarked": "false"})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(QuizAnswer.objects.filter(attempt=attempt, question=question).exists())

    def test_finish_applies_negative_marking_and_waits_for_manual_grading(self):
        quiz = self.make_quiz(negative_marking=True, negative_ratio=Decimal("0.25"))
        mcq, choices = self.make_mcq(quiz)
        descriptive = QuizQuestion.objects.create(
            quiz=quiz, question_type=QuizQuestion.Type.DESCRIPTIVE,
            text="توضیح دهید", explanation="پاسخ نمونه", score=Decimal("6"), order=2,
        )
        attempt = QuizAttempt.objects.create(
            quiz=quiz, student=self.student, expires_at=timezone.now() - timedelta(seconds=1),
            question_order=[mcq.pk, descriptive.pk], max_score=10,
        )
        QuizAnswer.objects.create(attempt=attempt, question=mcq, selected_choice=choices[0])
        QuizAnswer.objects.create(attempt=attempt, question=descriptive, text_answer="پاسخ دانش‌آموز")
        _finish(attempt, auto_submitted=True)
        attempt.refresh_from_db()
        mcq_answer = attempt.answers.get(question=mcq)
        self.assertEqual(mcq_answer.earned_score, Decimal("-1"))
        self.assertEqual(attempt.score, Decimal("-1"))
        self.assertEqual(attempt.status, QuizAttempt.Status.SUBMITTED)
        self.assertTrue(attempt.auto_submitted)

    def test_publish_rejects_incomplete_mcq(self):
        quiz = self.make_quiz(status=Quiz.Status.DRAFT)
        QuizQuestion.objects.create(quiz=quiz, question_type=QuizQuestion.Type.MCQ, text="ناقص", order=1)
        self.client.force_login(self.creator)
        response = self.client.post(reverse("quiz_module:publish", args=[quiz.pk]))
        quiz.refresh_from_db()
        self.assertRedirects(response, reverse("quiz_module:dashboard"))
        self.assertEqual(quiz.status, Quiz.Status.DRAFT)

    def test_future_answer_key_is_hidden_from_student(self):
        quiz = self.make_quiz(answer_release_at=timezone.now() + timedelta(days=1))
        question, choices = self.make_mcq(quiz)
        question.explanation = "پاسخ محرمانه تا فردا"
        question.save(update_fields=["explanation"])
        attempt = QuizAttempt.objects.create(
            quiz=quiz, student=self.student, expires_at=timezone.now(), submitted_at=timezone.now(),
            status=QuizAttempt.Status.GRADED, question_order=[question.pk], max_score=4, score=4,
        )
        QuizAnswer.objects.create(attempt=attempt, question=question, selected_choice=choices[2], is_correct=True, earned_score=4)
        self.client.force_login(self.student)
        response = self.client.get(reverse("quiz_module:result", args=[attempt.pk]))
        self.assertNotContains(response, "پاسخ محرمانه تا فردا")
        self.assertContains(response, "نتیجه پس از انتشار کلید")

    def test_author_reports_and_exports_render(self):
        quiz = self.make_quiz()
        question, choices = self.make_mcq(quiz)
        attempt = QuizAttempt.objects.create(
            quiz=quiz, student=self.student, expires_at=timezone.now(), submitted_at=timezone.now(),
            status=QuizAttempt.Status.GRADED, question_order=[question.pk], max_score=4, score=4,
        )
        QuizAnswer.objects.create(attempt=attempt, question=question, selected_choice=choices[2], is_correct=True, earned_score=4)
        self.client.force_login(self.creator)
        for route in [
            reverse("quiz_module:questions", args=[quiz.pk]),
            reverse("quiz_module:question_edit", args=[quiz.pk, question.pk]),
            reverse("quiz_module:reports", args=[quiz.pk]),
        ]:
            self.assertEqual(self.client.get(route).status_code, 200)
        excel = self.client.get(reverse("quiz_module:export_excel", args=[quiz.pk]))
        pdf = self.client.get(reverse("quiz_module:export_pdf", args=[quiz.pk]))
        self.assertEqual(excel.status_code, 200)
        self.assertIn("application/vnd.ms-excel", excel["Content-Type"])
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")

    def test_consultant_needs_quiz_access(self):
        self.client.force_login(self.consultant)
        self.assertEqual(self.client.get(reverse("quiz_module:create")).status_code, 302)
        access = Access.objects.create(name=Access.Code.QUIZ)
        self.consultant.accesses.add(access)
        response = self.client.get(reverse("quiz_module:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-jdp")

    def test_admin_can_publish_without_quiz_access(self):
        quiz = self.make_quiz(status=Quiz.Status.DRAFT)
        self.make_mcq(quiz)
        self.client.force_login(self.creator)
        response = self.client.post(reverse("quiz_module:publish", args=[quiz.pk]))
        self.assertRedirects(response, reverse("quiz_module:dashboard"))
        quiz.refresh_from_db()
        self.assertEqual(quiz.status, Quiz.Status.PUBLISHED)

    def test_consultant_quiz_requires_matching_trustee_approval(self):
        access = Access.objects.create(name=Access.Code.QUIZ)
        self.consultant.accesses.add(access)
        quiz = self.make_quiz(creator=self.consultant, status=Quiz.Status.DRAFT)
        quiz.schools.add(self.school)
        self.make_mcq(quiz)

        self.client.force_login(self.consultant)
        response = self.client.post(reverse("quiz_module:submit_for_review", args=[quiz.pk]))
        self.assertRedirects(response, reverse("quiz_module:dashboard"))
        quiz.refresh_from_db()
        self.assertEqual(quiz.status, Quiz.Status.PENDING)
        direct_publish = self.client.post(reverse("quiz_module:publish", args=[quiz.pk]))
        self.assertEqual(direct_publish.status_code, 403)

        self.client.force_login(self.trustee)
        self.assertContains(self.client.get(reverse("quiz_module:review_queue")), quiz.title)
        self.assertEqual(self.client.get(reverse("quiz_module:review_detail", args=[quiz.pk])).status_code, 200)
        approval = self.client.post(reverse("quiz_module:approve", args=[quiz.pk]), {"note": "مورد تأیید است"})
        self.assertRedirects(approval, reverse("quiz_module:review_queue"))
        quiz.refresh_from_db()
        self.assertEqual(quiz.status, Quiz.Status.PUBLISHED)
        self.assertEqual(quiz.reviewed_by, self.trustee)

    def test_jalali_picker_accepts_full_24_hour_range(self):
        value = JalaliDateTimeField().clean("۱۴۰۵/۰۶/۲۴ ۲۳:۵۹")
        local_value = timezone.localtime(value)
        self.assertEqual((local_value.hour, local_value.minute), (23, 59))
