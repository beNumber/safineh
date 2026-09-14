from django.conf import settings
from django.db import models
from django.utils import timezone
from ckeditor_uploader.fields import RichTextUploadingField
from auth_module.models import Province, School, Grade, FieldOfStudy


class Quiz(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار تأیید'
        APPROVED = 'approved', 'تأیید شده'
        REJECTED = 'rejected', 'رد شده'

    title = models.CharField('عنوان آزمون', max_length=200)
    description = RichTextUploadingField('توضیحات', blank=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_quizzes')
    status = models.CharField('وضعیت', max_length=20, choices=Status.choices, default=Status.PENDING)
    approval_note = models.TextField('یادداشت بررسی', blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_quizzes')
    duration_minutes = models.PositiveIntegerField('مدت آزمون (دقیقه)', default=30)
    max_attempts = models.PositiveIntegerField('حداکثر دفعات شرکت', default=1)
    question_count = models.PositiveIntegerField('تعداد سؤال', default=10)
    opens_at = models.DateTimeField('زمان باز شدن')
    closes_at = models.DateTimeField('زمان بسته شدن')
    province = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True, blank=True)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True)
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True)
    field = models.ForeignKey(FieldOfStudy, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_open(self):
        now = timezone.now()
        return self.status == self.Status.APPROVED and self.opens_at <= now <= self.closes_at

    def __str__(self):
        return self.title

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.closes_at and self.opens_at and self.closes_at <= self.opens_at:
            raise ValidationError({'closes_at': 'زمان بسته شدن باید بعد از زمان باز شدن باشد.'})
        if self.duration_minutes < 1:
            raise ValidationError({'duration_minutes': 'مدت آزمون باید حداقل یک دقیقه باشد.'})


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = RichTextUploadingField('متن سؤال')
    image = models.ImageField('تصویر سؤال', upload_to='quizzes/questions/%Y/%m/', blank=True)
    points = models.DecimalField('بارم', max_digits=6, decimal_places=2, default=1)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']


class QuizChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='choices')
    text = RichTextUploadingField('متن گزینه', blank=True)
    image = models.ImageField('تصویر گزینه', upload_to='quizzes/choices/%Y/%m/', blank=True)
    is_correct = models.BooleanField('پاسخ صحیح', default=False)
    order = models.PositiveIntegerField(default=0)


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    correct_count = models.PositiveIntegerField(default=0)
    answered_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-started_at']


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    choice = models.ForeignKey(QuizChoice, on_delete=models.SET_NULL, null=True, blank=True)
    points_earned = models.DecimalField(max_digits=8, decimal_places=2, default=0)
