from django.conf import settings
from django.db import models
from django.utils import timezone
import jdatetime


class OnlineClass(models.Model):
    title = models.CharField("عنوان کلاس", max_length=150)
    description = models.TextField("توضیحات", blank=True, max_length=600)
    meeting_url = models.URLField("لینک ورود")
    starts_at = models.DateTimeField("زمان شروع", db_index=True)
    ends_at = models.DateTimeField("زمان پایان", db_index=True)
    is_active = models.BooleanField("فعال", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_online_classes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = "کلاس آنلاین"
        verbose_name_plural = "کلاس‌های آنلاین"

    @property
    def is_live(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at

    @property
    def jalali_date(self):
        return jdatetime.date.fromgregorian(date=timezone.localtime(self.starts_at).date()).strftime("%Y/%m/%d")

    def __str__(self):
        return self.title
