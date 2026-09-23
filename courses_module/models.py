from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Q
from django.utils import timezone

from auth_module.models import FieldOfStudy, Province
from users_module.models import Grade, School, Subject


class ApprovalStatus(models.TextChoices):
    PENDING = "PENDING", "در انتظار تأیید"
    APPROVED = "APPROVED", "تأیید شده"
    REJECTED = "REJECTED", "رد شده"


class CourseLevel(models.TextChoices):
    BEGINNER = "BEGINNER", "مقدماتی"
    INTERMEDIATE = "INTERMEDIATE", "متوسط"
    ADVANCED = "ADVANCED", "پیشرفته"
    ALL = "ALL", "مناسب همه سطوح"


class EpisodeFileType(models.TextChoices):
    VIDEO = "video", "ویدیو"
    PDF = "pdf", "سند یا جزوه PDF"
    AUDIO = "audio", "فایل صوتی پادکست"
    ARCHIVE = "archive", "فایل فشرده (ZIP)"
    OTHER = "other", "سایر موارد"


class Course(models.Model):
    title = models.CharField("عنوان دوره", max_length=255)
    topic = models.CharField("نام مبحث / درس", max_length=255, blank=True)
    slug = models.SlugField("اسلاگ (URL)", allow_unicode=True, unique=True, db_index=True)
    description = models.TextField("توضیحات دوره")
    learning_outcomes = models.TextField("دستاوردهای یادگیری", blank=True)
    prerequisites = models.TextField("پیش‌نیازها", blank=True)
    level = models.CharField(
        "سطح دوره",
        max_length=20,
        choices=CourseLevel.choices,
        default=CourseLevel.ALL
    )
    estimated_duration = models.CharField("مدت تقریبی دوره", max_length=100, blank=True)
    capacity = models.PositiveIntegerField("ظرفیت دوره", null=True, blank=True)
    cover_image = models.ImageField("تصویر کاور", upload_to="courses/covers/", null=True, blank=True)

    all_fields_allowed = models.BooleanField("همه رشته‌ها مجازند", default=False)
    all_grades_allowed = models.BooleanField("همه پایه‌ها مجازند", default=False)
    all_provinces_allowed = models.BooleanField("همه استان‌ها مجازند", default=True)

    allowed_fields = models.ManyToManyField(
        to=FieldOfStudy,
        verbose_name="رشته‌های مجاز",
        related_name="courses_allowed_fields",
        blank=True,
    )

    allowed_grades = models.ManyToManyField(
        to=Grade,
        verbose_name="پایه‌های مجاز",
        related_name="courses_allowed_grades",
        blank=True,
    )

    allowed_provinces = models.ManyToManyField(
        to=Province,
        verbose_name="استان‌های مجاز",
        related_name="courses_allowed_provinces",
        blank=True,
    )

    start_date = models.DateTimeField("تاریخ و ساعت شروع", default=timezone.now)
    end_date = models.DateTimeField("تاریخ و ساعت پایان", null=True, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    subjects = models.ManyToManyField(
        to=Subject,
        verbose_name="درس‌ها",
        related_name="courses",
        blank=True
    )
    approval_status = models.CharField(
        "وضعیت تأیید",
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    rejection_reason = models.TextField("دلیل رد", blank=True)
    reviewed_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        verbose_name="بررسی‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_courses",
    )
    reviewed_at = models.DateTimeField("زمان بررسی", null=True, blank=True)

    author = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        verbose_name="مدرس / سازنده",
        on_delete=models.CASCADE,
        related_name="courses",
    )
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class PublishedManager(models.Manager):
        def get_queryset(self):
            now = timezone.now()
            return super().get_queryset().filter(
                approval_status=ApprovalStatus.APPROVED,
                is_active=True,
                start_date__lte=now,
            ).filter(Q(end_date__isnull=True) | Q(end_date__gte=now))

    objects = models.Manager()
    published = PublishedManager()

    class Meta:
        verbose_name = "دوره"
        verbose_name_plural = "دوره‌ها"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["approval_status", "is_active", "start_date"]),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "تاریخ پایان دوره باید پس از تاریخ شروع باشد."})

    @property
    def is_visible_now(self):
        now = timezone.now()
        if not (self.is_active and self.approval_status == ApprovalStatus.APPROVED):
            return False
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    @property
    def average_rating(self):
        if hasattr(self, "_average_rating"):
            return self._average_rating
        result = self.ratings.aggregate(value=Avg("value"))["value"]
        return round(result, 1) if result is not None else 0.0

    @average_rating.setter
    def average_rating(self, value):
        self._average_rating = round(value, 1) if value is not None else 0.0

    @property
    def rating_count(self):
        if hasattr(self, "_rating_count"):
            return self._rating_count
        return self.ratings.count()

    @rating_count.setter
    def rating_count(self, value):
        self._rating_count = value if value is not None else 0

    @property
    def is_full(self):
        return self.capacity is not None and self.enrollments.count() >= self.capacity

    def is_enrolled_by(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.enrollments.filter(student=user).exists()


class CourseSection(models.Model):
    course = models.ForeignKey(
        to=Course,
        verbose_name="دوره",
        on_delete=models.CASCADE,
        related_name="sections",
    )
    title = models.CharField("عنوان سرفصل", max_length=255)
    description = models.TextField("توضیحات سرفصل", blank=True, null=True)
    order = models.PositiveIntegerField("ترتیب", default=1)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "سرفصل"
        verbose_name_plural = "سرفصل‌ها"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    @property
    def active_episodes(self):
        return self.episodes.filter(is_active=True)


class CourseEpisode(models.Model):
    section = models.ForeignKey(
        to=CourseSection,
        verbose_name="سرفصل",
        on_delete=models.CASCADE,
        related_name="episodes",
    )
    title = models.CharField("عنوان جلسه / فایل", max_length=255)
    description = models.TextField("توضیحات جلسه", blank=True, null=True)
    file_type = models.CharField(
        "نوع محتوا",
        max_length=20,
        choices=EpisodeFileType.choices,
        default=EpisodeFileType.VIDEO,
    )
    file = models.FileField(
        "فایل ضمیمه",
        upload_to="courses/files/",
        blank=True,
        null=True,
        help_text="در صورت عدم آپلود فایل، لینک محتوا را وارد کنید."
    )
    url = models.URLField(
        "لینک مستقیم یا آنلاین محتوا",
        max_length=1000,
        blank=True,
        null=True
    )
    duration_or_pages = models.CharField("مدت یا تعداد صفحات", max_length=50, null=True, blank=True)
    order = models.PositiveIntegerField("ترتیب", default=1)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("تاریخ بارگذاری", auto_now_add=True)

    class Meta:
        verbose_name = "جلسه"
        verbose_name_plural = "جلسات"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if not self.file and not self.url:
            raise ValidationError("حداقل باید یکی از موارد 'فایل ضمیمه' یا 'لینک مستقیم' را وارد کنید.")

    @property
    def download_url(self):
        if self.file:
            return self.file.url
        return self.url


class CourseResource(models.Model):
    class ResourceType(models.TextChoices):
        VIDEO = "video", "ویدیو"
        IMAGE = "image", "تصویر"
        PDF = "pdf", "PDF"

    course = models.ForeignKey(
        to=Course,
        on_delete=models.CASCADE,
        related_name="resources",
        verbose_name="دوره"
    )
    title = models.CharField("عنوان محتوا", max_length=255)
    resource_type = models.CharField("نوع محتوا", max_length=10, choices=ResourceType.choices)
    file = models.FileField("فایل محتوا", upload_to="courses/resources/", blank=True, null=True)
    url = models.URLField("لینک محتوا", max_length=1000, blank=True)
    order = models.PositiveIntegerField("ترتیب نمایش", default=1)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("تاریخ بارگذاری", auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "محتوای دوره"
        verbose_name_plural = "محتواهای دوره"

    def __str__(self):
        return self.title

    @property
    def source_url(self):
        if self.file:
            return self.file.url
        return self.url

    @property
    def video_embed_url(self):
        """تولید آی‌فریم مناسب برای ویدیوهای آپارات و یوتوب"""
        if self.resource_type != self.ResourceType.VIDEO or not self.url:
            return ""
        parsed = urlparse(self.url)
        host = parsed.netloc.lower().removeprefix("www.")
        if host in {"youtube.com", "m.youtube.com"}:
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            return f"https://www.youtube.com/embed/{video_id}" if video_id else ""
        if host == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0]
            return f"https://www.youtube.com/embed/{video_id}" if video_id else ""
        if host.endswith("aparat.com"):
            parts = [part for part in parsed.path.split("/") if part]
            if "v" in parts and parts.index("v") + 1 < len(parts):
                return f"https://www.aparat.com/video/video/embed/videohash/{parts[parts.index('v') + 1]}/vt/frame"
        return ""


class CourseEnrollment(models.Model):
    course = models.ForeignKey(
        to=Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="دوره",
    )
    student = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_enrollments",
        verbose_name="دانش‌آموز",
    )
    created_at = models.DateTimeField("تاریخ ثبت‌نام", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "ثبت‌نام دوره"
        verbose_name_plural = "ثبت‌نام‌های دوره‌ها"
        constraints = [
            models.UniqueConstraint(fields=["course", "student"], name="unique_course_enrollment"),
        ]

    def __str__(self):
        return f"{self.student} → {self.course}"


class CourseRating(models.Model):
    course = models.ForeignKey(
        to=Course,
        on_delete=models.CASCADE,
        related_name="ratings",
        verbose_name="دوره",
    )
    student = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_ratings",
        verbose_name="دانش‌آموز",
    )
    value = models.PositiveSmallIntegerField(
        "امتیاز",
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)
    updated_at = models.DateTimeField("تاریخ ویرایش", auto_now=True)

    class Meta:
        verbose_name = "امتیاز دوره"
        verbose_name_plural = "امتیازهای دوره‌ها"
        constraints = [
            models.UniqueConstraint(fields=["course", "student"], name="unique_course_rating"),
            models.CheckConstraint(condition=models.Q(value__gte=1, value__lte=5), name="rating_between_1_and_5"),
        ]

    def __str__(self):
        return f"{self.student} → {self.course}: {self.value}"
