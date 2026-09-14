from django import forms
from django.forms import inlineformset_factory
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from .models import Quiz, QuizQuestion, QuizChoice


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ('title', 'description', 'question_count', 'duration_minutes', 'max_attempts', 'opens_at', 'closes_at', 'province', 'school', 'grade', 'field')
        labels = {'title':'عنوان آزمون','description':'توضیحات آزمون','question_count':'تعداد سؤال','duration_minutes':'مدت آزمون (دقیقه)','max_attempts':'حداکثر دفعات شرکت','opens_at':'زمان باز شدن','closes_at':'زمان بسته شدن','province':'استان هدف','school':'مدرسه هدف','grade':'پایه هدف','field':'رشته هدف'}
        widgets = {
            'description': CKEditorUploadingWidget(),
            'opens_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'w-full'}),
            'closes_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'w-full'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('opens_at', 'closes_at'):
            self.fields[name].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']


class QuizQuestionForm(forms.ModelForm):
    class Meta:
        model = QuizQuestion
        fields = ('text', 'image', 'points', 'order')
        labels = {'text':'متن سؤال','image':'تصویر سؤال','points':'بارم سؤال','order':'شماره سؤال'}
        widgets = {'text': CKEditorUploadingWidget()}


class QuizChoiceForm(forms.ModelForm):
    class Meta:
        model = QuizChoice
        fields = ('text', 'image', 'is_correct', 'order')
        labels = {'text':'متن گزینه','image':'تصویر گزینه','is_correct':'این گزینه پاسخ صحیح است','order':'ترتیب گزینه'}
        widgets = {'text': CKEditorUploadingWidget()}


ChoiceFormSet = inlineformset_factory(QuizQuestion, QuizChoice, form=QuizChoiceForm, extra=4, min_num=4, max_num=4, validate_min=True, validate_max=True, can_delete=True)
