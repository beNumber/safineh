from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_module.models import User, UserRole
from .models import OnlineClass


class ClassroomAccessTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="student-class", password="pass", role=UserRole.STUDENT)
        self.consultant = User.objects.create_user(username="consultant-class", password="pass", role=UserRole.CONSULTANT)
        self.admin = User.objects.create_user(username="admin-class", password="pass", role=UserRole.ADMIN, is_staff=True)
        now = timezone.now()
        self.online_class = OnlineClass.objects.create(title="کلاس تست", meeting_url="https://example.com/class", starts_at=now, ends_at=now + timedelta(hours=1), created_by=self.admin)

    def test_student_and_consultant_can_open_list_only(self):
        for user in (self.student, self.consultant):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("classroom_module:list")).status_code, 200)
            self.assertEqual(self.client.get(reverse("classroom_module:create")).status_code, 403)

    def test_admin_can_open_management_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("classroom_module:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("classroom_module:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("classroom_module:edit", args=[self.online_class.pk])).status_code, 200)

    def test_anonymous_user_is_redirected(self):
        self.assertEqual(self.client.get(reverse("classroom_module:list")).status_code, 302)
