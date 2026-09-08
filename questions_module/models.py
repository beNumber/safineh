from django.conf import settings
from django.db import models
from users_module.models import Subject


# ==============================================================================
# ۱. ثابت‌ها (Enums)
# ==============================================================================
class Difficulty(models.TextChoices):
    """سطح دشواری سوال"""
    EASY = 'E', 'ساده'
    MEDIUM = 'M', 'متوسط'
    HARD = 'H', 'سخت'
    VERY_HARD = 'VH', 'خیلی سخت'


# ==============================================================================
# ۲. ساختار آموزشی (درس و فصل) و دسته‌بندی
# ==============================================================================
class Category(models.Model):
    """دسته‌بندی درختی عمومی (اختیاری)"""
    name = models.CharField('نام دسته', max_length=100)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
        verbose_name='دسته مادر',
    )

    class Meta:
        verbose_name = 'دسته'
        verbose_name_plural = 'دسته‌ها'
        ordering = ['name']

    def __str__(self):
        return self.name


class Course(models.Model):
    """درس (مثال: ریاضی، فیزیک، ادبیات و ...)"""
    name = models.CharField('نام درس', max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'درس'
        verbose_name_plural = 'دروس'
        ordering = ['name']

    def __str__(self):
        return self.name


class Chapter(models.Model):
    """فصل متعلق به یک درس"""
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='chapters',
        verbose_name='درس',
        null=True,
        blank=True,
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name='question_chapters',
        verbose_name='درس ثبت‌شده',
        null=True,
        blank=True,
    )
    name = models.CharField('نام فصل', max_length=200)

    class Meta:
        verbose_name = 'فصل'
        verbose_name_plural = 'فصل‌ها'
        ordering = ['subject__title', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['subject', 'name'],
                name='unique_chapter_per_subject',
            )
        ]

    def __str__(self):
        subject_name = self.subject.title if self.subject_id else (self.course.name if self.course_id else 'بدون درس')
        return f'{subject_name} | {self.name}'

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.subject_id:
            raise ValidationError({'subject': 'انتخاب درس ثبت‌شده الزامی است.'})


# ==============================================================================
# ۳. سوالات و گزینه‌ها
# ==============================================================================
class Question(models.Model):
    """سؤال چهارگزینه‌ای متصل به درس و فصل."""

    class Type(models.TextChoices):
        MCQ = 'MCQ', 'چهارگزینه‌ای'

    question_type = models.CharField(
        'نوع سوال',
        max_length=3,
        choices=Type.choices,
        default=Type.MCQ,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions',
        verbose_name='دسته',
    )
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.PROTECT,
        related_name='questions',
        verbose_name='فصل',
        null=True,
        blank=True,
    )
    text = models.TextField('متن سوال')
    difficulty = models.CharField(
        'سطح دشواری',
        max_length=2,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    explanation = models.TextField('پاسخ تشریحی', blank=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='طراح سوال',
    )
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سوال'
        verbose_name_plural = 'سوالات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'question_type']),
        ]

    def __str__(self):
        return f'Q{self.pk}: {self.text[:50]}'

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.question_type != self.Type.MCQ:
            raise ValidationError({'question_type': 'تمام سؤال‌ها باید چهارگزینه‌ای باشند.'})


class Choice(models.Model):
    """گزینه‌های سوال"""
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name='سوال',
    )
    text = models.CharField('متن گزینه', max_length=255)
    is_correct = models.BooleanField('گزینه درست', default=False)

    class Meta:
        verbose_name = 'گزینه'
        verbose_name_plural = 'گزینه‌ها'
        ordering = ['pk']

    def __str__(self):
        return self.text


