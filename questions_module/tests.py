from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from auth_module.models import UserRole
from users_module.models import Access, FieldOfStudy, Grade, Province, School, Subject

from .models import (
    Chapter,
    Choice,
    ExamAnswer,
    ExamSession,
    PracticeAnswer,
    PracticeSession,
    Question,
)


class QuestionWizardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="question-user",
            password="test-password",
        )
        self.client.force_login(self.user)

        province = Province.objects.create(name="hormozgan")
        school = School.objects.create(province=province, name="مدرسه تست")
        grade = Grade.objects.create(title="دهم", code="G10", school=school)
        field = FieldOfStudy.objects.create(title="ریاضی", code="MATH", grade=grade)
        self.subject = Subject.objects.create(title="ریاضی", code="MATH-1", field=field)
        self.question_access = Access.objects.create(
            name=Access.Code.CREATE_QUESTION, subject=self.subject
        )
        self.chapter = Chapter.objects.create(subject=self.subject, name="فصل اول")
        self.question = Question.objects.create(
            chapter=self.chapter,
            text="دو بعلاوه دو چند می‌شود؟",
            question_type=Question.Type.MCQ,
            is_active=True,
        )
        self.correct_choice = Choice.objects.create(
            question=self.question,
            text="چهار",
            is_correct=True,
        )
        for text in ("یک", "دو", "سه"):
            Choice.objects.create(question=self.question, text=text)

    def test_root_enters_wizard_instead_of_ignoring_post(self):
        response = self.client.get(reverse("questions_module:question_list"))

        self.assertRedirects(response, reverse("questions_module:choose_mode"))

    def test_practice_flow_reaches_result(self):
        response = self.client.post(
            reverse("questions_module:choose_mode"),
            {"mode": "practice"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("questions_module:select_courses"))

        response = self.client.post(
            reverse("questions_module:select_courses"),
            {"courses": [self.subject.pk]},
        )
        self.assertRedirects(response, reverse("questions_module:select_chapters"))

        response = self.client.post(
            reverse("questions_module:select_chapters"),
            {
                "chapters": [self.chapter.pk],
                "difficulty": self.question.difficulty,
                "question_count": 1,
            },
            follow=True,
        )
        practice_session = PracticeSession.objects.get(user=self.user)
        self.assertEqual(
            response.redirect_chain,
            [
                (reverse("questions_module:start_practice"), 302),
                (
                    reverse(
                        "questions_module:practice_session",
                        args=[practice_session.pk],
                    ),
                    302,
                ),
            ],
        )
        self.assertContains(response, self.question.text)

        response = self.client.post(
            reverse("questions_module:practice_submit", args=[practice_session.pk]),
            {f"question_{self.question.pk}": self.correct_choice.pk},
        )
        self.assertRedirects(
            response,
            reverse("questions_module:practice_result", args=[practice_session.pk]),
        )

        practice_session.refresh_from_db()
        self.assertEqual(practice_session.correct_count, 1)
        self.assertEqual(practice_session.percent, 100.0)

    def test_question_with_more_or_less_than_four_choices_is_not_usable(self):
        Choice.objects.create(question=self.question, text="پنج")
        self.client.post(reverse("questions_module:choose_mode"), {"mode": "practice"})
        response = self.client.get(reverse("questions_module:select_courses"))
        self.assertNotContains(response, self.subject.title)

    def test_student_cannot_open_question_create(self):
        response = self.client.get(reverse("questions_module:question_create"))
        self.assertRedirects(response, reverse("questions_module:choose_mode"))

    def test_non_student_with_bank_access_can_open_question_form(self):
        self.user.role = UserRole.CONTENT_MODERATOR
        self.user.save(update_fields=["role"])
        self.user.accesses.add(self.question_access)
        response = self.client.get(reverse("questions_module:question_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "دقیقاً چهار گزینه")

    def test_non_student_without_access_cannot_create_question(self):
        self.user.role = UserRole.ADMIN
        self.user.save(update_fields=["role"])
        response = self.client.get(reverse("questions_module:question_create"))
        self.assertRedirects(response, reverse("questions_module:choose_mode"))

    def test_student_is_denied_even_when_bank_access_is_checked(self):
        self.user.accesses.add(self.question_access)
        response = self.client.get(reverse("questions_module:question_create"))
        self.assertRedirects(response, reverse("questions_module:choose_mode"))

    def test_superuser_can_create_without_access_tick(self):
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        self.assertEqual(self.client.get(reverse("questions_module:question_create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("questions_module:chapter_create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("questions_module:subject_create")).status_code, 200)

    def test_each_creation_permission_is_independent(self):
        self.user.role = UserRole.CONTENT_MODERATOR
        self.user.save(update_fields=["role"])
        chapter_access = Access.objects.create(
            name=Access.Code.CREATE_CHAPTER, subject=self.subject
        )
        self.user.accesses.add(chapter_access)
        self.assertEqual(self.client.get(reverse("questions_module:chapter_create")).status_code, 200)
        self.assertRedirects(
            self.client.get(reverse("questions_module:question_create")),
            reverse("questions_module:choose_mode"),
        )
        self.assertRedirects(
            self.client.get(reverse("questions_module:subject_create")),
            reverse("questions_module:choose_mode"),
        )

    def test_practice_answer_is_immediate_and_cannot_change(self):
        session = PracticeSession.objects.create(user=self.user, total_questions=1)
        session.chapters.add(self.chapter)
        session.questions.add(self.question)
        url = reverse(
            "questions_module:practice_answer",
            args=[session.pk, self.question.pk],
        )
        response = self.client.post(url, {"choice": self.correct_choice.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_correct"])
        self.assertEqual(PracticeAnswer.objects.get().selected_choice, self.correct_choice)

        wrong_choice = self.question.choices.filter(is_correct=False).first()
        response = self.client.post(url, {"choice": wrong_choice.pk})
        self.assertEqual(response.status_code, 409)

    def test_exam_autosave_is_used_when_finishing(self):
        from django.utils import timezone
        from datetime import timedelta

        session = ExamSession.objects.create(
            user=self.user,
            total_questions=1,
            ends_at=timezone.now() + timedelta(minutes=3),
        )
        session.chapters.add(self.chapter)
        session.questions.add(self.question)
        page = self.client.get(reverse("questions_module:exam_session", args=[session.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, self.question.text)
        save_url = reverse(
            "questions_module:exam_save_answer",
            args=[session.pk, self.question.pk],
        )
        self.assertEqual(
            self.client.post(save_url, {"choice": self.correct_choice.pk}).status_code,
            200,
        )
        result = self.client.post(
            reverse("questions_module:exam_submit", args=[session.pk]), {}, follow=True
        )
        self.assertContains(result, "کارنامه آزمون")
        session.refresh_from_db()
        self.assertEqual(session.correct_count, 1)
        self.assertEqual(ExamAnswer.objects.get().selected_choice, self.correct_choice)

# Create your tests here.
