from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from ckeditor_uploader.fields import RichTextUploadingField


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
            "news_modal:article_detail",
            kwargs={"slug": self.slug},
        )

    @property
    def is_published(self):
        """خبر فقط زمانی منتشر محسوب می‌شود که زمان انتشارش رسیده باشد."""

        return self.status == self.Status.PUBLISHED and (
            self.published_at is None
            or self.published_at <= timezone.now()
        )
