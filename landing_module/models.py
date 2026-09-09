from django.db import models


class Category(models.Model):
    title = models.CharField(max_length=150, verbose_name="عنوان دسته‌بندی")
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name="اسلاگ")
    icon = models.CharField(max_length=50, default="fa-graduation-cap", verbose_name="کلاس آیکون FontAwesome")
    description = models.TextField(blank=True, verbose_name="توضیحات مختصر")

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.title


class Instructor(models.Model):
    name = models.CharField(max_length=150, verbose_name="نام و نام خانوادگی")
    specialty = models.CharField(max_length=150, verbose_name="تخصص / سمت تحصیلی")
    bio = models.TextField(verbose_name="بیوگرافی مختصر")
    avatar = models.ImageField(upload_to="instructors/", blank=True, null=True, verbose_name="تصویر پروفایل")

    class Meta:
        verbose_name = "استاد / مشاور"
        verbose_name_plural = "اساتید و مشاوران"

    def __str__(self):
        return self.name


class Course(models.Model):
    LEVEL_CHOICES = (
        ('konkur', 'کنکور و کارشناسی'),
        ('arshad', 'کارشناسی ارشد'),
        ('phd', 'دکتری و پژوهش'),
        ('skill', 'مهارت‌محور'),
    )

    title = models.CharField(max_length=200, verbose_name="عنوان دوره")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="courses", verbose_name="دسته‌بندی")
    instructor = models.ForeignKey(Instructor, on_delete=models.SET_NULL, null=True, related_name="courses", verbose_name="مدرس")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='konkur', verbose_name="سطح تحصیلی")
    price = models.PositiveIntegerField(default=0, verbose_name="قیمت (تومان)")
    students_count = models.PositiveIntegerField(default=0, verbose_name="تعداد دانشجویان")
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=5.0, verbose_name="امتیاز")
    is_featured = models.BooleanField(default=False, verbose_name="نمایش در ویژه لندینگ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        verbose_name = "دوره تحصیلی"
        verbose_name_plural = "دوره‌های تحصیلی"

    def __str__(self):
        return self.title


class FAQ(models.Model):
    question = models.CharField(max_length=255, verbose_name="پرسش")
    answer = models.TextField(verbose_name="پاسخ")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        ordering = ['order']
        verbose_name = "سوال متداول"
        verbose_name_plural = "سوالات متداول"

    def __str__(self):
        return self.question


class Testimonial(models.Model):
    student_name = models.CharField(max_length=150, verbose_name="نام دانشجو")
    major_or_rank = models.CharField(max_length=150, verbose_name="رشته / رتبه یا قبولی")
    content = models.TextField(verbose_name="متن نظر")
    rating = models.PositiveSmallIntegerField(default=5, verbose_name="امتیاز (از ۵)")

    class Meta:
        verbose_name = "نظر دانشجو"
        verbose_name_plural = "نظرات دانشجویان"

    def __str__(self):
        return self.student_name


class ConsultationRequest(models.Model):
    full_name = models.CharField(max_length=150, verbose_name="نام و نام خانوادگی")
    phone_number = models.CharField(max_length=15, verbose_name="شماره تماس")
    target_field = models.CharField(max_length=100, verbose_name="رشته یا مقطع مدنظر")
    message = models.TextField(blank=True, verbose_name="پیام / درخواست مشاوره")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")
    is_called = models.BooleanField(default=False, verbose_name="تماس گرفته شد؟")

    class Meta:
        verbose_name = "درخواست مشاوره"
        verbose_name_plural = "درخواست‌های مشاوره"

    def __str__(self):
        return f"{self.full_name} - {self.phone_number}"
