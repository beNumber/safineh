from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_module.models import UserRole

from .models import ApprovalStatus, Course, CourseEnrollment, CourseRating

User = get_user_model()


class CourseWorkflowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="student", password="Pass123!", role=UserRole.STUDENT)
        self.consultant = User.objects.create_user(username="consultant", password="Pass123!", role=UserRole.CONSULTANT)
        self.trustee = User.objects.create_user(username="trustee", password="Pass123!", role=UserRole.PROVINCE_TRUSTEE)
        self.course = Course.objects.create(
            title="دوره آزمایشی",
            slug="test-course",
            author=self.consultant,
            description="توضیحات دوره",
            start_date=timezone.now() - timedelta(days=1),
            approval_status=ApprovalStatus.PENDING,
        )

    def test_pending_course_is_not_visible_to_student(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:course_list"))
        self.assertNotContains(response, self.course.title)
        detail = self.client.get(reverse("courses_module:course_detail", args=[self.course.slug]))
        self.assertEqual(detail.status_code, 404)

    def test_only_consultant_can_open_create_page(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("courses_module:course_create")).status_code, 403)
        self.client.force_login(self.consultant)
        self.assertEqual(self.client.get(reverse("courses_module:course_create")).status_code, 200)

    def test_consultant_trustee_and_admin_can_edit_course(self):
        for user in (self.consultant, self.trustee):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("courses_module:course_edit", args=[self.course.pk])).status_code, 200)
        admin = User.objects.create_user(username="editor-admin", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("courses_module:course_edit", args=[self.course.pk])).status_code, 200)

    def test_trustee_queue_is_available_from_my_courses(self):
        self.client.force_login(self.trustee)
        response = self.client.get(reverse("courses_module:my_courses"))
        self.assertContains(response, "دوره‌های تأییدنشده")
        self.assertContains(response, self.course.title)

    def test_trustee_can_approve_and_publish_course(self):
        self.client.force_login(self.trustee)
        response = self.client.post(reverse("courses_module:course_review", args=[self.course.pk]), {"action": "approve"})
        self.assertRedirects(response, reverse("courses_module:review_list"))
        self.course.refresh_from_db()
        self.assertEqual(self.course.approval_status, ApprovalStatus.APPROVED)
        self.assertEqual(self.course.reviewed_by, self.trustee)
        self.assertTrue(self.course.is_visible_now)

    def test_student_enrollment_and_rating_are_unique(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.student)
        enroll_url = reverse("courses_module:course_enroll", args=[self.course.slug])
        self.client.post(enroll_url)
        self.client.post(enroll_url)
        self.assertEqual(CourseEnrollment.objects.filter(course=self.course, student=self.student).count(), 1)
        rate_url = reverse("courses_module:course_rate", args=[self.course.slug])
        self.client.post(rate_url, {"rating": 4})
        self.client.post(rate_url, {"rating": 5})
        self.assertEqual(CourseRating.objects.get(course=self.course, student=self.student).value, 5)

    def test_my_courses_only_contains_enrolled_courses(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        other = Course.objects.create(
            title="دوره دیگر", slug="other", author=self.consultant, description="...",
            start_date=timezone.now() - timedelta(days=1), approval_status=ApprovalStatus.APPROVED,
        )
        CourseEnrollment.objects.create(course=self.course, student=self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:my_courses"))
        self.assertContains(response, self.course.title)
        self.assertNotContains(response, other.title)

    def test_approved_course_detail_renders_for_student(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:course_detail", args=[self.course.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)

    def test_persian_slug_is_supported(self):
        self.course.slug = "دوره-آزمایشی-فارسی"
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["slug", "approval_status"])
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:course_detail", args=[self.course.slug]))
        self.assertEqual(response.status_code, 200)

    def test_login_starts_at_dashboard(self):
        response = self.client.post(reverse("auth_module:login"), {"username": "consultant", "password": "Pass123!"})
        self.assertRedirects(response, reverse("dashboard"))

    def test_non_student_cannot_enroll(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.consultant)
        response = self.client.post(reverse("courses_module:course_enroll", args=[self.course.slug]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CourseEnrollment.objects.filter(course=self.course, student=self.consultant).exists())

    def test_only_admin_can_close_or_delete_course(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.trustee)
        self.assertEqual(self.client.post(reverse("courses_module:course_close", args=[self.course.pk])).status_code, 403)
        admin = User.objects.create_user(username="admin", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        response = self.client.post(reverse("courses_module:course_close", args=[self.course.pk]))
        self.assertRedirects(response, reverse("courses_module:course_detail", args=[self.course.slug]))
        self.course.refresh_from_db()
        self.assertFalse(self.course.is_active)
        self.client.post(reverse("courses_module:course_delete", args=[self.course.pk]))
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())
