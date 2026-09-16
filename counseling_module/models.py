from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from auth_module.models import Student, UserRole


class StudentConsultantAssignment(models.Model):
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name="consultant_assignment",
        verbose_name="دانش‌آموز",
    )
    consultant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="counseling_assignments",
        verbose_name="مشاور",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_counseling_assignments",
        verbose_name="تخصیص‌دهنده",
    )
    note = models.CharField("یادداشت داخلی", max_length=300, blank=True)
    created_at = models.DateTimeField("زمان شروع", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)

    class Meta:
        ordering = ["student__user__last_name", "student__user__first_name"]
        verbose_name = "تخصیص دانش‌آموز به مشاور"
        verbose_name_plural = "تخصیص دانش‌آموزان به مشاوران"
        indexes = [models.Index(fields=["consultant", "updated_at"])]

    def __str__(self):
        return f"{self.student} ← {self.consultant}"

    def clean(self):
        super().clean()
        if self.consultant_id and self.consultant.role != UserRole.CONSULTANT:
            raise ValidationError({"consultant": "کاربر انتخاب‌شده باید نقش مشاور داشته باشد."})
