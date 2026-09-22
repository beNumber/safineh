from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    UserLoginView,
    forgot_password_request,
    set_new_password,
    verify_password_reset_otp,
    user_management, user_import, user_template, user_bulk_action,
)


app_name = "auth_module"


urlpatterns = [
    path("users/", user_management, name="user-management"),
    path("users/import/", user_import, name="user-import"),
    path("users/template/", user_template, name="user-template"),
    path("users/bulk/", user_bulk_action, name="user-bulk"),
    path(
        "login/",
        UserLoginView.as_view(),
        name="login",
    ),

    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),

    path(
        "forgot-password/",
        forgot_password_request,
        name="forgot-password",
    ),

    path(
        "forgot-password/verify/",
        verify_password_reset_otp,
        name="verify-otp",
    ),

    path(
        "forgot-password/new-password/",
        set_new_password,
        name="set-new-password",
    ),
]
