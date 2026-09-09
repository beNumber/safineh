from django.test import TestCase
from django.urls import reverse

from auth_module.models import Consultant, ProvinceTrustee, Student, User, UserRole
from users_module.models import FieldOfStudy, Grade, Province, School, Subject

from .models import (
    ModerationStatus,
    Ticket,
    TicketAuditLog,
    TicketMessage,
    TicketQueue,
    TicketStatus,
    TicketType,
)
from .services import consultant_can_access, visible_tickets_for


class TicketingFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province = Province.objects.create(name="hormozgan")
        cls.other_province = Province.objects.create(name="kerman")
        cls.school = School.objects.create(name="مدرسه یک", province=cls.province)
        cls.grade = Grade.objects.create(title="دهم", code="g10", school=cls.school)
        cls.field = FieldOfStudy.objects.create(title="ریاضی", code="math", grade=cls.grade)
        cls.subject = Subject.objects.create(title="حسابان", code="calculus", field=cls.field)

        cls.student_user = User.objects.create_user(
            username="student", password="pass12345", role=UserRole.STUDENT, gender="MALE"
        )
        cls.student = Student.objects.create(user=cls.student_user, field=cls.field)
        cls.other_student_user = User.objects.create_user(
            username="other-student", password="pass12345", role=UserRole.STUDENT
        )
        cls.other_student = Student.objects.create(user=cls.other_student_user, field=cls.field)
        cls.consultant_user = User.objects.create_user(
            username="consultant", password="pass12345", role=UserRole.CONSULTANT,
            first_name="مشاور", last_name="آزمایشی",
        )
        cls.scope = Consultant.objects.create(
            consultant=cls.consultant_user,
            province=cls.province,
            subject=cls.subject,
            can_answer_tickets=True,
        )
        cls.psychologist_user = User.objects.create_user(
            username="psychologist", password="pass12345", role=UserRole.CONSULTANT
        )
        Consultant.objects.create(
            consultant=cls.psychologist_user,
            province=cls.province,
            can_answer_tickets=True,
            can_answer_psychology=True,
        )
        cls.trustee_user = User.objects.create_user(
            username="trustee", password="pass12345", role=UserRole.PROVINCE_TRUSTEE
        )
        ProvinceTrustee.objects.create(user=cls.trustee_user, province=cls.province)
        cls.other_trustee = User.objects.create_user(
            username="other-trustee", password="pass12345", role=UserRole.PROVINCE_TRUSTEE
        )
        ProvinceTrustee.objects.create(user=cls.other_trustee, province=cls.other_province)
        cls.moderator = User.objects.create_user(
            username="moderator", password="pass12345", role=UserRole.CONTENT_MODERATOR,
            first_name="ناظر", last_name="محتوا",
        )

    def create_ticket(self, ticket_type=TicketType.LESSON, subject=True):
        ticket = Ticket.objects.create(
            title="پرسش آزمایشی",
            student=self.student,
            ticket_type=ticket_type,
            subject=self.subject if subject else None,
        )
        message = TicketMessage.objects.create(
            ticket=ticket, sender=self.student_user, content="متن پرسش"
        )
        return ticket, message

    def test_student_creates_ticket_in_moderator_queue(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse("ticketing:create"),
            {
                "title": "سؤال حسابان",
                "ticket_type": TicketType.LESSON,
                "subject": self.subject.pk,
                "content": "چطور این مسئله را حل کنم؟",
            },
        )
        ticket = Ticket.objects.get(title="سؤال حسابان")
        self.assertRedirects(response, reverse("ticketing:detail", args=[ticket.pk]))
        self.assertEqual(ticket.current_queue, TicketQueue.MODERATOR)
        self.assertEqual(ticket.status, TicketStatus.PENDING_APPROVAL)
        self.assertEqual(ticket.messages.get().moderation_status, ModerationStatus.PENDING)

    def test_moderator_approval_routes_lesson_to_matching_consultant_queue(self):
        ticket, item = self.create_ticket()
        self.client.force_login(self.moderator)
        self.client.post(
            reverse("ticketing:moderate_message", args=[item.pk]),
            {"decision": "approve", "note": "مناسب است"},
        )
        ticket.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(item.moderation_status, ModerationStatus.APPROVED)
        self.assertEqual(ticket.current_queue, TicketQueue.CONSULTANT)
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertTrue(consultant_can_access(self.consultant_user, ticket))

    def test_technical_ticket_is_visible_only_to_its_province_trustee(self):
        ticket, item = self.create_ticket(TicketType.TECHNICAL, subject=False)
        self.client.force_login(self.moderator)
        self.client.post(
            reverse("ticketing:moderate_message", args=[item.pk]),
            {"decision": "approve"},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.current_queue, TicketQueue.TRUSTEE)
        self.assertIn(ticket, visible_tickets_for(self.trustee_user))
        self.assertNotIn(ticket, visible_tickets_for(self.other_trustee))

    def test_consultant_answer_is_hidden_until_moderator_approval(self):
        ticket, first = self.create_ticket()
        first.moderation_status = ModerationStatus.APPROVED
        first.is_approved_by_moderator = True
        first.save()
        ticket.current_queue = TicketQueue.CONSULTANT
        ticket.status = TicketStatus.OPEN
        ticket.save()

        self.client.force_login(self.consultant_user)
        self.client.post(
            reverse("ticketing:add_message", args=[ticket.pk]), {"content": "پاسخ مشاور"}
        )
        answer = ticket.messages.get(sender=self.consultant_user)
        self.assertEqual(answer.moderation_status, ModerationStatus.PENDING)

        self.client.force_login(self.student_user)
        response = self.client.get(reverse("ticketing:detail", args=[ticket.pk]))
        self.assertNotContains(response, "پاسخ مشاور")

        self.client.force_login(self.moderator)
        self.client.post(
            reverse("ticketing:moderate_message", args=[answer.pk]),
            {"decision": "approve"},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)
        self.client.force_login(self.student_user)
        self.assertContains(
            self.client.get(reverse("ticketing:detail", args=[ticket.pk])), "پاسخ مشاور"
        )

    def test_referral_and_subject_change_are_audited(self):
        ticket, item = self.create_ticket()
        item.moderation_status = ModerationStatus.APPROVED
        item.is_approved_by_moderator = True
        item.save()
        ticket.current_queue = TicketQueue.CONSULTANT
        ticket.status = TicketStatus.OPEN
        ticket.save()

        self.client.force_login(self.consultant_user)
        self.client.post(
            reverse("ticketing:refer", args=[ticket.pk]),
            {"queue": TicketQueue.TRUSTEE, "assignee": self.trustee_user.pk, "note": "درس اشتباه است"},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.current_queue, TicketQueue.TRUSTEE)
        self.assertTrue(ticket.logs.filter(action=TicketAuditLog.Action.REFERRED).exists())

        self.client.force_login(self.trustee_user)
        self.client.post(
            reverse("ticketing:edit", args=[ticket.pk]),
            {"ticket_type": TicketType.PSYCHOLOGY, "subject": "", "status": TicketStatus.IN_PROGRESS},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.ticket_type, TicketType.PSYCHOLOGY)
        self.assertIsNone(ticket.subject)
        self.assertTrue(ticket.logs.filter(action=TicketAuditLog.Action.TYPE_CHANGED).exists())
        self.assertTrue(ticket.logs.filter(action=TicketAuditLog.Action.SUBJECT_CHANGED).exists())

    def test_student_cannot_view_another_students_ticket(self):
        ticket, _ = self.create_ticket()
        self.client.force_login(self.other_student_user)
        response = self.client.get(reverse("ticketing:detail", args=[ticket.pk]))
        self.assertEqual(response.status_code, 403)

    def test_consultant_cannot_see_student_academic_location_details(self):
        ticket, item = self.create_ticket()
        item.moderation_status = ModerationStatus.APPROVED
        item.is_approved_by_moderator = True
        item.save()
        ticket.current_queue = TicketQueue.CONSULTANT
        ticket.status = TicketStatus.OPEN
        ticket.save()

        self.client.force_login(self.consultant_user)
        response = self.client.get(reverse("ticketing:detail", args=[ticket.pk]))
        self.assertNotContains(response, "مدرسه یک")
        self.assertNotContains(response, "اطلاعات تیکت")

    def test_trustee_sees_persian_province_display_name_and_full_actor_name(self):
        ticket, item = self.create_ticket(TicketType.TECHNICAL, subject=False)
        ticket.current_queue = TicketQueue.TRUSTEE
        ticket.status = TicketStatus.OPEN
        ticket.save()
        TicketAuditLog.objects.create(
            ticket=ticket,
            actor=self.moderator,
            action=TicketAuditLog.Action.APPROVED,
        )

        self.client.force_login(self.trustee_user)
        response = self.client.get(reverse("ticketing:detail", args=[ticket.pk]))
        self.assertContains(response, "هرمزگان")
        self.assertContains(response, "ناظر محتوا")
        self.assertNotContains(response, "moderator —")
