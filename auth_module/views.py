import hashlib
import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from .forms import (
    ForgotPasswordRequestForm,
    LoginForm,
    SetNewPasswordForm,
    VerifyOTPForm,
)


User = get_user_model()


# ---------------------------------------------------------
# جایگزین این تابع با API واقعی پیامک خودت کن
# ---------------------------------------------------------
def send_sms_code(mobile: str, code: str) -> bool:
    """
    این تابع باید به سرویس پیامکی متصل شود.

    mobile: شماره موبایل مقصد
    code: کد شش رقمی تولیدشده

    خروجی:
        True  -> ارسال موفق
        False -> خطا در ارسال
    """

    # TODO: اتصال به API سرویس پیامکی
    #
    # مثال:
    #
    # response = requests.post(
    #     "SMS_PROVIDER_API_URL",
    #     json={
    #         "mobile": mobile,
    #         "message": f"کد بازیابی رمز عبور شما: {code}",
    #     },
    #     timeout=10,
    # )
    #
    # return response.ok

    print(f"[SMS PLACEHOLDER] Mobile: {mobile} | Code: {code}")

    return True


def hash_otp(code: str) -> str:
    """
    برای ذخیره‌سازی امن‌تر، خود کد داخل session ذخیره نمی‌شود.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def normalize_mobile(value: str) -> str:
    """
    تبدیل اعداد فارسی و عربی به انگلیسی.
    """
    translation_table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    return value.translate(translation_table).strip()


# ---------------------------------------------------------
# ورود
# ---------------------------------------------------------

class UserLoginView(LoginView):
    template_name = "auth_module/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
    next_page = reverse_lazy("dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)

        user = self.request.user
        full_name = user.get_full_name().strip() or user.username

        messages.success(
            self.request,
            f"{full_name} عزیز، خوش آمدید. ورود شما با موفقیت انجام شد.",
        )

        return response


# ---------------------------------------------------------
# مرحله اول: دریافت نام کاربری و شماره موبایل
# ---------------------------------------------------------

def forgot_password_request(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = ForgotPasswordRequestForm(request.POST)

        if form.is_valid():
            user = form.user

            code = f"{secrets.randbelow(1_000_000):06d}"

            # پاک‌سازی اطلاعات قبلی بازیابی
            request.session.pop("password_reset_user_id", None)
            request.session.pop("password_reset_otp_hash", None)
            request.session.pop("password_reset_otp_expires_at", None)
            request.session.pop("password_reset_otp_attempts", None)
            request.session.pop("password_reset_verified", None)

            request.session["password_reset_user_id"] = user.pk
            request.session["password_reset_otp_hash"] = hash_otp(code)
            request.session["password_reset_otp_expires_at"] = (
                timezone.now() + timedelta(minutes=3)
            ).isoformat()
            request.session["password_reset_otp_attempts"] = 0

            request.session.set_expiry(10 * 60)

            sms_sent = send_sms_code(
                mobile=user.mobile,
                code=code,
            )

            if not sms_sent:
                request.session.flush()

                messages.error(
                    request,
                    "ارسال کد تأیید با خطا مواجه شد. دوباره تلاش کنید.",
                )

                return redirect("auth_module:forgot-password")

            messages.success(
                request,
                "کد تأیید به شماره موبایل شما ارسال شد.",
            )

            return redirect("auth_module:verify-otp")

    else:
        form = ForgotPasswordRequestForm()

    return render(
        request,
        "auth_module/forgot_password.html",
        {"form": form},
    )


# ---------------------------------------------------------
# مرحله دوم: بررسی کد پیامکی
# ---------------------------------------------------------

def verify_password_reset_otp(request):
    user_id = request.session.get("password_reset_user_id")
    otp_hash = request.session.get("password_reset_otp_hash")
    expires_at = request.session.get("password_reset_otp_expires_at")
    attempts = request.session.get("password_reset_otp_attempts", 0)

    if not user_id or not otp_hash or not expires_at:
        messages.error(
            request,
            "فرآیند بازیابی رمز عبور منقضی شده است.",
        )

        return redirect("auth_module:forgot-password")

    try:
        expires_datetime = timezone.datetime.fromisoformat(expires_at)

        if timezone.is_naive(expires_datetime):
            expires_datetime = timezone.make_aware(expires_datetime)

    except ValueError:
        request.session.flush()

        messages.error(
            request,
            "اطلاعات بازیابی نامعتبر است.",
        )

        return redirect("auth_module:forgot-password")

    if timezone.now() > expires_datetime:
        request.session.flush()

        messages.error(
            request,
            "کد تأیید منقضی شده است.",
        )

        return redirect("auth_module:forgot-password")

    if attempts >= 5:
        request.session.flush()

        messages.error(
            request,
            "تعداد تلاش‌های مجاز به پایان رسیده است.",
        )

        return redirect("auth_module:forgot-password")

    if request.method == "POST":
        form = VerifyOTPForm(request.POST)

        if form.is_valid():
            submitted_code = form.cleaned_data["code"]

            request.session["password_reset_otp_attempts"] = attempts + 1

            if hash_otp(submitted_code) != otp_hash:
                form.add_error(
                    "code",
                    "کد واردشده صحیح نیست.",
                )
            else:
                request.session["password_reset_verified"] = True

                messages.success(
                    request,
                    "کد تأیید شد. اکنون رمز عبور جدید خود را وارد کنید.",
                )

                return redirect("auth_module:set-new-password")

    else:
        form = VerifyOTPForm()

    return render(
        request,
        "auth_module/verify_otp.html",
        {
            "form": form,
            "remaining_attempts": 5 - attempts,
        },
    )


# ---------------------------------------------------------
# مرحله سوم: تعیین رمز عبور جدید
# ---------------------------------------------------------

def set_new_password(request):
    user_id = request.session.get("password_reset_user_id")
    is_verified = request.session.get("password_reset_verified", False)

    if not user_id or not is_verified:
        messages.error(
            request,
            "ابتدا باید کد تأیید را وارد کنید.",
        )

        return redirect("auth_module:forgot-password")

    try:
        user = User.objects.get(
            pk=user_id,
            is_active=True,
        )
    except User.DoesNotExist:
        request.session.flush()

        messages.error(
            request,
            "کاربر موردنظر پیدا نشد.",
        )

        return redirect("auth_module:forgot-password")

    if request.method == "POST":
        form = SetNewPasswordForm(request.POST)

        if form.is_valid():
            user.set_password(
                form.cleaned_data["new_password"]
            )
            user.save(update_fields=["password"])

            # پایان کامل فرآیند بازیابی
            request.session.pop("password_reset_user_id", None)
            request.session.pop("password_reset_otp_hash", None)
            request.session.pop("password_reset_otp_expires_at", None)
            request.session.pop("password_reset_otp_attempts", None)
            request.session.pop("password_reset_verified", None)

            messages.success(
                request,
                "رمز عبور شما با موفقیت تغییر کرد. اکنون وارد شوید.",
            )

            return redirect("auth_module:login")

    else:
        form = SetNewPasswordForm()

    return render(
        request,
        "auth_module/reset_password.html",
        {
            "form": form,
        },
    )
