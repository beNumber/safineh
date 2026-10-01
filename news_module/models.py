from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from ckeditor_uploader.fields import RichTextUploadingField


class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status="published").filter(
            Q(published_at__lte=timezone.now()) | Q(published_at__isnull=True)
        )

    def visible_to(self, user):
        if getattr(user, "is_authenticated", False) and user.is_staff:
            return self

        profile_rows = []
        if getattr(user, "is_authenticated", False):
            profile_rows = list(
                user.student_profiles.values_list(
                    "field__grade__school__province_id",
                    "field__grade__school_id",
                    "field__grade_id",
                )
            )

        province_ids = {row[0] for row in profile_rows}
        school_ids = {row[1] for row in profile_rows}
        grade_ids = {row[2] for row in profile_rows}
        queryset = self.annotate(
            _province_target_count=Count("target_provinces", distinct=True),
            _school_target_count=Count("target_schools", distinct=True),
            _grade_target_count=Count("target_grades", distinct=True),
            _province_match_count=Count("target_provinces", filter=Q(target_provinces__in=province_ids), distinct=True),
            _school_match_count=Count("target_schools", filter=Q(target_schools__in=school_ids), distinct=True),
            _grade_match_count=Count("target_grades", filter=Q(target_grades__in=grade_ids), distinct=True),
        )
        return queryset.filter(
            Q(_province_target_count=0) | Q(_province_match_count__gt=0),
            Q(_school_target_count=0) | Q(_school_match_count__gt=0),
            Q(_grade_target_count=0) | Q(_grade_match_count__gt=0),
        )


class Category(models.Model):
    """دسته‌بندی اخبار"""

    name = models.CharField(
        max_length=100,
        verbose_name="نام دسته‌بندی",
    )

    slug = models.SlugField(
        max_length=120,
        unique=True,
        allow_unicode=True,
        verbose_name="نامک",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
    )

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)

        super().save(*args, **kwargs)


class Tag(models.Model):
    """تگ‌های اخبار"""

    name = models.CharField(
        max_length=100,
        verbose_name="نام تگ",
    )

    slug = models.SlugField(
        max_length=120,
        unique=True,
        allow_unicode=True,
        verbose_name="نامک",
    )

    class Meta:
        verbose_name = "تگ"
        verbose_name_plural = "تگ‌ها"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)

        super().save(*args, **kwargs)


class Article(models.Model):
    """خبر اصلی"""

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PUBLISHED = "published", "منتشر شده"
        ARCHIVED = "archived", "بایگانی شده"

    title = models.CharField(
        max_length=250,
        verbose_name="عنوان خبر",
    )

    slug = models.SlugField(
        max_length=280,
        unique=True,
        allow_unicode=True,
        verbose_name="نامک",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name="دسته‌بندی",
    )

    tags = models.ManyToManyField(
        Tag,
        related_name="articles",
        blank=True,
        verbose_name="تگ‌ها",
    )

    target_provinces = models.ManyToManyField(
        "users_module.Province", related_name="targeted_news_articles", blank=True,
        verbose_name="استان‌های مخاطب",
        help_text="در صورت خالی بودن، خبر از نظر استان محدود نمی‌شود.",
    )
    target_schools = models.ManyToManyField(
        "users_module.School", related_name="targeted_news_articles", blank=True,
        verbose_name="مدارس مخاطب",
        help_text="در صورت خالی بودن، خبر از نظر مدرسه محدود نمی‌شود.",
    )
    target_grades = models.ManyToManyField(
        "users_module.Grade", related_name="targeted_news_articles", blank=True,
        verbose_name="پایه‌های مخاطب",
        help_text="اگر هر سه محدوده خالی باشند، خبر برای همه قابل مشاهده است.",
    )

    summary = models.TextField(
        max_length=500,
        verbose_name="خلاصه خبر",
    )

    # ویرایشگر متنی CKEditor به همراه امکان آپلود تصویر
    content = RichTextUploadingField(
        verbose_name="متن خبر",
    )

    image = models.ImageField(
        upload_to="news/articles/",
        blank=True,
        null=True,
        verbose_name="تصویر خبر",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="news_articles",
        verbose_name="نویسنده",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="وضعیت انتشار",
    )

    is_featured = models.BooleanField(
        default=False,
        verbose_name="خبر ویژه",
    )

    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد بازدید",
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان انتشار",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین بروزرسانی",
    )

    objects = ArticleQuerySet.as_manager()

    class Meta:
        verbose_name = "خبر"
        verbose_name_plural = "اخبار"
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["-published_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            "news_module:article_detail",
            kwargs={"slug": self.slug},
        )

    @property
    def is_public(self):
        if not self.pk:
            return True
        return not (
            self.target_provinces.exists()
            or self.target_schools.exists()
            or self.target_grades.exists()
        )

    @property
    def is_published(self):
        """خبر فقط زمانی منتشر محسوب می‌شود که زمان انتشارش رسیده باشد."""

        return self.status == self.Status.PUBLISHED and (
            self.published_at is None
            or self.published_at <= timezone.now()
        )
