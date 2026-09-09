from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from users_module.models import (
    Access,
    FieldOfStudy,
    Grade,
    Province,
    School,
    Subject,
)


class UserRole(models.TextChoices):
    STUDENT = "STUDENT", "دانش‌آموز"
    CONSULTANT = "CONSULTANT", "مشاور"
    PROVINCE_TRUSTEE = "PROVINCE_TRUSTEE", "معتمد استان"
    CONTENT_MODERATOR = "CONTENT_MODERATOR", "ناظر محتوا"
    ADMIN = "ADMIN", "مدیر سیستم"


class User(AbstractUser):
    role = models.CharField(
        max_length=20, choices=UserRole.choices, default=UserRole.STUDENT
    )
    national_code = models.CharField(max_length=10, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=11, unique=True, null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[("MALE", "پسر"), ("FEMALE", "دختر")],
        null=True,
        blank=True,
    )
    accesses = models.ManyToManyField(
        Access,
        blank=True,
        related_name='users',
        verbose_name='دسترسی‌ها',
        help_text='برای کاربران غیر دانش‌آموز، دسترسی‌های مجاز را انتخاب کنید.',
    )

    @property
    def mobile(self):
        """نام سازگار با کد قدیمی بازیابی رمز عبور."""
        return self.phone_number

    def has_project_access(self, access_code, subject=None):
        """سوپریوزر همیشه مجاز، دانش‌آموز همیشه غیرمجاز و سایرین تابع تیک دسترسی‌اند."""
        if self.is_superuser:
            return True
        if self.role == UserRole.STUDENT or not self.is_active:
            return False
        accesses = self.accesses.filter(name=access_code)
        if subject is None:
            return accesses.exists()
        subject_id = getattr(subject, 'pk', subject)
        return accesses.filter(subject__isnull=True).exists() or accesses.filter(
            subject_id=subject_id
        ).exists()


class Consultant(models.Model):
    """
    یک سطر از ماتریس دسترسی مشاور.

    تهی بودن هر بخش از محدوده به معنی «همه» است. بنابراین یک مشاور می‌تواند
    چند سطر با محدوده و مجوزهای متفاوت داشته باشد.
    """

    consultant = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="scopes"
    )
    gender = models.CharField(
        max_length=10,
        choices=[("MALE", "پسر"), ("FEMALE", "دختر")],
        null=True,
        blank=True,
    )
    province = models.ForeignKey(
        Province, on_delete=models.CASCADE, null=True, blank=True
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, null=True, blank=True
    )
    grade = models.ForeignKey(
        Grade, on_delete=models.CASCADE, null=True, blank=True
    )
    field = models.ForeignKey(
        FieldOfStudy, on_delete=models.CASCADE, null=True, blank=True
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, null=True, blank=True
    )

    # فیلد قدیمی نگه داشته شده تا داده‌ها و پنل فعلی از کار نیفتد.
    accesses = models.ManyToManyField(Access, blank=True)
    can_manage_question_bank = models.BooleanField(default=False)
    can_answer_tickets = models.BooleanField(default=False)
    can_answer_psychology = models.BooleanField(default=False)
    can_create_exam = models.BooleanField(default=False)
    can_upload_course = models.BooleanField(default=False)

    class Meta:
        verbose_name = "محدوده دسترسی مشاور"
        verbose_name_plural = "محدوده‌های دسترسی مشاوران"
        indexes = [
            models.Index(fields=["consultant", "subject"]),
            models.Index(fields=["province", "school", "grade"]),
        ]

    def __str__(self):
        return f"{self.consultant} - {self.subject or 'همه درس‌ها'}"

    def clean(self):
        errors = {}
        if self.school_id and self.province_id and self.school.province_id != self.province_id:
            errors["school"] = "مدرسه باید متعلق به استان انتخاب‌شده باشد."
        if self.grade_id and self.school_id and self.grade.school_id != self.school_id:
            errors["grade"] = "پایه باید متعلق به مدرسه انتخاب‌شده باشد."
        if self.field_id and self.grade_id and self.field.grade_id != self.grade_id:
            errors["field"] = "رشته باید متعلق به پایه انتخاب‌شده باشد."
        if self.subject_id and self.field_id and self.subject.field_id != self.field_id:
            errors["subject"] = "درس باید متعلق به رشته انتخاب‌شده باشد."
        if errors:
            raise ValidationError(errors)

    def matches_student(self, student, subject=None):
        field = student.field
        grade = field.grade
        school = grade.school
        return all(
            (
                self.gender is None or self.gender == student.user.gender,
                self.province_id is None or self.province_id == school.province_id,
                self.school_id is None or self.school_id == school.id,
                self.grade_id is None or self.grade_id == grade.id,
                self.field_id is None or self.field_id == field.id,
                self.subject_id is None
                or (subject is not None and self.subject_id == subject.id),
            )
        )


class Student(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="student_profiles")
    field = models.ForeignKey(FieldOfStudy, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.user)

    @property
    def province(self):
        return self.field.grade.school.province


class ProvinceTrustee(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="trustee_provinces"
    )
    province = models.ForeignKey(
        Province, on_delete=models.CASCADE, related_name="trustees"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "province"], name="unique_trustee_per_province"
            )
        ]
        verbose_name = "معتمد استان"
        verbose_name_plural = "معتمدان استان‌ها"

    def __str__(self):
        return f"{self.user} - {self.province}"
