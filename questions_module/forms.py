from django import forms
from django.forms import inlineformset_factory
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from users_module.models import Access, Subject

from .models import Choice, Question, Chapter


class QuestionForm(forms.ModelForm):
    """فرم ایجاد و ویرایش سوال با پشتیبانی از فصل‌ها و دسته‌ها"""

    class Meta:
        model = Question
        fields = [
            "chapter",
            "category",
            "difficulty",
            "text",
            "image",
            "explanation",
            "is_active",
        ]
        labels = {
            "chapter": "فصل / مبحث",
            "category": "دسته‌بندی (اختیاری)",
            "difficulty": "سطح دشواری",
            "text": "متن سوال",
            "image": "تصویر سوال (اختیاری)",
            "explanation": "پاسخ تشریحی (اختیاری)",
            "is_active": "فعال باشد؟",
        }
        widgets = {
            "chapter": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "difficulty": forms.Select(attrs={"class": "form-select"}),
            "text": CKEditorUploadingWidget(),
            "explanation": CKEditorUploadingWidget(),
            "image": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        chapters = Chapter.objects.select_related("subject").filter(
            subject__is_active=True
        )
        if user is not None and not user.is_superuser:
            accesses = user.accesses.filter(name=Access.Code.CREATE_QUESTION)
            if not accesses.filter(subject__isnull=True).exists():
                chapters = chapters.filter(
                    subject_id__in=accesses.values_list("subject_id", flat=True)
                )
        self.fields["chapter"].queryset = chapters.order_by("subject__title", "name")


class ChapterForm(forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ("subject", "name")
        widgets = {
            "subject": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام فصل"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        subjects = Subject.objects.filter(is_active=True)
        if user is not None and not user.is_superuser:
            accesses = user.accesses.filter(name=Access.Code.CREATE_CHAPTER)
            if not accesses.filter(subject__isnull=True).exists():
                subjects = subjects.filter(pk__in=accesses.values_list("subject_id", flat=True))
        self.fields["subject"].queryset = subjects.order_by("title")


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ("title", "code", "field", "is_active")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام درس"}),
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "کد یکتا"}),
            "field": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class BaseChoiceFormSet(forms.BaseInlineFormSet):
    """اعتبارسنجی گزینه‌ها: بررسی تعداد گزینه‌ها و وجود دقیقاً یک پاسخ صحیح"""

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        active_forms = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
            and (
                form.cleaned_data.get("text", "").strip()
                or form.cleaned_data.get("image")
                or (form.instance.pk and form.instance.image)
            )
        ]
        correct_answers = [form for form in active_forms if form.cleaned_data.get("is_correct")]

        if len(active_forms) != 4:
            raise forms.ValidationError("هر سؤال باید دقیقاً چهار گزینه داشته باشد.")
        if len(correct_answers) != 1:
            raise forms.ValidationError("دقیقاً یک گزینه باید به‌عنوان پاسخ صحیح انتخاب شود.")


ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    formset=BaseChoiceFormSet,
    fields=("text", "image", "is_correct"),
    extra=4,  # ۴ ردیف پیش‌فرض برای گزینه‌ها
    min_num=4,
    max_num=4,
    validate_min=True,
    validate_max=True,
    can_delete=True,
    labels={
        "text": "متن گزینه",
        "is_correct": "گزینه صحیح",
        "image": "تصویر گزینه (اختیاری)",
    },
    widgets={
        "text": CKEditorUploadingWidget(),
        "is_correct": forms.CheckboxInput(
            attrs={"class": "form-check-input"}
        ),
        "image": forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}
        ),
    },
)
