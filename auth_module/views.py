import hashlib
import secrets
from urllib.parse import parse_qs
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from .forms import (
    ForgotPasswordRequestForm,
    LoginForm,
    SetNewPasswordForm,
    VerifyOTPForm,
    UserSpreadsheetForm,
)
from .decorators import staff_admin_required
from .models import Student, UserRole
from .user_management import build_user_template_xlsx, import_users, shift_student_grade
from users_module.models import FieldOfStudy, Grade, Province, School


User = get_user_model()


def _login_greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return "صبح بخیر"
    if hour < 17:
        return "ظهر بخیر"
    if hour < 21:
        return "عصر بخیر"
    return "شب بخیر"


def _filtered_users(request):
    users = User.objects.all().order_by("-date_joined")
    query = request.GET.get("q", "").strip()
    if query:
        users = users.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query))
    if request.GET.get("role"):
        users = users.filter(role=request.GET["role"])
    if request.GET.get("status") == "active":
        users = users.filter(is_active=True)
    elif request.GET.get("status") == "inactive":
        users = users.filter(is_active=False)
    if request.GET.get("province"):
        users = users.filter(student_profiles__field__grade__school__province_id=request.GET["province"])
    if request.GET.get("city"):
        users = users.filter(student_profiles__field__grade__school_id=request.GET["city"])
    if request.GET.get("grade"):
        users = users.filter(student_profiles__field__grade_id=request.GET["grade"])
    if request.GET.get("field"):
        users = users.filter(student_profiles__field_id=request.GET["field"])
    return users.distinct()


@staff_admin_required
def user_management(request):
    import_results = request.session.pop("user_import_results", None)
    users = _filtered_users(request).select_related().prefetch_related("student_profiles__field__grade__school__province")
    paginator = Paginator(users, 24)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "auth_module/user_management.html", {
        "page_obj": page,
        "users_count": User.objects.count(),
        "active_count": User.objects.filter(is_active=True).count(),
        "student_count": User.objects.filter(role=UserRole.STUDENT).count(),
        "staff_count": User.objects.exclude(role=UserRole.STUDENT).count(),
        "roles": UserRole.choices,
        "provinces": Province.objects.all(), "cities": School.objects.select_related("province"),
        "grades": Grade.objects.filter(is_active=True).select_related("school"),
        "fields": FieldOfStudy.objects.filter(is_active=True).select_related("grade"),
        "upload_form": UserSpreadsheetForm(), "import_results": import_results,
    })


@staff_admin_required
def user_import(request):
    if request.method != "POST":
        return redirect("auth_module:user-management")
    form = UserSpreadsheetForm(request.POST, request.FILES)
    if form.is_valid():
        results = import_users(form.cleaned_data["file"])
        request.session["user_import_results"] = results[:200]
        success = sum(item["ok"] for item in results)
        messages.success(request, f"پردازش فایل تمام شد: {success} کاربر ساخته شد و {len(results) - success} ردیف خطا داشت.")
    else:
        messages.error(request, "فایل انتخاب‌شده معتبر نیست.")
    return redirect("auth_module:user-management")


@staff_admin_required
def user_template(request):
    workbook = build_user_template_xlsx()
    response = HttpResponse(
        workbook.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="fanous-members-template.xlsx"'
    return response


@staff_admin_required
def user_bulk_action(request):
    if request.method != "POST":
        return redirect("auth_module:user-management")
    action = request.POST.get("action")
    if request.POST.get("scope") == "filtered":
        query = request.POST.get("filter_query", "")
        mutable = request.GET.copy()
        mutable.update({key: values[-1] for key, values in parse_qs(query).items()})
        original = request.GET; request.GET = mutable
        users = _filtered_users(request)
        request.GET = original
    else:
        ids = [value for value in request.POST.getlist("user_ids") if value.isdigit()]
        users = User.objects.filter(pk__in=ids)
    users = users.exclude(pk=request.user.pk).exclude(is_superuser=True)
    affected = 0
    if action in ("activate", "deactivate"):
        affected = users.update(is_active=action == "activate")
    elif action == "delete":
        affected = users.count()
        users.delete()
    elif action in ("grade_up", "grade_down"):
        students = Student.objects.filter(user__in=users).select_related("field__grade__school")
        direction = 1 if action == "grade_up" else -1
        affected = sum(1 for student in students if shift_student_grade(student, direction))
    else:
        messages.error(request, "عملیات انتخاب‌شده معتبر نیست.")
        return redirect("auth_module:user-management")
    messages.success(request, f"عملیات برای {affected} کاربر انجام شد.")
    return redirect("auth_module:user-management")


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

    def get_success_url(self):
        """After a normal login always open the dashboard first.

        Course pages can still be opened explicitly from the sidebar.  We keep
        Django's ``next`` behaviour only when another protected flow explicitly
        supplied it; a plain login never starts inside the courses module.
        """
        return str(reverse_lazy("dashboard"))

    def form_valid(self, form):
        response = super().form_valid(form)

        user = self.request.user
        full_name = user.get_full_name().strip() or user.username

        messages.success(
            self.request,
            f"{_login_greeting()} {full_name} عزیز؛ به فانوس خوش آمدید.",
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
