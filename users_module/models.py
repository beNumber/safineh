from django.db import models


def normalize_name(value):
    return " ".join(str(value or "").replace("ي", "ی").replace("ك", "ک").split())


def normalize_province_name(value):
    text = normalize_name(value).casefold()
    return {"هرمزگان": "hormozgan", "کرمان": "kerman", "سیستان": "sistan",
            "سیستان و بلوچستان": "sistan"}.get(text, text)


class NormalizedNameMixin:
    def normalize_name(self):
        self.name = normalize_name(self.name)

    def clean(self):
        super().clean()
        self.normalize_name()

    def save(self, *args, **kwargs):
        self.normalize_name()
        return super().save(*args, **kwargs)


class Province(NormalizedNameMixin, models.Model):
    name = models.CharField(max_length=100, choices=(
        ('hormozgan', 'هرمزگان'),
        ('kerman', 'کرمان'),
        ('sistan', 'سیستان و بلوچستان')
    ), unique=True)

    def normalize_name(self):
        self.name = normalize_province_name(self.name)

    def __str__(self):
        return self.get_name_display()


class School(NormalizedNameMixin, models.Model):
    province = models.ForeignKey(Province, models.CASCADE, 'schools')
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "مدرسه"
        verbose_name_plural = "مدارس"
        constraints = [
            models.UniqueConstraint(
                fields=["province", "name"],
                name="unique_city_per_province",
            )
        ]

    def __str__(self):
        return f"{self.name}"


def normalize_curriculum_title(value):
    return normalize_name(value)


class CurriculumTitleMixin:
    def clean(self):
        super().clean()
        self.title = normalize_curriculum_title(self.title)

    def save(self, *args, **kwargs):
        self.title = normalize_curriculum_title(self.title)
        return super().save(*args, **kwargs)


class Grade(CurriculumTitleMixin, models.Model):
    title = models.CharField(max_length=100)
    school = models.ForeignKey(School, models.CASCADE, 'grades')
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "title"], name="unique_grade_title_per_school")]

    def __str__(self):
        return self.title


class FieldOfStudy(CurriculumTitleMixin, models.Model):
    title = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    grade = models.ForeignKey(Grade, models.CASCADE, 'fields')

    class Meta:
        constraints = [models.UniqueConstraint(fields=["grade", "title"], name="unique_field_title_per_grade")]

    def __str__(self):
        return self.title


class Subject(CurriculumTitleMixin, models.Model):
    title = models.CharField(max_length=100)
    field = models.ForeignKey(FieldOfStudy, models.CASCADE, 'subjects')
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["field", "title"], name="unique_subject_title_per_field")]

    def __str__(self):
        return self.title
class Access(models.Model):
    class Code(models.TextChoices):
        BANK = 'bank', 'بانک سوال'
        TICKET = 'ticket', 'تیکت'
        QUIZ = 'quiz', 'آزمون'
        COURSE = 'course', 'دوره'
        # مواردی که مربوط به سوالات هستند:
        CREATE_QUESTION = 'create_question', 'ثبت سوال'
        EDIT_QUESTION = 'edit_question', 'ویرایش سوال'
        DELETE_QUESTION = 'delete_question', 'حذف سوال'
        # موارد جدید اضافه شده 👇
        CREATE_CHAPTER = 'create_chapter', 'ایجاد فصل'
        CREATE_SUBJECT = 'create_subject', 'ایجاد درس'

    name = models.CharField(max_length=200, choices=Code.choices)
    # اگر دسترسی ایجاد درس عمومی است و مربوط به درس خاصی نیست، subject باید null پذیر باشد:
    subject = models.ForeignKey(Subject, models.CASCADE, null=True, blank=True)
