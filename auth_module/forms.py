from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="نام کاربری",
        widget=forms.TextInput(
            attrs={
                "class": (
                    "w-full rounded-xl border border-slate-200 "
                    "bg-slate-50 px-4 py-3 text-sm text-slate-700 "
                    "outline-none transition "
                    "focus:border-blue-500 focus:bg-white "
                    "focus:ring-4 focus:ring-blue-100"
                ),
                "placeholder": "نام کاربری خود را وارد کنید",
                "autocomplete": "username",
            }
        ),
    )

    password = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput(
            attrs={
                "class": (
                    "w-full rounded-xl border border-slate-200 "
                    "bg-slate-50 px-4 py-3 text-sm text-slate-700 "
                    "outline-none transition "
                    "focus:border-blue-500 focus:bg-white "
                    "focus:ring-4 focus:ring-blue-100"
                ),
                "placeholder": "رمز عبور خود را وارد کنید",
                "autocomplete": "current-password",
            }
        ),
    )


User = get_user_model()


mobile_validator = RegexValidator(
    regex=r"^09\d{9}$",
    message="شماره موبایل باید با 09 شروع شده و 11 رقم باشد.",
)


class ForgotPasswordRequestForm(forms.Form):
    username = forms.CharField(
        label="نام کاربری",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": (
                    "w-full rounded-xl border border-slate-200 "
                    "bg-slate-50 px-4 py-3 text-sm text-slate-700 "
                    "outline-none transition focus:border-blue-500 "
                    "focus:bg-white focus:ring-4 focus:ring-blue-100"
                ),
                "placeholder": "نام کاربری خود را وارد کنید",
                "autocomplete": "username",
            }
        ),
    )

    mobile = forms.CharField(
        label="شماره موبایل",
        max_length=11,
        validators=[mobile_validator],
        widget=forms.TextInput(
            attrs={
                "class": (
                    "w-full rounded-xl border border-slate-200 "
                    "bg-slate-50 px-4 py-3 text-sm text-slate-700 "
                    "outline-none transition focus:border-blue-500 "
                    "focus:bg-white focus:ring-4 focus:ring-blue-100"
                ),
                "placeholder": "09123456789",
                "inputmode": "numeric",
                "dir": "ltr",
                "autocomplete": "tel",
            }
        ),
    )

    def clean_mobile(self):
        mobile = self.cleaned_data["mobile"].strip()
        return mobile.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))

    def clean(self):
        cleaned_data = super().clean()

        username = cleaned_data.get("username")
        mobile = cleaned_data.get("mobile")

        if username and mobile:
            user = User.objects.filter(
                username=username,
                mobile=mobile,
                is_active=True,
            ).first()

            if not user:
                raise forms.ValidationError(
                    "اطلاعات واردشده با هیچ کاربر فعالی مطابقت ندارد."
                )

            self.user = user

        return cleaned_data


class VerifyOTPForm(forms.Form):
    code = forms.CharField(
        label="کد تأیید",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "class": (
                    "w-full rounded-xl border border-slate-200 "
                    "bg-slate-50 px-4 py-3 text-center text-xl "
                    "font-bold tracking-[0.5em] text-slate-700 "
                    "outline-none transition focus:border-blue-500 "
                    "focus:bg-white focus:ring-4 focus:ring-blue-100"
                ),
                "placeholder": "------",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "dir": "ltr",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        code = code.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))

        if not code.isdigit():
            raise forms.ValidationError("کد تأیید باید فقط شامل اعداد باشد.")

        if len(code) != 6:
            raise forms.ValidationError("کد تأیید باید ۶ رقم باشد.")

        return code


class SetNewPasswordForm(forms.Form):
    new_password = forms.CharField(
        label="رمز عبور جدید",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": (
                    "w-full rounded-xl border border-slate-200 "
                    "bg-slate-50 px-4 py-3 text-sm text-slate-700 "
                    "outline-none transition focus:border-blue-500 "
                    "focus:bg-white focus:ring-4 focus:ring-blue-100"
                ),
                "placeholder": "رمز عبور جدید را وارد کنید",
                "autocomplete": "new-password",
            }
        ),
    )

    confirm_password = forms.CharField(
        label="تکرار رمز عبور جدید",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": (
                    "w-full rounded-xl border border-slate-200 "
                    "bg-slate-50 px-4 py-3 text-sm text-slate-700 "
                    "outline-none transition focus:border-blue-500 "
                    "focus:bg-white focus:ring-4 focus:ring-blue-100"
                ),
                "placeholder": "رمز عبور جدید را دوباره وارد کنید",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError(
                "رمزهای عبور واردشده یکسان نیستند."
            )

        if password:
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(password)
            except forms.ValidationError:
                raise

        return cleaned_data
