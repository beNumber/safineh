import re
from django import forms
from django.utils import timezone
import jdatetime

from auth_module.models import UserRole
from users_module.models import FieldOfStudy, Grade, Subject
from .models import Course, CourseResource, CourseSection, CourseEpisode


class CourseCreateForm(forms.ModelForm):
    start_date = forms.CharField(
        label="تاریخ و ساعت شروع",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "glass-input",
                "data-jdp": "",
                "data-jdp-time": "true",
                "autocomplete": "off",
            }
        ),
    )
    end_date = forms.CharField(
        label="تاریخ و ساعت پایان",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "glass-input",
                "data-jdp": "",
                "data-jdp-time": "true",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        self.fields["allowed_grades"].queryset = Grade.objects.filter(is_active=True).select_related("school")
        self.fields["allowed_fields"].queryset = FieldOfStudy.objects.filter(is_active=True).select_related("grade")
        self.fields["subjects"].queryset = Subject.objects.filter(is_active=True).select_related("field")

        # اختیاری کردن فیلترها برای ثبت سریع دوره توسط ادمین و سوپریوزر
        self.fields["allowed_grades"].required = False
        self.fields["allowed_fields"].required = False
        self.fields["subjects"].required = False

        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple) and name not in ("start_date", "end_date"):
                field.widget.attrs["class"] = "glass-input"

        for name in ("start_date", "end_date"):
            current = getattr(self.instance, name, None)
            if current:
                local = timezone.localtime(current)
                jalali = jdatetime.datetime.fromgregorian(datetime=local)
                self.initial[name] = f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d} {local.hour:02d}:{local.minute:02d}"

    class Meta:
        model = Course
        fields = [
            "title", "description", "learning_outcomes", "prerequisites", "level",
            "estimated_duration", "capacity", "cover_image", "allowed_grades",
            "allowed_fields", "subjects", "start_date", "end_date"
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "learning_outcomes": forms.Textarea(attrs={"rows": 3}),
            "prerequisites": forms.Textarea(attrs={"rows": 3}),
            "allowed_grades": forms.CheckboxSelectMultiple(),
            "allowed_fields": forms.CheckboxSelectMultiple(),
            "subjects": forms.CheckboxSelectMultiple(),
        }

    def _clean_jalali_datetime(self, name):
        value = self.cleaned_data.get(name) or self.data.get(name)
        if not value:
            return None

        if isinstance(value, timezone.datetime):
            return value

        # اصلاح متناظر کاراکترها: دقیقا ۲۰ کاراکتر فارسی/عربی با ۲۰ کاراکتر انگلیسی معادل
        fa_ar_digits = "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"
        en_digits = "01234567890123456789"
        trans_table = str.maketrans(fa_ar_digits, en_digits)
        digits = str(value).translate(trans_table).strip()

        # استخراج اجزای تاریخ و ساعت
        pattern = r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?"
        match = re.search(pattern, digits)

        if not match:
            raise forms.ValidationError("فرمت تاریخ یا ساعت وارد شده نامعتبر است.")

        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else 0
            minute = int(match.group(5)) if match.group(5) else 0
            second = int(match.group(6)) if match.group(6) else 0

            local_dt = jdatetime.datetime(year, month, day, hour, minute, second).togregorian()
            return timezone.make_aware(local_dt, timezone.get_current_timezone())
        except (ValueError, TypeError, OverflowError):
            raise forms.ValidationError("تاریخ یا ساعت وارد شده در تقویم وجود ندارد.")

    def clean_start_date(self):
        return self._clean_jalali_datetime("start_date")

    def clean_end_date(self):
        return self._clean_jalali_datetime("end_date")

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")

        if start and end and end <= start:
            self.add_error("end_date", "زمان پایان باید بعد از زمان شروع باشد.")

        # بررسی جامع دسترسی ادمین و سوپریوزر
        is_admin_or_super = False
        if self.user:
            user_role = getattr(self.user, "role", None)
            if self.user.is_superuser or self.user.is_staff or user_role in [UserRole.ADMIN, "ADMIN"]:
                is_admin_or_super = True

        # اگر کاربر مشاور یا کاربر عادی باشد، پر کردن این فیلدها اجباری است
        if not is_admin_or_super:
            for name, message in (
                ("allowed_grades", "حداقل یک پایه را انتخاب کنید."),
                ("allowed_fields", "حداقل یک رشته را انتخاب کنید."),
                ("subjects", "حداقل یک درس را انتخاب کنید."),
            ):
                if not cleaned.get(name):
                    self.add_error(name, message)

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        is_admin_or_super = False
        if self.user:
            user_role = getattr(self.user, "role", None)
            if self.user.is_superuser or self.user.is_staff or user_role in [UserRole.ADMIN, "ADMIN"]:
                is_admin_or_super = True

        # اگر ادمین مقداری تعیین نکرده باشد، دوره عمومی لحاظ می‌شود
        if is_admin_or_super:
            if not self.cleaned_data.get("allowed_grades"):
                instance.all_grades_allowed = True
            if not self.cleaned_data.get("allowed_fields"):
                instance.all_fields_allowed = True

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CourseResourceForm(forms.ModelForm):
    class Meta:
        model = CourseResource
        fields = ["title", "resource_type", "file", "url", "order", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "glass-input"}),
            "resource_type": forms.Select(attrs={"class": "glass-input"}),
            "url": forms.URLInput(attrs={"class": "glass-input", "dir": "ltr", "placeholder": "https://..."}),
            "order": forms.NumberInput(attrs={"class": "glass-input", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "h-5 w-5 rounded border-slate-300 text-blue-600"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update({"class": "glass-input", "accept": "video/*,image/*,application/pdf"})
        self.fields["file"].help_text = "فایل PDF، ویدیو یا تصویر را انتخاب کنید؛ یا به‌جای آن لینک را وارد کنید."
        self.fields["url"].help_text = "لینک مستقیم فایل یا لینک ویدیوی YouTube/Aparat قابل استفاده است."

    def clean(self):
        cleaned = super().clean()
        uploaded_file = cleaned.get("file")
        url = cleaned.get("url")
        resource_type = cleaned.get("resource_type")

        if not uploaded_file and not url:
            raise forms.ValidationError("یک فایل آپلود کنید یا لینک محتوا را وارد کنید.")
        if uploaded_file and url:
            raise forms.ValidationError("فقط یکی از فایل یا لینک را انتخاب کنید.")

        if uploaded_file:
            content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
            allowed_prefixes = {
                CourseResource.ResourceType.VIDEO: ("video/",),
                CourseResource.ResourceType.IMAGE: ("image/",),
                CourseResource.ResourceType.PDF: ("application/pdf",),
            }
            if not any(content_type.startswith(item) for item in allowed_prefixes.get(resource_type, ())):
                self.add_error("file", "نوع فایل آپلودشده با نوع محتوای انتخابی مطابقت ندارد.")
            if uploaded_file.size > 50 * 1024 * 1024:
                self.add_error("file", "حجم فایل نباید بیشتر از ۵۰ مگابایت باشد.")
        return cleaned


# -------------------------------------------------------------------
# فرم‌های مدیریت سرفصل‌ها و جلسات
# -------------------------------------------------------------------

class CourseSectionForm(forms.ModelForm):
    class Meta:
        model = CourseSection
        fields = ["title", "order", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "glass-input"}),
            "order": forms.NumberInput(attrs={"class": "glass-input", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "h-5 w-5 rounded border-slate-300 text-blue-600"}),
        }

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is not None and order < 1:
            raise forms.ValidationError("ترتیب باید عددی بزرگ‌تر یا مساوی ۱ باشد.")
        return order


