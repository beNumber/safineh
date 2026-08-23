from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    UserLoginView,
    forgot_password_request,
    set_new_password,
    verify_password_reset_otp,
)


app_name = "auth_module"


urlpatterns = [
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
