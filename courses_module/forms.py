from django import forms
from django.utils import timezone
import jdatetime

from users_module.models import FieldOfStudy, Grade, Subject
from .models import Course, CourseResource


class CourseCreateForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["allowed_grades"].queryset = Grade.objects.filter(is_active=True).select_related("school")
        self.fields["allowed_fields"].queryset = FieldOfStudy.objects.filter(is_active=True).select_related("grade")
        self.fields["subjects"].queryset = Subject.objects.filter(is_active=True).select_related("field")
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "glass-input"
        for name in ("start_date", "end_date"):
            self.fields[name].widget.attrs.update({"data-jdp": "", "data-jdp-time": "true", "autocomplete": "off"})
            current = getattr(self.instance, name, None)
            if current:
                local = timezone.localtime(current)
                jalali = jdatetime.datetime.fromgregorian(datetime=local)
                self.initial[name] = f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d} {local.hour:02d}:{local.minute:02d}"

    class Meta:
        model = Course
        fields = ["title", "description", "learning_outcomes", "prerequisites", "level", "estimated_duration", "capacity", "cover_image", "allowed_grades", "allowed_fields", "subjects", "start_date", "end_date"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4}), "learning_outcomes": forms.Textarea(attrs={"rows": 3}), "prerequisites": forms.Textarea(attrs={"rows": 3}), "allowed_grades": forms.CheckboxSelectMultiple(), "allowed_fields": forms.CheckboxSelectMultiple(), "subjects": forms.CheckboxSelectMultiple(), "start_date": forms.TextInput(), "end_date": forms.TextInput()}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("start_date") and cleaned.get("end_date") and cleaned["end_date"] <= cleaned["start_date"]:
            self.add_error("end_date", "زمان پایان باید بعد از زمان شروع باشد.")
        is_admin = self.user and (self.user.role == "ADMIN" or self.user.is_superuser)
        if not is_admin:
            for name, message in (("allowed_grades", "حداقل یک پایه را انتخاب کنید."), ("allowed_fields", "حداقل یک رشته را انتخاب کنید."), ("subjects", "حداقل یک درس را انتخاب کنید.")):
                if not cleaned.get(name):
                    self.add_error(name, message)
        return cleaned

    def _clean_jalali_datetime(self, name):
        value = self.data.get(name)
        if not value:
            return None
        digits = str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "012345678901234567890123456789"))
        try:
            date_part, time_part = digits.strip().split(" ", 1)
            year, month, day = [int(item) for item in date_part.replace("-", "/").split("/")]
            bits = time_part.split(":")
            local_dt = jdatetime.datetime(year, month, day, int(bits[0]), int(bits[1]), int(bits[2]) if len(bits) > 2 else 0).togregorian()
            return timezone.make_aware(local_dt, timezone.get_current_timezone())
        except (ValueError, TypeError, IndexError):
            raise forms.ValidationError("تاریخ و ساعت جلالی را به شکل صحیح وارد کنید.")

    def clean_start_date(self):
        return self._clean_jalali_datetime("start_date")

    def clean_end_date(self):
        return self._clean_jalali_datetime("end_date")


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
