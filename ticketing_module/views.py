from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from auth_module.decorators import role_required
from auth_module.models import UserRole

from .forms import (
    ModerationForm,
    ReferralForm,
    TicketCreateForm,
    TicketEditForm,
    TicketMessageForm,
)
from .models import (
    ModerationStatus,
    Ticket,
    TicketAuditLog,
    TicketMessage,
    TicketQueue,
    TicketStatus,
)
from .services import (
    STAFF_ROLES,
    auto_approve_for,
    can_access_ticket,
    route_after_initial_approval,
    student_profile_for,
    visible_tickets_for,
)


ALL_ROLES = (
    UserRole.STUDENT,
    UserRole.CONSULTANT,
    UserRole.PROVINCE_TRUSTEE,
    UserRole.CONTENT_MODERATOR,
    UserRole.ADMIN,
)


@role_required(*ALL_ROLES)
def ticket_list(request):
    tickets = visible_tickets_for(request.user)
    status = request.GET.get("status")
    ticket_type = request.GET.get("type")
    if status in TicketStatus.values:
        tickets = tickets.filter(status=status)
    if ticket_type:
        tickets = tickets.filter(ticket_type=ticket_type)

    return render(
        request,
        "ticketing_module/ticket_list.html",
        {
            "tickets": tickets,
            "status_choices": TicketStatus.choices,
            "selected_status": status,
            "selected_type": ticket_type,
        },
    )


@role_required(UserRole.STUDENT)
def ticket_create(request):
    student = student_profile_for(request.user)
    if not student:
        messages.error(request, "پروفایل دانش‌آموزی شما کامل نشده است.")
        return redirect("ticketing:list")

    if request.method == "POST":
        form = TicketCreateForm(request.POST, request.FILES, student=student)
        if form.is_valid():
            with transaction.atomic():
                ticket = form.save(commit=False)
                ticket.student = student
                ticket.current_queue = TicketQueue.MODERATOR
                ticket.status = TicketStatus.PENDING_APPROVAL
                ticket.save()
                TicketMessage.objects.create(
                    ticket=ticket,
                    sender=request.user,
                    content=form.cleaned_data["content"],
                    attachment=form.cleaned_data.get("attachment"),
                )
                TicketAuditLog.objects.create(
                    ticket=ticket,
                    actor=request.user,
                    action=TicketAuditLog.Action.CREATED,
                    to_queue=TicketQueue.MODERATOR,
                    description="ثبت تیکت توسط دانش‌آموز",
                )
            messages.success(request, "تیکت ثبت شد و پس از تأیید ناظر ارجاع می‌شود.")
            return redirect("ticketing:detail", pk=ticket.pk)
    else:
        form = TicketCreateForm(student=student)
    return render(request, "ticketing_module/ticket_form.html", {"form": form})


def _visible_messages(ticket, user):
    messages_qs = ticket.messages.select_related("sender", "reviewed_by")
    if user.is_superuser or user.role in {
        UserRole.CONTENT_MODERATOR,
        UserRole.PROVINCE_TRUSTEE,
        UserRole.ADMIN,
    }:
        return messages_qs
    if user.role == UserRole.STUDENT:
        return messages_qs.filter(
            Q(sender=user)
            | Q(moderation_status=ModerationStatus.APPROVED, is_internal=False)
        )
    return messages_qs.filter(
        Q(sender=user)
        | Q(moderation_status=ModerationStatus.APPROVED, is_internal=False)
    )


