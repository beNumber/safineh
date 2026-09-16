from django import forms
import jdatetime

from auth_module.models import Student, UserRole
from users_module.models import Subject

from .models import ActivityType, PlanEntry


FIELD_CLASS = (
    "w-full rounded-2xl border border-white/70 bg-white/70 px-4 py-3 text-sm text-slate-700 "
    "shadow-sm outline-none backdrop-blur-xl transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
)
PERSIAN_TO_ENGLISH = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def jalali_date_string(value):
    if not value:
        return ""
    converted = jdatetime.date.fromgregorian(date=value)
    return converted.strftime("%Y/%m/%d").translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


class PlanEntryForm(forms.Form):
    activity_type = forms.ChoiceField(
        label="نوع برنامه", choices=ActivityType.choices, widget=forms.Select(attrs={"class": FIELD_CLASS})
    )
    subject = forms.ModelChoiceField(
        label="درس",
        queryset=Subject.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": FIELD_CLASS, "data-plan-subject": ""}),
    )
    title = forms.CharField(
        label="عنوان دلخواه",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": FIELD_CLASS, "placeholder": "مثلاً تمرین زبان یا جلسه آموزشی"}),
    )
    scheduled_date = forms.CharField(
        label="تاریخ اجرای برنامه",
        widget=forms.TextInput(
            attrs={
                "class": FIELD_CLASS,
                "data-jdp": "",
                "autocomplete": "off",
                "placeholder": "مثلاً ۱۴۰۵/۰۶/۲۸",
            }
        ),
    )
    start_hour = forms.TypedChoiceField(
        label="از ساعت",
        choices=[(hour, f"{hour:02d}:00") for hour in range(8, 24)],
        coerce=int,
        widget=forms.Select(attrs={"class": FIELD_CLASS}),
    )
    end_hour = forms.TypedChoiceField(
        label="تا ساعت",
        choices=[(hour, f"{hour:02d}:00") for hour in range(9, 25)],
        coerce=int,
        widget=forms.Select(attrs={"class": FIELD_CLASS}),
    )
    color = forms.ChoiceField(
        label="رنگ کارت", choices=PlanEntry.Color.choices, widget=forms.Select(attrs={"class": FIELD_CLASS})
    )
    notes = forms.CharField(
        label="یادداشت",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"class": FIELD_CLASS, "rows": 3, "placeholder": "هدف، تعداد تست یا توضیح کوتاه..."}),
    )

    def __init__(self, *args, actor=None, subjects=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields["subject"].queryset = subjects if subjects is not None else Subject.objects.none()

    def clean(self):
        cleaned = super().clean()
        activity_type = cleaned.get("activity_type")
        subject = cleaned.get("subject")
        if activity_type == ActivityType.SUBJECT and not subject:
            self.add_error("subject", "برای برنامه درسی، یک درس انتخاب کنید.")
        if activity_type != ActivityType.SUBJECT:
            cleaned["subject"] = None
            if not cleaned.get("title"):
                cleaned["title"] = dict(ActivityType.choices).get(activity_type, "فعالیت")
        if cleaned.get("start_hour") is not None and cleaned.get("end_hour") is not None:
            if cleaned["end_hour"] <= cleaned["start_hour"]:
                self.add_error("end_hour", "ساعت پایان باید بعد از شروع باشد.")
        raw_date = (cleaned.get("scheduled_date") or "").translate(PERSIAN_TO_ENGLISH).strip()
        try:
            jalali_date = jdatetime.datetime.strptime(raw_date, "%Y/%m/%d").date()
            cleaned["scheduled_date"] = jalali_date.togregorian()
        except (TypeError, ValueError):
            self.add_error("scheduled_date", "یک تاریخ جلالی معتبر انتخاب کنید.")
        return cleaned


class StaffPlanEntryForm(PlanEntryForm):
    target_students = forms.ModelMultipleChoiceField(
        label="دانش‌آموزان هدف",
        queryset=Student.objects.none(),
        required=False,
    )
    apply_to_all = forms.BooleanField(label="اعمال برای همه دانش‌آموزان", required=False)

    def __init__(self, *args, students=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_students"].queryset = Student.objects.none() if students is None else students
        self.fields["target_students"].widget = forms.CheckboxSelectMultiple()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("apply_to_all") and self.actor and not (
            self.actor.is_superuser or self.actor.role == UserRole.ADMIN
        ):
            self.add_error("apply_to_all", "فقط مدیر کل می‌تواند برنامه را برای همه اعمال کند.")
        if not cleaned.get("apply_to_all") and not cleaned.get("target_students"):
            self.add_error("target_students", "حداقل یک دانش‌آموز را انتخاب کنید.")
        return cleaned
