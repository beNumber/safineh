from decimal import Decimal

from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from questions_module.models import Question, Chapter
from users_module.models import FieldOfStudy, Grade, Province, School


class Quiz(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PENDING = "pending", "در انتظار تأیید"
        APPROVED = "approved", "تأیید شده"
        REJECTED = "rejected", "رد شده"

    title = models.CharField("عنوان آزمون", max_length=200)
    description = RichTextUploadingField("توضیحات", blank=True)
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.DRAFT)
    approval_note = models.TextField("یادداشت بررسی", blank=True)
    duration_minutes = models.PositiveIntegerField("مدت آزمون (دقیقه)", default=30)
    max_attempts = models.PositiveIntegerField("حداکثر دفعات شرکت", default=1)
    opens_at = models.DateTimeField("زمان شروع")
    closes_at = models.DateTimeField("زمان پایان")
    answer_release_at = models.DateTimeField("زمان انتشار پاسخ‌نامه", null=True, blank=True)
    question_count = models.PositiveIntegerField("تعداد سؤال", default=0)
    negative_marking = models.BooleanField("نمره منفی", default=False)
    negative_ratio = models.DecimalField("ضریب نمره منفی", max_digits=4, decimal_places=2, default=Decimal("0.33"))
    shuffle_questions = models.BooleanField("چیدمان تصادفی سؤال‌ها", default=True)
    shuffle_choices = models.BooleanField("چیدمان تصادفی گزینه‌ها", default=True)
    publish_results = models.BooleanField("نمایش نتیجه به دانش‌آموز", default=True)
    all_students = models.BooleanField("همه دانش‌آموزان", default=False)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, related_name="quizzes")
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True, related_name="quizzes")
    field = models.ForeignKey(FieldOfStudy, on_delete=models.SET_NULL, null=True, blank=True, related_name="quizzes")
    province = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True, blank=True, related_name="quizzes")
    assigned_students = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="assigned_quizzes")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_quizzes")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_quizzes")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "آزمون"
        verbose_name_plural = "آزمون‌ها"

    def __str__(self):
        return self.title

    def clean(self):
        if self.closes_at and self.opens_at and self.closes_at <= self.opens_at:
            raise ValidationError({"closes_at": "زمان پایان باید بعد از زمان شروع باشد."})
        if self.answer_release_at and self.closes_at and self.answer_release_at < self.closes_at:
            raise ValidationError({"answer_release_at": "انتشار پاسخ‌نامه نمی‌تواند قبل از پایان آزمون باشد."})

    @property
    def is_open(self):
        now = timezone.now()
        return self.status == self.Status.APPROVED and self.opens_at <= now <= self.closes_at

    @property
    def total_points(self):
        return self.questions.aggregate(total=models.Sum("points"))["total"] or Decimal("0")

    def sync_question_count(self):
        count = self.questions.count()
        if self.question_count != count:
            type(self).objects.filter(pk=self.pk).update(question_count=count)
            self.question_count = count


class QuizQuestion(models.Model):
    class Type(models.TextChoices):
        MCQ = "MCQ", "چهارگزینه‌ای"
        DESCRIPTIVE = "DES", "تشریحی"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    source_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, related_name="quiz_copies")
    bank_topic = models.ForeignKey(Chapter, on_delete=models.SET_NULL, null=True, blank=True, related_name="quiz_questions", verbose_name="فصل مرتبط")
    question_type = models.CharField("نوع سؤال", max_length=3, choices=Type.choices, default=Type.MCQ)
    text = RichTextUploadingField("متن سؤال", blank=True)
    image = models.ImageField("تصویر سؤال", upload_to="quizzes/questions/%Y/%m/", blank=True)
    explanation = RichTextUploadingField("پاسخ تشریحی", blank=True)
    explanation_image = models.ImageField("تصویر پاسخ تشریحی", upload_to="quizzes/explanations/%Y/%m/", blank=True)
    points = models.DecimalField("بارم", max_digits=6, decimal_places=2, default=1)
    order = models.PositiveIntegerField(default=0)
    submit_to_bank = models.BooleanField("ارسال به صف بانک سؤال پس از آزمون", default=True)
    bank_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, related_name="origin_quiz_questions")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.quiz} - سؤال {self.order + 1}"

    def clean(self):
        if not (self.text or "").strip() and not self.image:
            raise ValidationError("متن یا تصویر سؤال الزامی است.")


class QuizChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name="choices")
    text = RichTextUploadingField("متن گزینه", blank=True)
    image = models.ImageField("تصویر گزینه", upload_to="quizzes/choices/%Y/%m/", blank=True)
    is_correct = models.BooleanField("پاسخ صحیح", default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class QuizAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "در حال انجام"
        SUBMITTED = "submitted", "ارسال شده"
        GRADED = "graded", "تصحیح شده"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    auto_submitted = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    answered_count = models.PositiveIntegerField(default=0)
    tab_switch_count = models.PositiveIntegerField(default=0)
    question_order = models.JSONField(default=list, blank=True)
    choice_order = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [models.UniqueConstraint(fields=["quiz", "student", "started_at"], name="unique_quiz_attempt_start")]

    @property
    def percent(self):
        if not self.total_score:
            return 0
        return round(float(self.score / self.total_score * 100), 2)


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name="answers")
    choice = models.ForeignKey(QuizChoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="answers")
    text_answer = models.TextField("پاسخ متنی", blank=True)
    answer_image = models.ImageField("تصویر پاسخ دست‌نویس", upload_to="quizzes/answers/%Y/%m/", blank=True)
    bookmarked = models.BooleanField(default=False)
    points_earned = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    grader_note = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="graded_quiz_answers")
    saved_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["attempt", "question"], name="unique_attempt_question_answer")]

    @property
    def is_answered(self):
        return bool(self.choice_id or self.text_answer.strip() or self.answer_image)


class QuizEvent(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=30, choices=[("tab_hidden", "خروج از صفحه"), ("tab_visible", "بازگشت به صفحه")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