@role_required(*ALL_ROLES)
def ticket_detail(request, pk):
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            "student__user",
            "student__field__grade__school__province",
            "subject",
            "current_assignee_user",
        ),
        pk=pk,
    )
    if not can_access_ticket(request.user, ticket):
        raise PermissionDenied("این تیکت در محدوده دسترسی شما نیست.")

    previous_tickets = Ticket.objects.none()
    if request.user.role in STAFF_ROLES or request.user.is_superuser:
        previous_tickets = Ticket.objects.filter(
            student=ticket.student, subject=ticket.subject
        ).exclude(pk=ticket.pk).order_by("-created_at")[:10]

    can_moderate = request.user.is_superuser or request.user.role in {
        UserRole.CONTENT_MODERATOR,
        UserRole.ADMIN,
    }
    can_edit = request.user.is_superuser or request.user.role in {
        UserRole.PROVINCE_TRUSTEE,
        UserRole.ADMIN,
    }
    can_refer = request.user.is_superuser or request.user.role in {
        UserRole.CONSULTANT,
        UserRole.PROVINCE_TRUSTEE,
        UserRole.ADMIN,
    }
    return render(
        request,
        "ticketing_module/ticket_detail.html",
        {
            "ticket": ticket,
            "ticket_messages": _visible_messages(ticket, request.user),
            "message_form": TicketMessageForm(),
            "referral_form": ReferralForm(actor=request.user, ticket=ticket),
            "edit_form": TicketEditForm(instance=ticket),
            "previous_tickets": previous_tickets,
            "can_moderate": can_moderate,
            "can_edit": can_edit,
            "can_refer": can_refer,
        },
    )


