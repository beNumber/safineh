from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from auth_module.models import Consultant, Student
from users_module.models import Subject


class TicketType(models.TextChoices):
    LESSON = "LESSON", "درسی"
    TECHNICAL = "TECHNICAL", "فنی"
    PSYCHOLOGY = "PSYCHOLOGY", "روانشناسی و مشاوره"


class TicketStatus(models.TextChoices):
    PENDING_APPROVAL = "PENDING_APPROVAL", "در انتظار تأیید ناظر"
    OPEN = "OPEN", "باز"
    IN_PROGRESS = "IN_PROGRESS", "در حال پیگیری"
    RESOLVED = "RESOLVED", "پاسخ داده شده"
    CLOSED = "CLOSED", "بسته شده"


class TicketQueue(models.TextChoices):
    MODERATOR = "MODERATOR", "ناظر محتوا"
    CONSULTANT = "CONSULTANT", "مشاور"
    TRUSTEE = "TRUSTEE", "معتمد استان"
    ADMIN = "ADMIN", "مدیر سیستم"


class ModerationStatus(models.TextChoices):
    PENDING = "PENDING", "در انتظار بررسی"
    APPROVED = "APPROVED", "تأیید شده"
    REJECTED = "REJECTED", "رد شده"


class Ticket(models.Model):
    title = models.CharField(max_length=255)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="tickets"
    )
    ticket_type = models.CharField(
        max_length=20, choices=TicketType.choices, default=TicketType.LESSON
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.SET_NULL, null=True, blank=True
    )

    # برای سازگاری با نسخه اولیه نگه داشته شده است.
    current_assignee = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    current_queue = models.CharField(
        max_length=20,
        choices=TicketQueue.choices,
        default=TicketQueue.MODERATOR,
    )
    current_assignee_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.PENDING_APPROVAL,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["current_queue", "status"]),
            models.Index(fields=["ticket_type", "subject"]),
        ]
        verbose_name = "تیکت"
        verbose_name_plural = "تیکت‌ها"

    def __str__(self):
        return f"#{self.pk} - {self.title}"

    def clean(self):
        if self.ticket_type == TicketType.LESSON and not self.subject_id:
            raise ValidationError({"subject": "برای تیکت درسی انتخاب درس الزامی است."})
        if self.ticket_type != TicketType.LESSON and self.subject_id:
            raise ValidationError(
                {"subject": "برای موضوع فنی یا روانشناسی نباید درس انتخاب شود."}
            )

    @property
    def province(self):
        return self.student.province


class TicketMessage(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_messages"
    )
    content = models.TextField()
    attachment = models.FileField(
        upload_to="ticket_attachments/%Y/%m/", null=True, blank=True
    )
    moderation_status = models.CharField(
        max_length=10,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
    )
    # برای سازگاری با داده‌های نسخه اولیه.
    is_approved_by_moderator = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_ticket_messages",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    is_internal = models.BooleanField(
        default=False,
        help_text="یادداشت داخلی برای عوامل سامانه و غیرقابل نمایش به دانش‌آموز",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["moderation_status", "created_at"])]
        verbose_name = "پیام تیکت"
        verbose_name_plural = "پیام‌های تیکت"

    def __str__(self):
        return f"پیام {self.sender} در تیکت #{self.ticket_id}"


class TicketAuditLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "CREATED", "ایجاد تیکت"
        MESSAGE_SENT = "MESSAGE_SENT", "ارسال پیام"
        APPROVED = "APPROVED", "تأیید محتوا"
        REJECTED = "REJECTED", "رد محتوا"
        REFERRED = "REFERRED", "ارجاع تیکت"
        SUBJECT_CHANGED = "SUBJECT_CHANGED", "تغییر درس"
        TYPE_CHANGED = "TYPE_CHANGED", "تغییر موضوع"
        STATUS_CHANGED = "STATUS_CHANGED", "تغییر وضعیت"
        CLOSED = "CLOSED", "بستن تیکت"
        REOPENED = "REOPENED", "بازگشایی تیکت"

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="logs"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=30, choices=Action.choices)

    # فیلدهای مشاور نسخه قبلی برای جلوگیری از حذف اطلاعات باقی مانده‌اند.
    from_assignee = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    to_assignee = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_referrals_from",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_referrals_to",
    )
    from_queue = models.CharField(
        max_length=20, choices=TicketQueue.choices, null=True, blank=True
    )
    to_queue = models.CharField(
        max_length=20, choices=TicketQueue.choices, null=True, blank=True
    )
    description = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "رویداد تیکت"
        verbose_name_plural = "گردش تیکت‌ها"

    def __str__(self):
        return f"{self.get_action_display()} - تیکت #{self.ticket_id}"
