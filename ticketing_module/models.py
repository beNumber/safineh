from django.db import models
from auth_module.models import Student,Consultant,User
from users_module.models import Subject
class TicketType(models.TextChoices):
    LESSON = 'LESSON', 'درسی'
    TECHNICAL = 'TECHNICAL', 'فنی'
    PSYCHOLOGY = 'PSYCHOLOGY', 'روانشناسی و مشاوره'


class TicketStatus(models.TextChoices):
    PENDING_APPROVAL = 'PENDING_APPROVAL', 'در انتظار تایید ناظر'
    OPEN = 'OPEN', 'باز'
    IN_PROGRESS = 'IN_PROGRESS', 'در حال پیگیری'
    RESOLVED = 'RESOLVED', 'پاسخ داده شده'
    CLOSED = 'CLOSED', 'بسته شده'


class Ticket(models.Model):
    title = models.CharField(max_length=255)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='tickets'
    )
    ticket_type = models.CharField(
        max_length=20,
        choices=TicketType.choices,
        default=TicketType.LESSON,
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.SET_NULL, null=True, blank=True
    )
    current_assignee = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
    )
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.PENDING_APPROVAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class TicketMessage(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    is_approved_by_moderator = models.BooleanField(
        default=False
    )  # برای معتمد و ادمین به صورت خودکار True می‌شود
    created_at = models.DateTimeField(auto_now_add=True)


class TicketAuditLog(models.Model):
    """ثبت گردش تیکت، ارجاعات و تغییر موضوع"""

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='logs'
    )
    actor = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(
        max_length=100
    )  # مثلا: 'REFERRED_TO_TRUSTEE', 'CHANGED_LESSON', 'MODERATOR_APPROVED'
    from_assignee = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    to_assignee = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
