# auth/models.py

from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models


class User(AbstractUser):
    class UserType(models.TextChoices):
        STUDENT = "student", "دانش‌آموز"
        SUPPORT = "support", "پشتیبان"
        COUNSELOR = "counselor", "مشاور"
        ADMIN = "admin", "مدیر"

    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.STUDENT,
    )

    mobile = models.CharField(
        max_length=11,
        unique=True,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_student(self):
        return self.user_type == self.UserType.STUDENT

    def is_support(self):
        return self.user_type == self.UserType.SUPPORT

    def is_counselor(self):
        return self.user_type == self.UserType.COUNSELOR

    def __str__(self):
        return self.get_full_name() or self.username


## پروفایل دانش‌آموز

class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )

    student_code = models.CharField(
        max_length=50,
        unique=True,
    )

    grade = models.ForeignKey(
        "courses_module.Grade",
        on_delete=models.PROTECT,
        related_name="students",
    )

    field_of_study = models.ForeignKey(
        "courses_module.FieldOfStudy",
        on_delete=models.PROTECT,
        related_name="students",
    )

    city = models.ForeignKey(
        "courses_module.City",
        on_delete=models.PROTECT,
        related_name="students",
    )

    parent_name = models.CharField(
        max_length=150,
        blank=True,
    )

    parent_mobile = models.CharField(
        max_length=11,
        blank=True,
    )

    # imported_from_excel = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.student_code}"


class SupportProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_profile",
    )

    employee_code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
    )

    can_view_all_tickets = models.BooleanField(default=True)

    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.user)


class CounselorSubjectAccess(models.Model):
    counselor = models.ForeignKey(
        "auth_module.CounselorProfile",
        on_delete=models.CASCADE,
        related_name="subject_accesses",
    )

    subject = models.ForeignKey(
        "courses_module.Subject",
        on_delete=models.CASCADE,
        related_name="counselor_accesses",
    )

    granted_at = models.DateTimeField(auto_now_add=True)

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_counselor_accesses",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["counselor", "subject"],
                name="unique_counselor_subject_access",
            )
        ]


class CounselorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="counselor_profile",
    )

    employee_code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
    )

    subjects = models.ManyToManyField(
        "courses_module.Subject",
        through="CounselorSubjectAccess",
        related_name="counselors",
        blank=True,
    )

    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.user)
