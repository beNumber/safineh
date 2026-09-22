import jdatetime
from datetime import datetime
from django import forms
from django.utils import timezone
from .models import OnlineClass

FIELD = "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
PERSIAN_TO_ENGLISH = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


class OnlineClassForm(forms.ModelForm):
    class_date = forms.CharField(label="تاریخ کلاس", widget=forms.TextInput(attrs={"class": FIELD, "data-jdp": "", "autocomplete": "off", "placeholder": "۱۴۰۵/۰۷/۰۱"}))
    start_time = forms.TimeField(label="ساعت شروع", widget=forms.TimeInput(format="%H:%M", attrs={"class": FIELD, "type": "time"}))
    end_time = forms.TimeField(label="ساعت پایان", widget=forms.TimeInput(format="%H:%M", attrs={"class": FIELD, "type": "time"}))

    class Meta:
        model = OnlineClass
        fields = ["title", "description", "meeting_url", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": FIELD}),
            "description": forms.Textarea(attrs={"class": FIELD, "rows": 3}),
            "meeting_url": forms.URLInput(attrs={"class": FIELD, "dir": "ltr", "placeholder": "https://..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            local_start = timezone.localtime(self.instance.starts_at)
            local_end = timezone.localtime(self.instance.ends_at)
            self.initial.update({"class_date": jdatetime.date.fromgregorian(date=local_start.date()).strftime("%Y/%m/%d"), "start_time": local_start.time(), "end_time": local_end.time()})

    def clean(self):
        cleaned = super().clean()
        try:
            raw_date = (cleaned.get("class_date") or "").translate(PERSIAN_TO_ENGLISH)
            gregorian = jdatetime.datetime.strptime(raw_date, "%Y/%m/%d").date().togregorian()
            start = timezone.make_aware(datetime.combine(gregorian, cleaned["start_time"]))
            end = timezone.make_aware(datetime.combine(gregorian, cleaned["end_time"]))
            if end <= start:
                self.add_error("end_time", "ساعت پایان باید بعد از ساعت شروع باشد.")
            cleaned["starts_at"] = start
            cleaned["ends_at"] = end
        except (KeyError, TypeError, ValueError):
            self.add_error("class_date", "تاریخ و ساعت کلاس را کامل و معتبر وارد کنید.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.starts_at = self.cleaned_data["starts_at"]
        instance.ends_at = self.cleaned_data["ends_at"]
        if commit:
            instance.save()
        return instance
