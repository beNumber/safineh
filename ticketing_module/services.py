from django.db.models import Q
from django.utils import timezone

from auth_module.models import Consultant, ProvinceTrustee, UserRole

from .models import (
    ModerationStatus,
    Ticket,
    TicketAuditLog,
    TicketQueue,
    TicketStatus,
    TicketType,
)


STAFF_ROLES = {
    UserRole.CONSULTANT,
    UserRole.PROVINCE_TRUSTEE,
    UserRole.CONTENT_MODERATOR,
    UserRole.ADMIN,
}


def student_profile_for(user):
    return user.student_profiles.select_related(
        "field__grade__school__province"
    ).first()


def consultant_scope_ids(user, student, subject, psychology=False):
    scopes = Consultant.objects.filter(consultant=user).prefetch_related("accesses")
    ids = []
    for scope in scopes:
        if psychology:
            if scope.can_answer_psychology:
                ids.append(scope.pk)
        elif scope.matches_student(student, subject):
            ids.append(scope.pk)
    return ids


def consultant_can_access(user, ticket):
    if ticket.current_assignee_user_id == user.id:
        return True
    if ticket.current_queue != TicketQueue.CONSULTANT:
        return False
    return bool(
        consultant_scope_ids(
            user,
            ticket.student,
            ticket.subject,
            psychology=ticket.ticket_type == TicketType.PSYCHOLOGY,
        )
    )


def trustee_can_access(user, ticket):
    return ProvinceTrustee.objects.filter(
        user=user, province_id=ticket.province.id
    ).exists()


def can_access_ticket(user, ticket):
    if user.is_superuser or user.role == UserRole.ADMIN:
        return True
    if ticket.is_private_consultation:
        if user.role == UserRole.STUDENT:
            return ticket.student.user_id == user.id
        if user.role == UserRole.CONTENT_MODERATOR:
            return True
        if user.role == UserRole.CONSULTANT:
            return (
                ticket.current_queue == TicketQueue.CONSULTANT
                and ticket.current_assignee_user_id == user.id
            )
        return False
    if user.role == UserRole.STUDENT:
        return ticket.student.user_id == user.id
    if user.role == UserRole.CONTENT_MODERATOR:
        return True
    if user.role == UserRole.PROVINCE_TRUSTEE:
        return trustee_can_access(user, ticket)
    if user.role == UserRole.CONSULTANT:
        return consultant_can_access(user, ticket)
    return False


def visible_tickets_for(user):
    queryset = Ticket.objects.select_related(
        "student__user",
        "student__field__grade__school__province",
        "subject",
        "current_assignee_user",
    )
    if user.is_superuser or user.role == UserRole.ADMIN:
        return queryset
    if user.role == UserRole.CONTENT_MODERATOR:
        return queryset
    if user.role == UserRole.STUDENT:
        return queryset.filter(student__user=user)
    if user.role == UserRole.PROVINCE_TRUSTEE:
        provinces = ProvinceTrustee.objects.filter(user=user).values("province_id")
        return queryset.filter(
            student__field__grade__school__province_id__in=provinces,
            is_private_consultation=False,
        )
    if user.role == UserRole.CONSULTANT:
        private_ids = queryset.filter(
            is_private_consultation=True,
            current_queue=TicketQueue.CONSULTANT,
            current_assignee_user=user,
        ).values_list("pk", flat=True)
        candidate_ids = []
        for ticket in queryset.filter(
            Q(current_queue=TicketQueue.CONSULTANT) | Q(current_assignee_user=user),
            is_private_consultation=False,
        ):
            if consultant_can_access(user, ticket):
                candidate_ids.append(ticket.pk)
        return queryset.filter(Q(pk__in=candidate_ids) | Q(pk__in=private_ids))
    return queryset.none()


def route_after_initial_approval(ticket, actor):
    if ticket.is_private_consultation:
        queue = TicketQueue.CONSULTANT
    elif ticket.ticket_type == TicketType.TECHNICAL:
        queue = TicketQueue.TRUSTEE
    else:
        queue = TicketQueue.CONSULTANT
    old_queue = ticket.current_queue
    ticket.current_queue = queue
    if not ticket.is_private_consultation:
        ticket.current_assignee_user = None
    ticket.status = TicketStatus.OPEN
    ticket.save(update_fields=["current_queue", "current_assignee_user", "status", "updated_at"])
    TicketAuditLog.objects.create(
        ticket=ticket,
        actor=actor,
        action=TicketAuditLog.Action.REFERRED,
        from_queue=old_queue,
        to_queue=queue,
        to_user=ticket.current_assignee_user,
        description=(
            "ارسال تیکت خصوصی به مشاور اختصاصی پس از تأیید ناظر"
            if ticket.is_private_consultation
            else "ارجاع خودکار پس از تأیید پرسش اولیه"
        ),
    )


def auto_approve_for(user):
    return user.is_superuser or user.role in {
        UserRole.PROVINCE_TRUSTEE,
        UserRole.CONTENT_MODERATOR,
        UserRole.ADMIN,
    }


def close_ticket(ticket, actor):
    ticket.status = TicketStatus.CLOSED
    ticket.closed_at = timezone.now()
    ticket.save(update_fields=["status", "closed_at", "updated_at"])
    TicketAuditLog.objects.create(
        ticket=ticket, actor=actor, action=TicketAuditLog.Action.CLOSED
    )
