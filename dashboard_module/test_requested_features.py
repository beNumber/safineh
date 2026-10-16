from datetime import timedelta
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auth_module.models import ProvinceTrustee, Student, User, UserRole
from classroom_module.models import OnlineClass
from counseling_module.models import StudentConsultantAssignment
from courses_module.models import Course
from plans_module.forms import jalali_date_string
from plans_module.models import ActivityType, PlanEntry
from questions_module.models import Chapter, Question, Topic
from questions_module.views import _usable_question_qs
from quiz_module.models import Quiz, QuizAttempt
from quiz_module.permissions import available_student_quizzes, student_quizzes
from ticketing_module.models import Ticket, TicketQueue, TicketStatus, TicketType
from users_module.models import FieldOfStudy, Grade, Province, School, Subject


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RequestedFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province = Province.objects.get_or_create(name="hormozgan")[0]
        cls.other_province = Province.objects.get_or_create(name="kerman")[0]
        cls.school = School.objects.create(name="مدرسه آزمون", province=cls.province)
        cls.grade = Grade.objects.create(title="دهم", school=cls.school)
        cls.field = FieldOfStudy.objects.create(title="ریاضی", grade=cls.grade)
        cls.subject = Subject.objects.create(title="حسابان", field=cls.field)
        cls.chapter = Chapter.objects.create(name="فصل اول", subject=cls.subject)
        cls.topic = Topic.objects.create(name="مبحث اول", chapter=cls.chapter)
        cls.student = User.objects.create_user(username="features-student", role=UserRole.STUDENT)
        cls.profile = Student.objects.create(user=cls.student, field=cls.field)
        cls.second_student = User.objects.create_user(username="features-second", role=UserRole.STUDENT)
        cls.second_profile = Student.objects.create(user=cls.second_student, field=cls.field)
        cls.consultant = User.objects.create_user(username="features-consultant", role=UserRole.CONSULTANT)
        cls.admin = User.objects.create_user(username="features-admin", role=UserRole.ADMIN)
        cls.superuser = User.objects.create_superuser(username="features-super", password="test")
        cls.trustee = User.objects.create_user(username="features-trustee", role=UserRole.PROVINCE_TRUSTEE)
        ProvinceTrustee.objects.create(user=cls.trustee, province=cls.province)

    def make_quiz(self, **overrides):
        values = dict(title="آزمون مرتبط", creator=self.consultant, status=Quiz.Status.APPROVED,
                      opens_at=timezone.now() - timedelta(minutes=5),
                      closes_at=timezone.now() + timedelta(hours=2), province=self.province)
        values.update(overrides)
        return Quiz.objects.create(**values)

    def test_consultant_can_submit_without_bank_access_but_not_publish(self):
        self.client.force_login(self.consultant)
        response = self.client.get(reverse("questions_module:question_create"), {"type": "DES"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.subject, response.context["form"].fields["subject"].queryset)
        response = self.client.post(reverse("questions_module:question_create"), {
            "question_type": "DES", "grade": self.grade.pk, "field": self.field.pk,
            "subject": self.subject.pk, "chapter": self.chapter.pk, "topic": self.topic.pk,
            "difficulty": "E", "text": "سؤال جدید", "explanation": "پاسخ سؤال", "is_active": "on",
            "choices-TOTAL_FORMS": "0", "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0", "choices-MAX_NUM_FORMS": "4",
        })
        self.assertEqual(response.status_code, 302)
        question = Question.objects.get(creator=self.consultant)
        self.assertEqual(question.approval_status, Question.ApprovalStatus.PENDING)
        self.assertFalse(question.is_active)
        self.assertNotIn(question, _usable_question_qs("DES"))
        self.client.force_login(self.trustee)
        self.client.post(reverse("questions_module:review_question", args=[question.pk]),
                         {"decision": Question.ApprovalStatus.APPROVED})
        self.assertIn(question, _usable_question_qs("DES"))

    def test_question_overview_has_submission_action(self):
        self.client.force_login(self.consultant)
        response = self.client.get(reverse("questions_module:choose_mode"))
        self.assertContains(response, "افزودن سؤال به بانک")
        self.assertTrue(response.context["can_create_question"])

    def test_bulk_assignment_and_reassignment_are_idempotent(self):
        self.client.force_login(self.admin)
        for repeat in range(2):
            response = self.client.post(reverse("counseling:bulk_assign"), {
                "students": [self.profile.pk, self.second_profile.pk], "consultant": self.consultant.pk,
            })
            self.assertEqual(response.status_code, 302)
        self.assertEqual(StudentConsultantAssignment.objects.count(), 2)
        self.assertEqual(StudentConsultantAssignment.objects.filter(assigned_by=self.admin).count(), 2)

    def test_bulk_assignment_rejects_entire_out_of_province_selection(self):
        other_school = School.objects.create(province=self.other_province, name="خارج محدوده")
        other_grade = Grade.objects.create(school=other_school, title="دهم")
        other_field = FieldOfStudy.objects.create(grade=other_grade, title="ریاضی")
        Student.objects.filter(pk=self.second_profile.pk).update(field=other_field)
        self.client.force_login(self.trustee)
        self.client.post(reverse("counseling:bulk_assign"), {
            "students": [self.profile.pk, self.second_profile.pk], "consultant": self.consultant.pk,
        })
        self.assertFalse(StudentConsultantAssignment.objects.exists())

    def test_bulk_assignment_rejects_non_consultant_and_empty_selection(self):
        self.client.force_login(self.admin)
        for payload in [{"students": [self.profile.pk], "consultant": self.admin.pk},
                        {"consultant": self.consultant.pk}]:
            self.client.post(reverse("counseling:bulk_assign"), payload)
        self.assertFalse(StudentConsultantAssignment.objects.exists())

    def test_admin_navigation_has_bulk_assignment_not_my_consultant(self):
        for user in [self.admin, self.superuser]:
            self.client.force_login(user)
            response = self.client.get(reverse("counseling:manage"))
            self.assertContains(response, 'id="bulk-assignment-form"')
            self.assertContains(response, 'form="bulk-assignment-form"')
            self.assertNotContains(response, 'title="مشاور من"')
            self.assertContains(response, 'title="تخصیص مشاور"')
        self.assertRedirects(self.client.get(reverse("counseling:my_consultant")), reverse("counseling:manage"))

    def test_quiz_audiences_match_the_actual_student(self):
        regional = self.make_quiz()
        wrong_province = self.make_quiz(province=self.other_province)
        personal = self.make_quiz(province=self.other_province)
        personal.assigned_students.add(self.student)
        another_student = self.make_quiz()
        another_student.assigned_students.add(self.second_student)
        universal = self.make_quiz(all_students=True, province=self.other_province)
        self.assertSetEqual(set(student_quizzes(self.student)),
                            {regional, personal, universal})
        self.assertNotIn(wrong_province, student_quizzes(self.student))
        self.assertNotIn(another_student, student_quizzes(self.student))

    def test_quiz_profile_filters_cannot_mix_two_profiles(self):
        other_school = School.objects.create(province=self.other_province, name="مدرسه دوم")
        other_grade = Grade.objects.create(school=other_school, title="یازدهم")
        other_field = FieldOfStudy.objects.create(grade=other_grade, title="تجربی")
        Student.objects.create(user=self.student, field=other_field)
        impossible = self.make_quiz(field=other_field)
        self.assertNotIn(impossible, student_quizzes(self.student))

    def test_quiz_indicator_ignores_paused_closed_draft_and_exhausted_quizzes(self):
        active = self.make_quiz()
        future = self.make_quiz(opens_at=timezone.now() + timedelta(hours=1))
        self.make_quiz(is_paused=True)
        self.make_quiz(closes_at=timezone.now() - timedelta(minutes=1))
        self.make_quiz(status=Quiz.Status.DRAFT)
        exhausted = self.make_quiz()
        QuizAttempt.objects.create(quiz=exhausted, student=self.student, status=QuizAttempt.Status.SUBMITTED)
        self.assertSetEqual(set(available_student_quizzes(self.student)), {active, future})
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["active_exam_count"], 1)
        self.assertEqual(len(response.context["fanous_quiz_windows"]), 2)
        self.assertContains(response, 'id="quiz-live-windows"')
        self.assertContains(response, active.title)

    def test_indicator_keeps_live_attempt_but_not_expired_attempt(self):
        quiz = self.make_quiz()
        attempt = QuizAttempt.objects.create(quiz=quiz, student=self.student,
                                             expires_at=timezone.now() + timedelta(minutes=15))
        self.assertIn(quiz, available_student_quizzes(self.student))
        QuizAttempt.objects.filter(pk=attempt.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertNotIn(quiz, available_student_quizzes(self.student))

    def test_tomorrow_and_today_plans_are_date_specific(self):
        today = timezone.localdate()
        plans = {}
        for label, date in [("today", today), ("old", today - timedelta(days=7)),
                            ("tomorrow", today + timedelta(days=1))]:
            plans[label] = PlanEntry.objects.create(student=self.profile, activity_type=ActivityType.OTHER,
                title=label, scheduled_date=date, weekday=(date.weekday() + 2) % 7, start_hour=10, end_hour=11)
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "کارهای روبه‌رو")
        self.assertQuerySetEqual(response.context["today_plans"], [plans["today"]])
        self.assertQuerySetEqual(response.context["tomorrow_plans"], [plans["tomorrow"]])

    def test_upcoming_classes_include_live_and_exclude_inactive_or_finished(self):
        now = timezone.now()
        classes = {}
        for title, start, end, active in [
            ("live", now - timedelta(minutes=10), now + timedelta(minutes=30), True),
            ("upcoming", now + timedelta(days=1), now + timedelta(days=1, hours=1), True),
            ("finished", now - timedelta(hours=2), now - timedelta(hours=1), True),
            ("disabled", now + timedelta(hours=1), now + timedelta(hours=2), False),
        ]:
            classes[title] = OnlineClass.objects.create(title=title, starts_at=start, ends_at=end,
                                                        is_active=active, meeting_url="https://example.com/class")
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard"))
        self.assertQuerySetEqual(response.context["upcoming_classes"], [classes["live"], classes["upcoming"]])

    def test_quiz_indicator_is_available_on_non_dashboard_pages(self):
        quiz = self.make_quiz()
        self.client.force_login(self.student)
        response = self.client.get(reverse("ticketing:list"))
        self.assertEqual(response.context["active_exam_count"], 1)
        self.assertContains(response, 'id="quiz-live-indicator"')
        self.assertContains(response, quiz.opens_at.isoformat())
        Quiz.objects.filter(pk=quiz.pk).update(opens_at=timezone.now() + timedelta(minutes=20))
        response = self.client.get(reverse("ticketing:list"))
        self.assertEqual(response.context["active_exam_count"], 0)
        self.assertEqual(len(response.context["fanous_quiz_windows"]), 1)

    def test_consultant_cannot_use_bulk_assignment(self):
        self.client.force_login(self.consultant)
        response = self.client.post(reverse("counseling:bulk_assign"), {
            "students": [self.profile.pk], "consultant": self.consultant.pk,
        })
        self.assertIn(response.status_code, [302, 403])
        self.assertFalse(StudentConsultantAssignment.objects.exists())

    def test_new_plan_defaults_to_today_even_when_browsing_another_week(self):
        for user in [self.student, self.admin]:
            self.client.force_login(user)
            response = self.client.get(reverse("plans_module:board"), {
                "week": (timezone.localdate() - timedelta(days=14)).isoformat(), "student": self.profile.pk,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["form"].initial["scheduled_date"], jalali_date_string(timezone.localdate()))

    def test_curriculum_duplicates_are_rejected_within_their_parent(self):
        for model, values in [(Grade, {"title": " دهم ", "school": self.school}),
                              (FieldOfStudy, {"title": "رياضي", "grade": self.grade})]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create(**values)
        other_school = School.objects.create(name="مدرسه مستقل", province=self.province)
        independent = Grade.objects.create(title="دهم", school=other_school)
        FieldOfStudy.objects.create(title="ریاضی", grade=independent)

    def test_ticket_glass_theme_covers_list_detail_create_and_moderation(self):
        ticket = Ticket.objects.create(student=self.profile, title="گفت‌وگوی تست", ticket_type=TicketType.TECHNICAL,
                                       current_queue=TicketQueue.TRUSTEE, status=TicketStatus.OPEN)
        self.client.force_login(self.student)
        for url in [reverse("ticketing:list"), reverse("ticketing:create"), reverse("ticketing:detail", args=[ticket.pk])]:
            response = self.client.get(url)
            self.assertContains(response, "css/ticketing-glass.css")
            self.assertContains(response, 'class="ticket-shell"')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("ticketing:moderation_queue")), "میز بررسی پیوست‌ها")

    def test_ticket_search_and_stats_remain_scoped(self):
        mine = Ticket.objects.create(student=self.profile, title="پرسش خصوصی", ticket_type=TicketType.TECHNICAL,
                                     status=TicketStatus.OPEN)
        Ticket.objects.create(student=self.second_profile, title="تیکت مخفی", ticket_type=TicketType.TECHNICAL)
        self.client.force_login(self.student)
        response = self.client.get(reverse("ticketing:list"), {"q": "خصوصی"})
        self.assertEqual(response.context["total_count"], 1)
        self.assertEqual(list(response.context["tickets"]), [mine])


