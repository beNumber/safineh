from datetime import datetime

import jdatetime
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from django.utils import timezone

from auth_module.models import UserRole
from users_module.models import FieldOfStudy, Grade
from users_module.choices import UniqueTitleChoiceField
# خط ۱۱ را به این شکل تغییر بده:
from questions_module.models import Question, Topic

from .models import Quiz, QuizChoice, QuizQuestion
from .permissions import has_full_quiz_access, quiz_students_for


CONTROL = "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"


def _jalali_to_datetime(date_value, time_value):
    try:
        time_text = time_value.strftime("%H:%M") if hasattr(time_value, "strftime") else str(time_value)
        value = jdatetime.datetime.strptime(f"{date_value} {time_text}", "%Y/%m/%d %H:%M").togregorian()
        return timezone.make_aware(value, timezone.get_current_timezone())
    except (TypeError, ValueError):
        raise forms.ValidationError("تاریخ یا ساعت شمسی معتبر نیست.")


class QuizForm(forms.ModelForm):
    grade = UniqueTitleChoiceField(label="پایه", queryset=Grade.objects.filter(is_active=True), required=False)
    field = UniqueTitleChoiceField(label="رشته", queryset=FieldOfStudy.objects.filter(is_active=True), required=False)
    opens_date = forms.CharField(label="تاریخ شروع (شمسی)")
    opens_time = forms.TimeField(label="ساعت شروع", widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "step": "60"}))
    closes_date = forms.CharField(label="تاریخ پایان (شمسی)")
    closes_time = forms.TimeField(label="ساعت پایان", widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "step": "60"}))
    release_date = forms.CharField(label="تاریخ انتشار پاسخ‌نامه", required=False)
    release_time = forms.TimeField(label="ساعت انتشار پاسخ‌نامه", required=False, widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "step": "60"}))
    assigned_students = forms.ModelMultipleChoiceField(label="دانش‌آموزان منتخب", required=False, queryset=get_user_model().objects.none())

    class Meta:
        model = Quiz
        fields = ["title", "description", "all_students", "province", "school", "grade", "field", "assigned_students", "duration_minutes", "max_attempts", "negative_marking", "negative_ratio", "shuffle_questions", "shuffle_choices", "publish_results"]
        widgets = {
            "description": CKEditorUploadingWidget(), "all_students": forms.CheckboxInput(), "negative_marking": forms.CheckboxInput(),
            "shuffle_questions": forms.CheckboxInput(), "shuffle_choices": forms.CheckboxInput(),
            "publish_results": forms.CheckboxInput(),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["school"].queryset = self.fields["school"].queryset.select_related("province")
        self.fields["school"].label_from_instance = lambda school: f"{school.name} — {school.province}"
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, CKEditorUploadingWidget)):
                field.widget.attrs["class"] = CONTROL
        for name in ("opens_date", "closes_date", "release_date"):
            self.fields[name].widget.attrs.update({"data-jdp": "", "autocomplete": "off", "placeholder": "برای انتخاب تاریخ کلیک کنید", "readonly": "readonly"})
        self.fields["assigned_students"].widget.attrs["size"] = "8"
        self.fields["assigned_students"].queryset = get_user_model().objects.filter(role=UserRole.STUDENT, is_active=True).order_by("last_name", "first_name", "username")
        if user is not None:
            self.fields['assigned_students'].queryset = quiz_students_for(user).order_by('last_name', 'first_name', 'username')
            if not has_full_quiz_access(user):
                self.fields['all_students'].disabled = True
                self.initial['all_students'] = False
        if self.instance.pk:
            for prefix, value in (("opens", self.instance.opens_at), ("closes", self.instance.closes_at), ("release", self.instance.answer_release_at)):
                if value:
                    local = timezone.localtime(value)
                    jalali = jdatetime.datetime.fromgregorian(datetime=local.replace(tzinfo=None))
                    self.initial[f"{prefix}_date"] = jalali.strftime("%Y/%m/%d")
                    self.initial[f"{prefix}_time"] = local.strftime("%H:%M")

    def clean(self):
        data = super().clean()
        opens = _jalali_to_datetime(data.get("opens_date"), data.get("opens_time"))
        closes = _jalali_to_datetime(data.get("closes_date"), data.get("closes_time"))
        release = None
        if data.get("release_date") or data.get("release_time"):
            if not data.get("release_date") or not data.get("release_time"):
                raise forms.ValidationError("برای انتشار پاسخ‌نامه، تاریخ و ساعت را کامل وارد کنید.")
            release = _jalali_to_datetime(data["release_date"], data["release_time"])
        if closes <= opens:
            raise forms.ValidationError("زمان پایان باید بعد از زمان شروع باشد.")
        if release and release < closes:
            raise forms.ValidationError("انتشار پاسخ‌نامه باید پس از پایان آزمون باشد.")
        data["opens_at_value"], data["closes_at_value"], data["answer_release_at_value"] = opens, closes, release
        school, grade, field = data.get("school"), data.get("grade"), data.get("field")
        if data.get("all_students"):
            data["assigned_students"] = get_user_model().objects.none()
        if self.user is not None and not has_full_quiz_access(self.user) and not data.get('assigned_students'):
            self.add_error('assigned_students', 'حداقل یکی از دانش‌آموزان خود را انتخاب کنید.')
        if school and data.get("province") and school.province_id != data["province"].id:
            self.add_error("school", "مدرسه متعلق به استان انتخاب‌شده نیست.")
        if grade and school:
            grade = Grade.objects.filter(title=grade.title, school=school, is_active=True).first()
            if grade is None:
                self.add_error("grade", "پایه در مدرسه انتخاب‌شده تعریف نشده است.")
            else:
                data["grade"] = grade
        if field and grade:
            field = FieldOfStudy.objects.filter(title=field.title, grade=grade, is_active=True).first()
            if field is None:
                self.add_error("field", "رشته در پایه انتخاب‌شده تعریف نشده است.")
            else:
                data["field"] = field
        return data

    def save(self, commit=True):
        item = super().save(commit=False)
        item.opens_at = self.cleaned_data["opens_at_value"]
        item.closes_at = self.cleaned_data["closes_at_value"]
        item.answer_release_at = self.cleaned_data["answer_release_at_value"]
        if commit:
            item.save()
            self.save_m2m()
            if item.all_students:
                item.assigned_students.clear()
        return item


