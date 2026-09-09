from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

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