class CurriculumMergeMigrationTests(TransactionTestCase):
    def test_duplicate_merge_preserves_student_subject_quiz_and_course_relations(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("users_module", "0007_deactivate_legacy_school_values")])
            province = Province.objects.get_or_create(name="hormozgan")[0]
            school = School.objects.create(province=province, name="merge-test")
            grade = Grade.objects.create(school=school, title="دهم")
            duplicate_grade = Grade.objects.create(school=school, title="دهم")
            field = FieldOfStudy.objects.create(grade=grade, title="ریاضی")
            duplicate_field = FieldOfStudy.objects.create(grade=duplicate_grade, title="ریاضی")
            user = User.objects.create_user(username="merge-student", role=UserRole.STUDENT)
            profile = Student.objects.create(user=user, field=duplicate_field)
            subject = Subject.objects.create(title="درس محفوظ", field=duplicate_field)
            quiz = Quiz.objects.create(title="آزمون محفوظ", grade=duplicate_grade, field=duplicate_field,
                                       opens_at=timezone.now(), closes_at=timezone.now() + timedelta(hours=1))
            course = Course.objects.create(title="دوره محفوظ", slug="merge-course", author=user, description="شرح")
            course.allowed_fields.add(field, duplicate_field)
            course.allowed_grades.add(grade, duplicate_grade)
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            profile.refresh_from_db()
            subject.refresh_from_db()
            quiz.refresh_from_db()
            self.assertEqual(profile.field_id, field.pk)
            self.assertEqual(subject.field_id, field.pk)
            self.assertEqual(quiz.field_id, field.pk)
            self.assertEqual(quiz.grade_id, grade.pk)
            self.assertQuerySetEqual(course.allowed_fields.all(), [field])
            self.assertQuerySetEqual(course.allowed_grades.all(), [grade])
            self.assertFalse(Grade.objects.filter(pk=duplicate_grade.pk).exists())
            self.assertFalse(FieldOfStudy.objects.filter(pk=duplicate_field.pk).exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
