from django import forms

from .models import FieldOfStudy, Grade, Province, School


CONTROL = "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm"


class AcademicDefaultsForm(forms.Form):
    default_province = forms.ModelChoiceField(label="استان پیش‌فرض", queryset=Province.objects.all(), required=False)
    default_school = forms.ModelChoiceField(label="مدرسه پیش‌فرض", queryset=School.objects.none(), required=False)
    default_grade = forms.ChoiceField(label="پایه پیش‌فرض", required=False)
    default_field = forms.ChoiceField(label="رشته پیش‌فرض", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["default_school"].queryset = School.objects.select_related("province").order_by("name", "pk")
        self.fields["default_school"].label_from_instance = lambda school: f"{school.name} · {school.province}"
        for name, model in [("default_grade", Grade), ("default_field", FieldOfStudy)]:
            titles = model.objects.filter(is_active=True).order_by("title").values_list("title", flat=True).distinct()
            self.fields[name].choices = [("", "از ستون فایل خوانده شود")] + [(title, title) for title in titles]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "h-4 w-4 rounded border-slate-300" if isinstance(field.widget, forms.CheckboxInput) else CONTROL)

    def clean(self):
        data = super().clean()
        province, school = data.get("default_province"), data.get("default_school")
        if school and province and school.province_id != province.pk:
            self.add_error("default_school", "مدرسه متعلق به استان انتخاب‌شده نیست.")
        return data


class CurriculumSpreadsheetForm(AcademicDefaultsForm):
    file = forms.FileField(label="فایل Excel یا CSV", widget=forms.FileInput(attrs={"accept": ".xlsx,.csv"}))
    apply_to_all = forms.BooleanField(label="اعمال در همه مدارس محدوده انتخابی (اگر مدرسه مشخص نشده باشد)", required=False)

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith((".xlsx", ".csv")) or upload.size > 8 * 1024 * 1024:
            raise forms.ValidationError("فایل xlsx یا csv با حداکثر حجم ۸ مگابایت انتخاب کنید.")
        return upload