@role_required(*ALL_ROLES)
def add_message(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if not can_access_ticket(request.user, ticket):
        raise PermissionDenied
    if ticket.status == TicketStatus.CLOSED:
        messages.error(request, "برای تیکت بسته‌شده نمی‌توان پیام فرستاد.")
        return redirect("ticketing:detail", pk=pk)

    form = TicketMessageForm(request.POST, request.FILES)
    if form.is_valid():
        with transaction.atomic():
            item = form.save(commit=False)
            item.ticket = ticket
            item.sender = request.user
            if auto_approve_for(request.user):
                item.moderation_status = ModerationStatus.APPROVED
                item.is_approved_by_moderator = True
                item.reviewed_by = request.user
                item.reviewed_at = timezone.now()
            item.save()
            TicketAuditLog.objects.create(
                ticket=ticket,
                actor=request.user,
                action=TicketAuditLog.Action.MESSAGE_SENT,
                description="پیام تأییدشده" if item.is_approved_by_moderator else "پیام در انتظار تأیید ناظر",
            )
            if not item.is_approved_by_moderator:
                ticket.status = TicketStatus.PENDING_APPROVAL
                ticket.save(update_fields=["status", "updated_at"])
        messages.success(
            request,
            "پیام ارسال شد. پس از تأیید ناظر نمایش داده می‌شود."
            if not item.is_approved_by_moderator
            else "پیام ارسال شد.",
        )
    else:
        messages.error(request, "متن پیام معتبر نیست.")
    return redirect("ticketing:detail", pk=pk)


@role_required(UserRole.CONTENT_MODERATOR, UserRole.ADMIN)
def moderation_queue(request):
    pending = TicketMessage.objects.filter(
        moderation_status=ModerationStatus.PENDING
    ).select_related(
        "ticket__student__user", "ticket__subject", "sender"
    ).order_by("created_at")
    return render(
        request, "ticketing_module/moderation_queue.html", {"pending_messages": pending}
    )


@role_required(UserRole.CONTENT_MODERATOR, UserRole.ADMIN)
def moderate_message(request, message_id):
    if request.method != "POST":
        raise PermissionDenied
    item = get_object_or_404(
        TicketMessage.objects.select_related("ticket", "sender"), pk=message_id
    )
    form = ModerationForm(request.POST)
    if form.is_valid() and item.moderation_status == ModerationStatus.PENDING:
        approved = form.cleaned_data["decision"] == "approve"
        with transaction.atomic():
            item.moderation_status = (
                ModerationStatus.APPROVED if approved else ModerationStatus.REJECTED
            )
            item.is_approved_by_moderator = approved
            item.reviewed_by = request.user
            item.reviewed_at = timezone.now()
            item.review_note = form.cleaned_data["note"]
            item.save(
                update_fields=[
                    "moderation_status",
                    "is_approved_by_moderator",
                    "reviewed_by",
                    "reviewed_at",
                    "review_note",
                ]
            )
            TicketAuditLog.objects.create(
                ticket=item.ticket,
                actor=request.user,
                action=(TicketAuditLog.Action.APPROVED if approved else TicketAuditLog.Action.REJECTED),
                description=form.cleaned_data["note"],
                metadata={"message_id": item.pk},
            )
            first_message = item.ticket.messages.order_by("created_at").first()
            if approved and first_message and first_message.pk == item.pk:
                route_after_initial_approval(item.ticket, request.user)
            elif approved and item.sender.role == UserRole.CONSULTANT:
                item.ticket.status = TicketStatus.RESOLVED
                item.ticket.save(update_fields=["status", "updated_at"])
            elif approved:
                item.ticket.status = TicketStatus.OPEN
                item.ticket.save(update_fields=["status", "updated_at"])
        messages.success(request, "نتیجه بررسی ثبت شد.")
    return redirect("ticketing:detail", pk=item.ticket_id)


@role_required(UserRole.CONSULTANT, UserRole.PROVINCE_TRUSTEE, UserRole.ADMIN)
def refer_ticket(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if not can_access_ticket(request.user, ticket):
        raise PermissionDenied
    form = ReferralForm(request.POST, actor=request.user, ticket=ticket)
    if form.is_valid():
        old_queue = ticket.current_queue
        old_user = ticket.current_assignee_user
        with transaction.atomic():
            ticket.current_queue = form.cleaned_data["queue"]
            ticket.current_assignee_user = form.cleaned_data["assignee"]
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.save(update_fields=["current_queue", "current_assignee_user", "status", "updated_at"])
            TicketAuditLog.objects.create(
                ticket=ticket,
                actor=request.user,
                action=TicketAuditLog.Action.REFERRED,
                from_queue=old_queue,
                to_queue=ticket.current_queue,
                from_user=old_user,
                to_user=ticket.current_assignee_user,
                description=form.cleaned_data["note"],
            )
        messages.success(request, "تیکت با موفقیت ارجاع شد.")
    else:
        messages.error(request, "اطلاعات ارجاع معتبر نیست.")
    return redirect("ticketing:detail", pk=pk)


@role_required(UserRole.PROVINCE_TRUSTEE, UserRole.ADMIN)
def edit_ticket(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if not can_access_ticket(request.user, ticket):
        raise PermissionDenied
    old_type, old_subject, old_status = ticket.ticket_type, ticket.subject, ticket.status
    form = TicketEditForm(request.POST, instance=ticket)
    if form.is_valid():
        with transaction.atomic():
            ticket = form.save()
            if old_type != ticket.ticket_type:
                TicketAuditLog.objects.create(
                    ticket=ticket, actor=request.user, action=TicketAuditLog.Action.TYPE_CHANGED,
                    description=f"{old_type} ← {ticket.ticket_type}",
                )
            if old_subject != ticket.subject:
                TicketAuditLog.objects.create(
                    ticket=ticket, actor=request.user, action=TicketAuditLog.Action.SUBJECT_CHANGED,
                    description=f"{old_subject or '-'} ← {ticket.subject or '-'}",
                )
            if old_status != ticket.status:
                TicketAuditLog.objects.create(
                    ticket=ticket, actor=request.user, action=TicketAuditLog.Action.STATUS_CHANGED,
                    description=f"{old_status} ← {ticket.status}",
                )
        messages.success(request, "اطلاعات تیکت و تاریخچه تغییرات ثبت شد.")
    else:
        messages.error(request, "اطلاعات تیکت معتبر نیست.")
    return redirect("ticketing:detail", pk=pk)
