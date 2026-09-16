from django.contrib import admin

from .models import PlanCompletion, PlanEntry


@admin.register(PlanEntry)
class PlanEntryAdmin(admin.ModelAdmin):
    list_display = (
        "display_title",
        "student",
        "weekday",
        "start_hour",
        "end_hour",
        "source",
        "assigned_by",
    )
    list_filter = ("weekday", "activity_type", "source", "color", "is_active")
    search_fields = (
        "title",
        "subject__title",
        "student__user__username",
        "student__user__first_name",
        "student__user__last_name",
    )
    autocomplete_fields = ("subject", "assigned_by")
    raw_id_fields = ("student",)


@admin.register(PlanCompletion)
class PlanCompletionAdmin(admin.ModelAdmin):
    list_display = ("entry", "week_start", "completed_at")
    list_filter = ("week_start",)
    search_fields = ("entry__title", "entry__student__user__username")
