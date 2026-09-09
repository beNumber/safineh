from django import forms
from django.utils import timezone
import jdatetime

from users_module.models import FieldOfStudy, Grade, Subject

from .models import Course


class CourseCreateForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "title", "description", "learning_outcomes", "prerequisites", "level",
            "estimated_duration", "capacity", "cover_image", "allowed_grades",
            "allowed_fields", "subjects", "start_date", "end_date",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "learning_outcomes": forms.Textarea(attrs={"rows": 3}),
            "prerequisites": forms.Textarea(attrs={"rows": 3}),
            "allowed_grades": forms.CheckboxSelectMultiple(),
            "allowed_fields": forms.CheckboxSelectMultiple(),
            "subjects": forms.CheckboxSelectMultiple(),
            "start_date": forms.TextInput(attrs={"data-jdp": "", "data-jdp-time": "true", "autocomplete": "off", "placeholder": "۱۴۰۵/۰۱/۰۱ ۱۰:۳۰"}),
            "end_date": forms.TextInput(attrs={"data-jdp": "", "data-jdp-time": "true", "autocomplete": "off", "placeholder": "۱۴۰۵/۰۱/۰۱ ۱۰:۳۰"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allowed_grades"].queryset = Grade.objects.filter(is_active=True).select_related("school")
        self.fields["allowed_fields"].queryset = FieldOfStudy.objects.filter(is_active=True).select_related("grade")
        self.fields["subjects"].queryset = Subject.objects.filter(is_active=True).select_related("field")
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "glass-input"
        self.fields["title"].widget.attrs["placeholder"] = "مثلاً جمع‌بندی ریاضی دوازدهم"
        self.fields["estimated_duration"].widget.attrs["placeholder"] = "مثلاً ۱۲ ساعت"
        self.fields["capacity"].widget.attrs["placeholder"] = "خالی یعنی بدون محدودیت"
        for name in ("start_date", "end_date"):
            current = getattr(self.instance, name, None)
            if current:
                local = timezone.localtime(current)
                jalali = jdatetime.datetime.fromgregorian(datetime=local)
                self.initial[name] = f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d} {local.hour:02d}:{local.minute:02d}"

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date and end_date <= start_date:
            self.add_error("end_date", "زمان پایان باید بعد از زمان شروع باشد.")
        if not cleaned.get("allowed_grades"):
            self.add_error("allowed_grades", "حداقل یک پایه را انتخاب کنید.")
        if not cleaned.get("allowed_fields"):
            self.add_error("allowed_fields", "حداقل یک رشته را انتخاب کنید.")
        if not cleaned.get("subjects"):
            self.add_error("subjects", "حداقل یک درس را انتخاب کنید.")
        return cleaned

    def _clean_jalali_datetime(self, name):
        value = self.data.get(name)
        if not value:
            return None
        digits = str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        try:
            date_part, time_part = digits.strip().split(" ", 1)
            year, month, day = [int(item) for item in date_part.replace("-", "/").split("/")]
            bits = time_part.split(":")
            hour, minute = int(bits[0]), int(bits[1])
            second = int(bits[2]) if len(bits) > 2 else 0
            return jdatetime.datetime(year, month, day, hour, minute, second).togregorian()
        except (ValueError, TypeError, IndexError):
            raise forms.ValidationError("تاریخ جلالی را به شکل صحیح انتخاب کنید.")

    def clean_start_date(self):
        return self._clean_jalali_datetime("start_date")

    def clean_end_date(self):
        return self._clean_jalali_datetime("end_date")
