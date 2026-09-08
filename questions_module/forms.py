from django import forms
from django.forms import inlineformset_factory

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
            "explanation",
            "is_active",
        ]
        labels = {
            "chapter": "فصل / مبحث",
            "category": "دسته‌بندی (اختیاری)",
            "difficulty": "سطح دشواری",
            "text": "متن سوال",
            "explanation": "پاسخ تشریحی (اختیاری)",
            "is_active": "فعال باشد؟",
        }
        widgets = {
            "chapter": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "difficulty": forms.Select(attrs={"class": "form-select"}),
            "text": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-control",
                    "placeholder": "متن سوال را اینجا وارد کنید...",
                }
            ),
            "explanation": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "توضیحات و پاسخ تشریحی برای نمایش در حالت تمرین یا کارنامه...",
                }
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
        if user is not None:
            bank_accesses = user.accesses.filter(name="bank")
            if not bank_accesses.filter(subject__isnull=True).exists():
                subject_ids = bank_accesses.values_list("subject_id", flat=True)
                chapters = chapters.filter(subject_id__in=subject_ids)
        self.fields["chapter"].queryset = chapters.order_by("subject__title", "name")


class BaseChoiceFormSet(forms.BaseInlineFormSet):
    """اعتبارسنجی گزینه‌ها: بررسی تعداد گزینه‌ها و وجود دقیقاً یک پاسخ صحیح"""

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        active_forms = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
            and form.cleaned_data.get("text", "").strip()
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
    fields=("text", "is_correct"),
    extra=4,  # ۴ ردیف پیش‌فرض برای گزینه‌ها
    min_num=4,
    max_num=4,
    validate_min=True,
    validate_max=True,
    can_delete=True,
    labels={
        "text": "متن گزینه",
        "is_correct": "گزینه صحیح",
    },
    widgets={
        "text": forms.TextInput(
            attrs={"class": "form-control", "placeholder": "متن گزینه..."}
        ),
        "is_correct": forms.CheckboxInput(
            attrs={"class": "form-check-input"}
        ),
    },
)
