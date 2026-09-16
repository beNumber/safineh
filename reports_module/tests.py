from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_module.models import User, UserRole
from courses_module.models import Course


class PeopleActivityReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="system-admin",
            password="Pass123!",
            role=UserRole.ADMIN,
        )
        cls.consultant = User.objects.create_user(
            username="consultant-one",
            first_name="مشاور",
            last_name="نمونه",
            password="Pass123!",
            role=UserRole.CONSULTANT,
        )
        cls.student = User.objects.create_user(
            username="student-one",
            password="Pass123!",
            role=UserRole.STUDENT,
        )
        cls.current_course = Course.objects.create(
            title="دوره جدید",
            slug="new-course",
            description="توضیحات",
            author=cls.consultant,
        )
        cls.old_course = Course.objects.create(
            title="دوره قدیمی",
            slug="old-course",
            description="توضیحات",
            author=cls.consultant,
        )
        Course.objects.filter(pk=cls.old_course.pk).update(
            created_at=timezone.now() - timedelta(days=60)
        )

    def test_only_system_admin_can_open_report(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("reports_module:people_activity"))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports_module:people_activity"))
        self.assertEqual(response.status_code, 200)

    def test_period_changes_aggregate_course_count(self):
        self.client.force_login(self.admin)
        url = reverse("reports_module:people_activity")

        response = self.client.get(url, {"section": "consultants", "period": "30"})
        consultant = response.context["page_obj"].object_list[0]
        self.assertEqual(consultant.courses_count, 1)

        response = self.client.get(url, {"section": "consultants", "period": "all"})
        consultant = response.context["page_obj"].object_list[0]
        self.assertEqual(consultant.courses_count, 2)

    def test_superuser_can_open_report_regardless_of_role(self):
        root = User.objects.create_superuser(
            username="root-report",
            password="Pass123!",
            role=UserRole.STUDENT,
        )
        self.client.force_login(root)
        response = self.client.get(reverse("reports_module:people_activity"))
        self.assertEqual(response.status_code, 200)

    def test_all_three_role_sections_render(self):
        self.client.force_login(self.admin)
        url = reverse("reports_module:people_activity")
        for section in ("consultants", "trustees", "students"):
            with self.subTest(section=section):
                response = self.client.get(url, {"section": section})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["active_section"], section)