class CourseEpisodeForm(forms.ModelForm):
    class Meta:
        model = CourseEpisode
        fields = ["title", "description", "file_type", "file", "url", "order", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "glass-input"}),
            "description": forms.Textarea(attrs={"class": "glass-input", "rows": 3}),
            "file_type": forms.Select(attrs={"class": "glass-input"}),
            "url": forms.URLInput(attrs={"class": "glass-input", "dir": "ltr", "placeholder": "https://..."}),
            "order": forms.NumberInput(attrs={"class": "glass-input", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "h-5 w-5 rounded border-slate-300 text-blue-600"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "file" in self.fields:
            self.fields["file"].widget.attrs.update(
                {"class": "glass-input", "accept": "video/*,application/pdf,audio/*,image/*"}
            )

        if "url" in self.fields:
            self.fields["url"].help_text = "اگر فایل آپلود نمی‌کنید، لینک مستقیم (یا آپارات/یوتیوب) را وارد کنید."

    def clean(self):
        cleaned = super().clean()

        uploaded_file = cleaned.get("file")
        url = cleaned.get("url")

        if "file" in self.fields and "url" in self.fields:
            if not uploaded_file and not url:
                raise forms.ValidationError("یک فایل آپلود کنید یا لینک جلسه را وارد کنید.")
            if uploaded_file and url:
                raise forms.ValidationError("فقط یکی از فایل یا لینک را انتخاب کنید.")

        if uploaded_file and getattr(uploaded_file, "size", 0) > 200 * 1024 * 1024:
            self.add_error("file", "حجم فایل نباید بیشتر از ۲۰۰ مگابایت باشد.")

        file_type = cleaned.get("file_type")
        if uploaded_file and file_type:
            content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
            allowed = {
                "video": ("video/",),
                "pdf": ("application/pdf",),
                "audio": ("audio/",),
                "image": ("image/",),
            }
            prefixes = allowed.get(str(file_type), ())
            if prefixes and not any(content_type.startswith(p) for p in prefixes):
                self.add_error("file", "نوع فایل آپلودشده با نوع انتخاب‌شده مطابقت ندارد.")

        order = cleaned.get("order")
        if order is not None and order < 1:
            self.add_error("order", "ترتیب باید عددی بزرگ‌تر یا مساوی ۱ باشد.")

        return cleaned