class QuizQuestionForm(forms.ModelForm):
    class Meta:
        model = QuizQuestion
        fields = ["question_type", "bank_topic", "text", "image", "explanation", "explanation_image", "points", "submit_to_bank"]
        widgets = {"text": CKEditorUploadingWidget(), "explanation": CKEditorUploadingWidget()}

    def __init__(self, *args, quiz=None, **kwargs):
        super().__init__(*args, **kwargs)
        topics = Topic.objects.filter(is_active=True).select_related("chapter__subject")
        if quiz is not None:
            if quiz.field_id:
                topics = topics.filter(chapter__subject__field__title=quiz.field.title)
            elif quiz.grade_id:
                topics = topics.filter(chapter__subject__field__grade__title=quiz.grade.title)
        self.fields["bank_topic"].queryset = topics
        self.fields["bank_topic"].label = "مبحث مرتبط"
        self.fields["bank_topic"].help_text = "فقط مباحث پایه و رشته انتخاب‌شده در آزمون نمایش داده می‌شوند."
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, CKEditorUploadingWidget)):
                field.widget.attrs["class"] = CONTROL


class BaseChoiceFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if self.instance.question_type == QuizQuestion.Type.DESCRIPTIVE:
            return
        active = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE") and (f.cleaned_data.get("text") or f.cleaned_data.get("image") or f.instance.image)]
        if len(active) != 4:
            raise forms.ValidationError("سؤال تستی باید دقیقاً چهار گزینه داشته باشد.")
        if sum(bool(f.cleaned_data.get("is_correct")) for f in active) != 1:
            raise forms.ValidationError("دقیقاً یک گزینه را به‌عنوان پاسخ صحیح مشخص کنید.")


QuizChoiceFormSet = inlineformset_factory(
    QuizQuestion, QuizChoice, formset=BaseChoiceFormSet,
    fields=["text", "image", "is_correct"], extra=4, max_num=4, can_delete=True,
    widgets={"text": CKEditorUploadingWidget(), "image": forms.ClearableFileInput(attrs={"class": CONTROL}), "is_correct": forms.CheckboxInput()},
)


class BankImportForm(forms.Form):
    questions = forms.ModelMultipleChoiceField(queryset=Question.objects.none(), widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["questions"].queryset = Question.objects.filter(is_active=True, approval_status=Question.ApprovalStatus.APPROVED).select_related("topic__chapter__subject").prefetch_related("choices")


class ManualGradeForm(forms.Form):
    points = forms.DecimalField(min_value=0, decimal_places=2, max_digits=8, widget=forms.NumberInput(attrs={"step": "0.25", "class": CONTROL}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": CONTROL}))
