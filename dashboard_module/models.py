from django.db import models


class ModuleAvailability(models.Model):
    class Code(models.TextChoices):
        QUESTION_BANK = "question_bank", "بانک سؤالات"
        COURSES = "courses", "دوره‌ها و درس‌ها"
        QUIZZES = "quizzes", "آزمون‌ها"

    code = models.CharField(max_length=30, choices=Code.choices, unique=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_code_display()} - {'فعال' if self.is_active else 'غیرفعال'}"


class UserPresence(models.Model):
    user = models.OneToOneField("auth_module.User", on_delete=models.CASCADE, related_name="site_presence")
    last_seen = models.DateTimeField(db_index=True)


class PresencePeak(models.Model):
    day = models.DateField(unique=True)
    count = models.PositiveIntegerField(default=0)
    recorded_at = models.DateTimeField()
