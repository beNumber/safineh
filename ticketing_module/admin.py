from django.contrib import admin

from .models import Ticket, TicketAuditLog, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ("created_at",)


class TicketAuditInline(admin.TabularInline):
    model = TicketAuditLog
    extra = 0
    readonly_fields = ("actor", "action", "description", "created_at")
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "student", "ticket_type", "current_queue", "status", "updated_at")
    list_filter = ("ticket_type", "current_queue", "status")
    search_fields = ("title", "student__user__username", "student__user__first_name", "student__user__last_name")
    inlines = (TicketMessageInline, TicketAuditInline)

    def save_model(self, request, obj, form, change):
        old = Ticket.objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        if not old:
            TicketAuditLog.objects.create(
                ticket=obj,
                actor=request.user,
                action=TicketAuditLog.Action.CREATED,
                to_queue=obj.current_queue,
                description="ایجاد از طریق Django Admin",
            )
            return
        if old.current_queue != obj.current_queue or old.current_assignee_user_id != obj.current_assignee_user_id:
            TicketAuditLog.objects.create(
                ticket=obj,
                actor=request.user,
                action=TicketAuditLog.Action.REFERRED,
                from_queue=old.current_queue,
                to_queue=obj.current_queue,
                from_user=old.current_assignee_user,
                to_user=obj.current_assignee_user,
                description="ارجاع از طریق Django Admin",
            )
        if old.ticket_type != obj.ticket_type:
            TicketAuditLog.objects.create(
                ticket=obj,
                actor=request.user,
                action=TicketAuditLog.Action.TYPE_CHANGED,
                description=f"{old.ticket_type} ← {obj.ticket_type}",
            )
        if old.subject_id != obj.subject_id:
            TicketAuditLog.objects.create(
                ticket=obj,
                actor=request.user,
                action=TicketAuditLog.Action.SUBJECT_CHANGED,
                description=f"{old.subject or '-'} ← {obj.subject or '-'}",
            )
        if old.status != obj.status:
            TicketAuditLog.objects.create(
                ticket=obj,
                actor=request.user,
                action=TicketAuditLog.Action.STATUS_CHANGED,
                description=f"{old.status} ← {obj.status}",
            )


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "sender", "moderation_status", "created_at")
    list_filter = ("moderation_status", "is_internal")


@admin.register(TicketAuditLog)
class TicketAuditLogAdmin(admin.ModelAdmin):
    list_display = ("ticket", "action", "actor", "from_queue", "to_queue", "created_at")
    list_filter = ("action", "from_queue", "to_queue")
    readonly_fields = ("created_at",)
