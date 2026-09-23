from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .decorators import role_required
from .models import User, UserRole


class RoleRequiredTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def decorated_view(self):
        @role_required(UserRole.CONSULTANT)
        def view(request):
            return HttpResponse("ok")

        return view

    def test_anonymous_user_is_redirected_to_login(self):
        request = self.factory.get("/protected/")
        request.user = AnonymousUser()
        response = self.decorated_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_wrong_role_gets_permission_denied(self):
        request = self.factory.get("/protected/")
        request.user = User(username="student", role=UserRole.STUDENT)
        with self.assertRaises(PermissionDenied):
            self.decorated_view()(request)

    def test_allowed_role_and_superuser_can_enter(self):
        request = self.factory.get("/protected/")
        request.user = User(username="consultant", role=UserRole.CONSULTANT)
        self.assertEqual(self.decorated_view()(request).status_code, 200)

        request.user = User(username="root", role=UserRole.STUDENT, is_superuser=True)
        self.assertEqual(self.decorated_view()(request).status_code, 200)


class LogoutTests(TestCase):
    def test_logout_works_with_post(self):
        user = User.objects.create_user(username="logout-user", password="pass12345")
        self.client.force_login(user)

        response = self.client.post(reverse("auth_module:logout"))

        self.assertRedirects(response, reverse("auth_module:login"))
        self.assertNotIn("_auth_user_id", self.client.session)


class UserBulkDeleteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-user",
            password="pass12345",
            role=UserRole.ADMIN,
            is_staff=True,
        )
        self.target = User.objects.create_user(
            username="delete-me",
            password="pass12345",
        )
        self.superuser = User.objects.create_superuser(
            username="protected-root",
            password="pass12345",
        )
        self.client.force_login(self.admin)

    def test_admin_can_delete_selected_user(self):
        with patch("django.db.models.query.QuerySet.delete") as delete:
            response = self.client.post(
                reverse("auth_module:user-bulk"),
                {"action": "delete", "scope": "selected", "user_ids": [self.target.pk]},
            )

        self.assertRedirects(response, reverse("auth_module:user-management"))
        delete.assert_called_once()

    def test_admin_cannot_delete_self_or_superuser(self):
        self.client.post(
            reverse("auth_module:user-bulk"),
            {
                "action": "delete",
                "scope": "selected",
                "user_ids": [self.admin.pk, self.superuser.pk],
            },
        )

        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())
