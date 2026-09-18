from django.contrib.auth import get_user_model
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_module.models import UserRole
from users_module.models import Access, FieldOfStudy, Grade, Province, School, Subject

from .models import Chapter, ExamAnswer, ExamSession, PracticeAnswer, PracticeSession, Question, Topic


class WrittenQuestionFlowTests(TestCase):
    def setUp(self):
        province = Province.objects.create(name="hormozgan")
        school = School.objects.create(name="مدرسه آزمون", province=province)
        grade = Grade.objects.create(title="دهم", school=school)
        field = FieldOfStudy.objects.create(title="ریاضی", grade=grade)
        self.subject = Subject.objects.create(title="فیزیک", field=field)
        self.chapter = Chapter.objects.create(subject=self.subject, name="حرکت")
        self.topic = Topic.objects.create(chapter=self.chapter, name="سرعت متوسط")
        self.question = Question.objects.create(
            question_type=Question.Type.DESCRIPTIVE, chapter=self.chapter, topic=self.topic,
            text="سرعت متوسط را تعریف کنید.", explanation="نسبت جابه‌جایی به زمان است.",
            approval_status=Question.ApprovalStatus.APPROVED,
        )
        self.student = get_user_model().objects.create_user(username="student-written", password="pass")
        self.admin = get_user_model().objects.create_user(username="admin-written", password="pass", role=UserRole.ADMIN)

    def test_only_admin_can_manage_curriculum(self):
        self.client.force_login(self.student)
        self.assertRedirects(self.client.get(reverse("questions_module:curriculum_manage")), reverse("questions_module:choose_mode"))
        self.client.force_login(self.admin)
        response = self.client.get(reverse("questions_module:curriculum_manage"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سرعت متوسط")

    def test_descriptive_practice_reveals_answer_without_text_input(self):
        session = PracticeSession.objects.create(user=self.student, total_questions=1, question_type=Question.Type.DESCRIPTIVE)
        session.questions.add(self.question)
        session.chapters.add(self.chapter)
        session.topics.add(self.topic)
        self.client.force_login(self.student)
        page = self.client.get(reverse("questions_module:practice_session", args=[session.pk]))
        self.assertContains(page, "مشاهده پاسخ سؤال")
        self.assertNotContains(page, "<textarea")
        reveal_url = reverse("questions_module:practice_reveal", args=[session.pk, self.question.pk])
        reveal = self.client.post(reveal_url)
        self.assertEqual(reveal.status_code, 200)
        self.assertEqual(reveal.json()["explanation"], self.question.explanation)
        response = self.client.post(reverse("questions_module:practice_submit", args=[session.pk]), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پاسخ تشریحی سؤال")
        self.assertEqual(PracticeAnswer.objects.get().text_answer, "")

    def test_descriptive_exam_only_shows_question_and_reveal_button(self):
        session = ExamSession.objects.create(user=self.student, total_questions=1, question_type=Question.Type.DESCRIPTIVE, ends_at=timezone.now() + timedelta(minutes=5))
        session.questions.add(self.question)
        session.chapters.add(self.chapter)
        session.topics.add(self.topic)
        self.client.force_login(self.student)
        page = self.client.get(reverse("questions_module:exam_session", args=[session.pk]))
        self.assertContains(page, "مشاهده پاسخ سؤال")
        self.assertNotContains(page, "<textarea")
        response = self.client.post(reverse("questions_module:exam_submit", args=[session.pk]), {}, follow=True)
        self.assertContains(response, "پاسخ تشریحی سؤال")
        self.assertEqual(ExamAnswer.objects.get().text_answer, "")

    def test_assigned_consultant_sees_descriptive_form_without_choices(self):
        consultant = get_user_model().objects.create_user(username="consultant-written", password="pass", role=UserRole.CONSULTANT)
        access = Access.objects.create(name=Access.Code.BANK, subject=self.subject)
        consultant.accesses.add(access)
        self.client.force_login(consultant)
        response = self.client.get(reverse("questions_module:question_create") + "?type=DES")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فقط متن سؤال و پاسخ تشریحی")
        self.assertNotContains(response, "<h2 class=\"mb-4 font-black text-slate-800\">گزینه‌ها</h2>", html=True)

    def test_written_wizard_selects_topic_and_starts_practice(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("questions_module:choose_mode"), {"mode": "practice", "question_type": "DES"})
        self.assertRedirects(response, reverse("questions_module:select_courses"))
        response = self.client.post(reverse("questions_module:select_courses"), {"courses": [self.subject.pk]})
        self.assertRedirects(response, reverse("questions_module:select_chapters"))
        page = self.client.get(reverse("questions_module:select_chapters"))
        self.assertContains(page, self.chapter.name)
        self.assertContains(page, self.topic.name)
        response = self.client.post(reverse("questions_module:select_chapters"), {
            "topics": [self.topic.pk], "difficulties": ["M"], "count_M": 1,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("questions_module:start_practice"))
        response = self.client.get(reverse("questions_module:start_practice"))
        session = PracticeSession.objects.latest("pk")
        self.assertRedirects(response, reverse("questions_module:practice_session", args=[session.pk]))
        self.assertEqual(session.question_type, Question.Type.DESCRIPTIVE)
        self.assertEqual(list(session.topics.all()), [self.topic])
