from django.db import models
from ckeditor.fields import RichTextField
from django.utils.text import slugify
from django.utils import timezone

from django.conf import settings
# ====================== Category ======================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="نام دسته‌بندی")
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name="اسلاگ دسته‌بندی")

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name


# ====================== Tag ======================
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="نام تگ")
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name="اسلاگ تگ")

    class Meta:
        verbose_name = "تگ"
        verbose_name_plural = "تگ‌ها"

    def __str__(self):
        return self.name


# ====================== PublishedManager ======================
class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            status="published",
            published_at__lte=timezone.now()
        )


# ====================== Post ======================
class Post(models.Model):
    image = models.ImageField(
    upload_to="posts/",
    blank=True,
    null=True,
    verbose_name="تصویر",
)
    title = models.CharField(max_length=200, verbose_name="عنوان")
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name="اسلاگ")
    summary = models.TextField(verbose_name="خلاصه")
    body = RichTextField(verbose_name="متن کامل")
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name="posts",
        verbose_name="دسته‌بندی"
    )
    cover = models.ImageField(
    upload_to="posts/covers/",
    blank=True,
    null=True,
    verbose_name="کاور صفحه اصلی",
)
    content_image = models.ImageField(
    upload_to="posts/content/",
    blank=True,
    null=True,
    verbose_name="عکس داخل پست",
)
    content_video = models.FileField(
    upload_to="posts/videos/",
    blank=True,
    null=True,
    verbose_name="فیلم داخل پست",
)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, 
        related_name="posts",
        verbose_name="نویسنده"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=10, 
        choices=[("draft", "پیش‌نویس"), ("published", "منتشرشده")], 
        default="draft"
    )
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان انتشار")
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="posts",
        verbose_name="تگ‌ها",
    )

    objects = models.Manager()
    published = PublishedManager()   # <-- این خط را حتماً اضافه کن

    def save(self, *args, **kwargs):
        if self.status == "published" and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title
