from django.test import TestCase
from django.urls import reverse

from auth_module.models import ProvinceTrustee, Student, User, UserRole
from ticketing_module.models import ModerationStatus, Ticket, TicketQueue
from users_module.models import FieldOfStudy, Grade, Province, School
from questions_module.models import ExamSession

from .models import StudentConsultantAssignment
from .services import manageable_students_for


class CounselingFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province = Province.objects.create(name="hormozgan")
        cls.other_province = Province.objects.create(name="kerman")
        school = School.objects.create(name="مدرسه هرمزگان", province=cls.province)
        other_school = School.objects.create(name="مدرسه کرمان", province=cls.other_province)
        grade = Grade.objects.create(title="دهم", school=school)
        other_grade = Grade.objects.create(title="دهم", school=other_school)
        field = FieldOfStudy.objects.create(title="ریاضی", grade=grade)
        other_field = FieldOfStudy.objects.create(title="تجربی", grade=other_grade)

        cls.student_user = User.objects.create_user(
            username="assigned-student", password="pass12345", role=UserRole.STUDENT,
            first_name="علی", last_name="دانش‌آموز"
        )
        cls.student = Student.objects.create(user=cls.student_user, field=field)
        cls.other_student_user = User.objects.create_user(
            username="other-province-student", password="pass12345", role=UserRole.STUDENT
        )
        cls.other_student = Student.objects.create(user=cls.other_student_user, field=other_field)
        cls.consultant = User.objects.create_user(
            username="dedicated-consultant", password="pass12345", role=UserRole.CONSULTANT,
            first_name="سارا", last_name="مشاور"
        )
        cls.other_consultant = User.objects.create_user(
            username="other-consultant", password="pass12345", role=UserRole.CONSULTANT
        )
        cls.trustee = User.objects.create_user(
            username="province-trustee", password="pass12345", role=UserRole.PROVINCE_TRUSTEE
        )
        ProvinceTrustee.objects.create(user=cls.trustee, province=cls.province)
        cls.admin_user = User.objects.create_user(
            username="system-admin", password="pass12345", role=UserRole.ADMIN
        )
        cls.moderator = User.objects.create_user(
            username="counseling-moderator",
            password="pass12345",
            role=UserRole.CONTENT_MODERATOR,
        )

    def test_trustee_only_manages_students_in_own_province(self):
        visible = manageable_students_for(self.trustee)
        self.assertIn(self.student, visible)
        self.assertNotIn(self.other_student, visible)
        self.client.force_login(self.trustee)
        response = self.client.post(
            reverse("counseling:assign", args=[self.other_student.pk]),
            {"consultant": self.consultant.pk},
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_assigns_and_reassigns_student(self):
        self.client.force_login(self.admin_user)
        manage_page = self.client.get(reverse("counseling:manage"))
        self.assertEqual(manage_page.status_code, 200)
        self.assertContains(manage_page, "هر دانش‌آموز، یک همراه مشخص")
        self.client.post(
            reverse("counseling:assign", args=[self.student.pk]),
            {"consultant": self.consultant.pk, "note": "پیگیری هفتگی"},
        )
        assignment = StudentConsultantAssignment.objects.get(student=self.student)
        self.assertEqual(assignment.consultant, self.consultant)
        self.assertEqual(assignment.assigned_by, self.admin_user)

        self.client.post(
            reverse("counseling:assign", args=[self.student.pk]),
            {"consultant": self.other_consultant.pk},
        )
        assignment.refresh_from_db()
        self.assertEqual(assignment.consultant, self.other_consultant)
        self.assertEqual(StudentConsultantAssignment.objects.filter(student=self.student).count(), 1)

    def test_consultant_sees_assigned_student_in_my_students(self):
        StudentConsultantAssignment.objects.create(
            student=self.student, consultant=self.consultant, assigned_by=self.admin_user
        )
        self.client.force_login(self.consultant)
        response = self.client.get(reverse("counseling:my_students"))
        self.assertContains(response, "علی دانش‌آموز")
        self.client.force_login(self.other_consultant)
        self.assertNotContains(self.client.get(reverse("counseling:my_students")), "علی دانش‌آموز")

    def test_only_assigned_consultant_can_see_student_exam_performance(self):
        StudentConsultantAssignment.objects.create(
            student=self.student, consultant=self.consultant, assigned_by=self.admin_user
        )
        ExamSession.objects.create(
            user=self.student_user,
            total_questions=10,
            correct_count=8,
            wrong_count=2,
            percent=80,
            status=ExamSession.Status.DONE,
        )
        url = reverse("counseling:student_performance", args=[self.student.pk])

        self.client.force_login(self.consultant)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "80.0٪")
        self.assertContains(response, "نمودار عملکرد آزمون‌ها")

        self.client.force_login(self.other_consultant)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_private_ticket_is_moderated_then_sent_only_to_assigned_consultant(self):
        StudentConsultantAssignment.objects.create(
            student=self.student, consultant=self.consultant, assigned_by=self.admin_user
        )
        self.client.force_login(self.student_user)
        consultant_page = self.client.get(reverse("counseling:my_consultant"))
        self.assertContains(consultant_page, "سارا مشاور")
        response = self.client.post(
            reverse("counseling:private_ticket"),
            {"title": "برنامه آزمون", "content": "برای آزمون بعدی چه کار کنم؟"},
        )
        ticket = Ticket.objects.get()
        self.assertRedirects(response, reverse("ticketing:detail", args=[ticket.pk]))
        self.assertTrue(ticket.is_private_consultation)
        self.assertEqual(ticket.current_queue, TicketQueue.MODERATOR)
        self.assertEqual(ticket.current_assignee_user, self.consultant)
        first_message = ticket.messages.get()
        self.assertEqual(first_message.moderation_status, ModerationStatus.PENDING)

        self.client.force_login(self.other_consultant)
        self.assertEqual(self.client.get(reverse("ticketing:detail", args=[ticket.pk])).status_code, 403)
        self.client.force_login(self.consultant)
        self.assertEqual(self.client.get(reverse("ticketing:detail", args=[ticket.pk])).status_code, 403)

        self.client.force_login(self.moderator)
        self.assertEqual(self.client.get(reverse("ticketing:detail", args=[ticket.pk])).status_code, 200)
        self.client.post(
            reverse("ticketing:moderate_message", args=[first_message.pk]),
            {"decision": "approve", "note": "مناسب است"},
        )
        ticket.refresh_from_db()
        first_message.refresh_from_db()
        self.assertEqual(first_message.moderation_status, ModerationStatus.APPROVED)
        self.assertEqual(ticket.current_queue, TicketQueue.CONSULTANT)
        self.assertEqual(ticket.current_assignee_user, self.consultant)

        self.client.force_login(self.other_consultant)
        self.assertEqual(self.client.get(reverse("ticketing:detail", args=[ticket.pk])).status_code, 403)
        self.client.force_login(self.consultant)
        self.assertEqual(self.client.get(reverse("ticketing:detail", args=[ticket.pk])).status_code, 200)
        self.client.post(
            reverse("ticketing:add_message", args=[ticket.pk]),
            {"content": "پاسخ خصوصی مشاور"},
        )
        answer = ticket.messages.get(sender=self.consultant)
        self.assertEqual(answer.moderation_status, ModerationStatus.PENDING)

        self.client.force_login(self.student_user)
        self.assertNotContains(
            self.client.get(reverse("ticketing:detail", args=[ticket.pk])),
            "پاسخ خصوصی مشاور",
        )
        self.client.force_login(self.moderator)
        self.client.post(
            reverse("ticketing:moderate_message", args=[answer.pk]),
            {"decision": "approve"},
        )
        self.client.force_login(self.student_user)
        self.assertContains(
            self.client.get(reverse("ticketing:detail", args=[ticket.pk])),
            "پاسخ خصوصی مشاور",
        )

    def test_student_without_assignment_cannot_create_private_ticket(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("counseling:private_ticket"))
        self.assertEqual(response.status_code, 404)