# ==============================================================================
# ۴. مدیریت جلسات تمرین (Practice System)
# ==============================================================================
class PracticeSession(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'در حال انجام'
        DONE = 'done', 'پایان یافته'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_sessions',
        verbose_name='کاربر',
    )
    chapters = models.ManyToManyField(Chapter, related_name='practice_sessions', verbose_name='فصل‌ها')
    questions = models.ManyToManyField(Question, related_name='practice_sessions', verbose_name='سوالات')
    started_at = models.DateTimeField('زمان شروع', auto_now_add=True)
    finished_at = models.DateTimeField('زمان پایان', null=True, blank=True)
    total_questions = models.PositiveIntegerField('تعداد کل سوالات', default=0)
    correct_count = models.PositiveIntegerField('تعداد درست', default=0)
    wrong_count = models.PositiveIntegerField('تعداد نادرست', default=0)
    skipped_count = models.PositiveIntegerField('تعداد نزده', default=0)
    percent = models.FloatField('درصد', default=0.0)
    requested_difficulty = models.CharField(
        'سطح انتخابی', max_length=2, choices=Difficulty.choices, blank=True
    )
    status = models.CharField('وضعیت', max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)

    class Meta:
        verbose_name = 'جلسه تمرین'
        verbose_name_plural = 'جلسات تمرین'
        ordering = ['-started_at']

    def __str__(self):
        return f'تمرین #{self.pk} - {self.user}'


class PracticeAnswer(models.Model):
    session = models.ForeignKey(
        PracticeSession,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='جلسه تمرین',
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='+', verbose_name='سوال')
    selected_choice = models.ForeignKey(
        Choice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='گزینه انتخابی',
    )
    is_correct = models.BooleanField('پاسخ درست', null=True, blank=True)
    revealed = models.BooleanField('مشاهده جواب', default=False)
    answered_at = models.DateTimeField('زمان پاسخ', auto_now=True)

    class Meta:
        verbose_name = 'پاسخ تمرین'
        verbose_name_plural = 'پاسخ‌های تمرین'
        unique_together = ('session', 'question')


# ==============================================================================
# ۵. مدیریت جلسات آزمون (Exam System)
# ==============================================================================
class ExamSession(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'در حال انجام'
        DONE = 'done', 'پایان یافته'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_sessions',
        verbose_name='کاربر',
    )
    chapters = models.ManyToManyField(Chapter, related_name='exam_sessions', verbose_name='فصل‌ها')
    questions = models.ManyToManyField(Question, related_name='exam_sessions', verbose_name='سوالات')
    started_at = models.DateTimeField('زمان شروع', auto_now_add=True)
    ends_at = models.DateTimeField('مهلت زمانی', null=True, blank=True)
    finished_at = models.DateTimeField('زمان پایان', null=True, blank=True)
    total_questions = models.PositiveIntegerField('تعداد کل سوالات', default=0)
    correct_count = models.PositiveIntegerField('تعداد درست', default=0)
    wrong_count = models.PositiveIntegerField('تعداد نادرست', default=0)
    unanswered_count = models.PositiveIntegerField('تعداد نزده', default=0)
    percent = models.FloatField('درصد', default=0.0)
    requested_difficulty = models.CharField(
        'سطح انتخابی', max_length=2, choices=Difficulty.choices, blank=True
    )
    status = models.CharField('وضعیت', max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    auto_submitted = models.BooleanField('ثبت خودکار (اتمام زمان)', default=False)

    class Meta:
        verbose_name = 'جلسه آزمون'
        verbose_name_plural = 'جلسات آزمون'
        ordering = ['-started_at']

    def __str__(self):
        return f'آزمون #{self.pk} - {self.user}'


class ExamAnswer(models.Model):
    session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='جلسه آزمون',
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='+', verbose_name='سوال')
    selected_choice = models.ForeignKey(
        Choice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='گزینه انتخابی',
    )
    is_correct = models.BooleanField('پاسخ درست', null=True, blank=True)
    answered_at = models.DateTimeField('زمان پاسخ', auto_now=True)

    class Meta:
        verbose_name = 'پاسخ آزمون'
        verbose_name_plural = 'پاسخ‌های آزمون'
        unique_together = ('session', 'question')
