from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from auth_module.models import Student
from users_module.models import Subject


class ActivityType(models.TextChoices):
    SUBJECT = "SUBJECT", "مطالعه درس"
    FREE = "FREE", "زمان آزاد"
    ENTERTAINMENT = "ENTERTAINMENT", "سرگرمی"
    LEARNING = "LEARNING", "یادگیری مهارت"
    REST = "REST", "استراحت"
    OTHER = "OTHER", "سایر"


class PlanSource(models.TextChoices):
    SELF = "SELF", "برنامه شخصی"
    CONSULTANT = "CONSULTANT", "پیشنهاد مشاور"
    ADMIN = "ADMIN", "برنامه مدیر"


class PlanEntry(models.Model):
    class Weekday(models.IntegerChoices):
        SATURDAY = 0, "شنبه"
        SUNDAY = 1, "یکشنبه"
        MONDAY = 2, "دوشنبه"
        TUESDAY = 3, "سه‌شنبه"
        WEDNESDAY = 4, "چهارشنبه"
        THURSDAY = 5, "پنجشنبه"

    class Color(models.TextChoices):
        BLUE = "blue", "آبی"
        VIOLET = "violet", "بنفش"
        EMERALD = "emerald", "سبز"
        AMBER = "amber", "کهربایی"
        ROSE = "rose", "صورتی"
        CYAN = "cyan", "فیروزه‌ای"

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="plan_entries", verbose_name="دانش‌آموز"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="plan_entries",
        null=True,
        blank=True,
        verbose_name="درس",
    )
    activity_type = models.CharField(
        "نوع فعالیت", max_length=20, choices=ActivityType.choices, default=ActivityType.SUBJECT
    )
    title = models.CharField("عنوان", max_length=120, blank=True)
    scheduled_date = models.DateField("تاریخ اجرا", null=True, blank=True, db_index=True)
    weekday = models.PositiveSmallIntegerField("روز هفته", choices=Weekday.choices)
    start_hour = models.PositiveSmallIntegerField(
        "ساعت شروع", validators=[MinValueValidator(8), MaxValueValidator(23)]
    )
    end_hour = models.PositiveSmallIntegerField(
        "ساعت پایان", validators=[MinValueValidator(9), MaxValueValidator(24)]
    )
    color = models.CharField("رنگ", max_length=12, choices=Color.choices, default=Color.BLUE)
    notes = models.TextField("یادداشت", blank=True, max_length=500)
    source = models.CharField("منبع", max_length=20, choices=PlanSource.choices, default=PlanSource.SELF)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_plan_entries",
        verbose_name="ثبت‌کننده",
    )
    batch_id = models.UUIDField("شناسه تخصیص گروهی", null=True, blank=True, db_index=True)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("زمان ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)

    class Meta:
        ordering = ["weekday", "start_hour", "end_hour"]
        verbose_name = "آیتم برنامه"
        verbose_name_plural = "آیتم‌های برنامه"
        indexes = [
            models.Index(fields=["student", "scheduled_date", "start_hour"]),
            models.Index(fields=["assigned_by", "source"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_hour__gte=8, start_hour__lte=23),
                name="plan_start_hour_between_8_23",
            ),
            models.CheckConstraint(
                condition=models.Q(end_hour__gte=9, end_hour__lte=24),
                name="plan_end_hour_between_9_24",
            ),
            models.CheckConstraint(
                condition=models.Q(end_hour__gt=models.F("start_hour")),
                name="plan_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.student} - {self.get_weekday_display()} - {self.display_title}"

    @property
    def display_title(self):
        if self.activity_type == ActivityType.SUBJECT and self.subject_id:
            return self.subject.title
        return self.title or self.get_activity_type_display()

    @property
    def duration(self):
        return self.end_hour - self.start_hour

    def clean(self):
        super().clean()
        if self.start_hour is not None and self.end_hour is not None and self.end_hour <= self.start_hour:
            raise ValidationError({"end_hour": "ساعت پایان باید بعد از ساعت شروع باشد."})
        if self.activity_type == ActivityType.SUBJECT:
            if not self.subject_id:
                raise ValidationError({"subject": "برای مطالعه درسی، انتخاب درس الزامی است."})
            if self.student_id and self.subject.field_id != self.student.field_id:
                raise ValidationError({"subject": "این درس برای پایه و رشته دانش‌آموز تعریف نشده است."})
        elif self.subject_id:
            raise ValidationError({"subject": "برای فعالیت غیردرسی نباید درس انتخاب شود."})

        if self.scheduled_date:
            self.weekday = (self.scheduled_date.weekday() + 2) % 7
            if self.weekday == 6:
                raise ValidationError({"scheduled_date": "برای جمعه امکان ثبت برنامه در جدول هفتگی وجود ندارد."})

        if self.student_id and self.scheduled_date and self.start_hour is not None and self.end_hour is not None:
            overlap = PlanEntry.objects.filter(
                student_id=self.student_id,
                scheduled_date=self.scheduled_date,
                is_active=True,
                start_hour__lt=self.end_hour,
                end_hour__gt=self.start_hour,
            )
            if self.pk:
                overlap = overlap.exclude(pk=self.pk)
            if overlap.exists():
                raise ValidationError("این بازه با یکی از آیتم‌های برنامه تداخل دارد.")

    def save(self, *args, **kwargs):
        if self.scheduled_date:
            self.weekday = (self.scheduled_date.weekday() + 2) % 7
        return super().save(*args, **kwargs)


class PlanCompletion(models.Model):
    entry = models.ForeignKey(
        PlanEntry, on_delete=models.CASCADE, related_name="completions", verbose_name="آیتم برنامه"
    )
    week_start = models.DateField("شروع هفته")
    completed_at = models.DateTimeField("زمان انجام", auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]
        verbose_name = "انجام برنامه"
        verbose_name_plural = "انجام‌های برنامه"
        constraints = [
            models.UniqueConstraint(fields=["entry", "week_start"], name="unique_weekly_plan_completion")
        ]

    def __str__(self):
        return f"{self.entry} - {self.week_start}"
