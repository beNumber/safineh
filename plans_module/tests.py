from datetime import timedelta

import jdatetime

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from auth_module.models import Consultant, Student, User, UserRole
from users_module.models import Access, FieldOfStudy, Grade, Province, School, Subject

from .models import ActivityType, PlanCompletion, PlanEntry, PlanSource
from .services import current_week_start, visible_students_for


class PlansModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        province = Province.objects.create(name="hormozgan")
        school = School.objects.create(name="مدرسه برنامه", province=province)
        grade = Grade.objects.create(title="دهم", school=school)
        cls.math_field = FieldOfStudy.objects.create(title="ریاضی", grade=grade)
        cls.humanities_field = FieldOfStudy.objects.create(title="انسانی", grade=grade)
        cls.math = Subject.objects.create(title="حسابان", field=cls.math_field)
        cls.physics = Subject.objects.create(title="فیزیک", field=cls.math_field)
        cls.literature = Subject.objects.create(title="علوم و فنون", field=cls.humanities_field)

        cls.student_user = User.objects.create_user(
            username="plan-student", password="pass12345", role=UserRole.STUDENT
        )
        cls.student = Student.objects.create(user=cls.student_user, field=cls.math_field)
        cls.second_student_user = User.objects.create_user(
            username="second-student", password="pass12345", role=UserRole.STUDENT
        )
        cls.second_student = Student.objects.create(user=cls.second_student_user, field=cls.math_field)
        cls.other_student_user = User.objects.create_user(
            username="humanities-student", password="pass12345", role=UserRole.STUDENT
        )
        cls.other_student = Student.objects.create(user=cls.other_student_user, field=cls.humanities_field)

        cls.consultant_user = User.objects.create_user(
            username="plan-consultant", password="pass12345", role=UserRole.CONSULTANT
        )
        consultant = Consultant.objects.create(consultant=cls.consultant_user)
        access = Access.objects.create(name="ticket", subject=cls.math)
        consultant.accesses.add(access)

        cls.admin_user = User.objects.create_user(
            username="plan-admin", password="pass12345", role=UserRole.ADMIN
        )

    def plan_payload(self, **overrides):
        scheduled_date = current_week_start()
        payload = {
            "activity_type": ActivityType.SUBJECT,
            "subject": self.math.pk,
            "title": "",
            "scheduled_date": jdatetime.date.fromgregorian(date=scheduled_date).strftime("%Y/%m/%d"),
            "start_hour": 8,
            "end_hour": 10,
            "color": "blue",
            "notes": "حل ۲۰ تست",
        }
        payload.update(overrides)
        return payload

    def test_student_can_create_plan_only_with_own_field_subject(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("plans_module:board"), self.plan_payload())
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"week={current_week_start().isoformat()}", response.url)
        entry = PlanEntry.objects.get()
        self.assertEqual(entry.student, self.student)
        self.assertEqual(entry.subject, self.math)
        self.assertEqual(entry.source, PlanSource.SELF)

        response = self.client.post(
            reverse("plans_module:board"),
            self.plan_payload(subject=self.literature.pk, start_hour=10, end_hour=11),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlanEntry.objects.count(), 1)

    def test_overlapping_entries_are_rejected(self):
        PlanEntry.objects.create(
            student=self.student,
            subject=self.math,
            activity_type=ActivityType.SUBJECT,
            scheduled_date=current_week_start(),
            weekday=0,
            start_hour=9,
            end_hour=11,
            assigned_by=self.student_user,
        )
        overlapping = PlanEntry(
            student=self.student,
            subject=self.physics,
            activity_type=ActivityType.SUBJECT,
            scheduled_date=current_week_start(),
            weekday=0,
            start_hour=10,
            end_hour=12,
            assigned_by=self.student_user,
        )
        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_consultant_sees_all_active_students_for_plan_assignment(self):
        visible = visible_students_for(self.consultant_user)
        self.assertIn(self.student, visible)
        self.assertIn(self.second_student, visible)
        self.assertIn(self.other_student, visible)

    def test_consultant_cannot_assign_subject_from_another_students_field(self):
        self.client.force_login(self.consultant_user)
        response = self.client.post(
            reverse("plans_module:board"),
            self.plan_payload(target_students=[self.other_student.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlanEntry.objects.exists())

    def test_consultant_can_assign_one_plan_to_multiple_students(self):
        self.client.force_login(self.consultant_user)
        payload = self.plan_payload(
            target_students=[self.student.pk, self.second_student.pk], color="violet"
        )
        response = self.client.post(reverse("plans_module:board"), payload)
        self.assertEqual(response.status_code, 302)
        entries = PlanEntry.objects.order_by("student_id")
        self.assertEqual(entries.count(), 2)
        self.assertEqual(len(set(entries.values_list("batch_id", flat=True))), 1)
        self.assertTrue(all(entry.source == PlanSource.CONSULTANT for entry in entries))

    def test_admin_can_assign_non_subject_activity_to_all_students(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("plans_module:board"),
            self.plan_payload(
                activity_type=ActivityType.LEARNING,
                subject="",
                title="جلسه مهارت مطالعه",
                apply_to_all="on",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PlanEntry.objects.count(), 3)
        self.assertEqual(PlanEntry.objects.filter(source=PlanSource.ADMIN).count(), 3)

    def test_student_can_toggle_weekly_completion(self):
        entry = PlanEntry.objects.create(
            student=self.student,
            subject=self.math,
            activity_type=ActivityType.SUBJECT,
            scheduled_date=current_week_start(),
            weekday=0,
            start_hour=8,
            end_hour=9,
            assigned_by=self.consultant_user,
            source=PlanSource.CONSULTANT,
        )
        self.client.force_login(self.student_user)
        url = reverse("plans_module:toggle_completion", args=[entry.pk])
        self.client.post(url)
        self.assertTrue(
            PlanCompletion.objects.filter(entry=entry, week_start=current_week_start()).exists()
        )
        self.client.post(url)
        self.assertFalse(PlanCompletion.objects.filter(entry=entry).exists())

    def test_student_cannot_edit_consultant_entry(self):
        entry = PlanEntry.objects.create(
            student=self.student,
            subject=self.math,
            activity_type=ActivityType.SUBJECT,
            scheduled_date=current_week_start() + timedelta(days=1),
            weekday=1,
            start_hour=8,
            end_hour=9,
            assigned_by=self.consultant_user,
            source=PlanSource.CONSULTANT,
        )
        self.client.force_login(self.student_user)
        self.assertEqual(
            self.client.get(reverse("plans_module:edit", args=[entry.pk])).status_code, 403
        )

    def test_board_uses_fixed_grid_rows_and_jalali_calendar(self):
        PlanEntry.objects.create(
            student=self.student,
            subject=self.math,
            activity_type=ActivityType.SUBJECT,
            scheduled_date=current_week_start(),
            weekday=0,
            start_hour=8,
            end_hour=9,
            assigned_by=self.student_user,
        )
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("plans_module:board"))
        self.assertContains(response, "تقویم برنامه‌ریزی")
        self.assertContains(response, "grid-row: 2;")
        self.assertContains(response, "هفته جاری")
