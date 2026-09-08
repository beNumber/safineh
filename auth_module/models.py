from django.contrib.auth.models import AbstractUser
from django.db import models
from users_module.models import Access, School, FieldOfStudy, Grade, Province, Subject


class UserRole(models.TextChoices):
    STUDENT = 'STUDENT', 'دانش‌آموز'
    CONSULTANT = 'CONSULTANT', 'مشاور'
    PROVINCE_TRUSTEE = 'PROVINCE_TRUSTEE', 'معتمد استان'
    CONTENT_MODERATOR = 'CONTENT_MODERATOR', 'ناظر محتوا'
    ADMIN = 'ADMIN', 'مدیر سیستم'


class User(AbstractUser):
    role = models.CharField(
        max_length=20, choices=UserRole.choices, default=UserRole.STUDENT
    )
    national_code = models.CharField(max_length=10, unique=True, null=True)
    phone_number = models.CharField(max_length=11, unique=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[('MALE', 'پسر'), ('FEMALE', 'دختر')],
        null=True,
        blank=True,
    )


# ماتریس دسترسی مشاور: مقادیر Null به معنی "همه" است
class Consultant(models.Model):
    consultant = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='scopes'
    )
    accesses = models.ManyToManyField(Access)


class Student(models.Model):
    user = models.ForeignKey(User, models.CASCADE)
    field = models.ForeignKey(FieldOfStudy, models.CASCADE)
