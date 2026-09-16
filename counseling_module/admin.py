from django.contrib import admin

from .models import StudentConsultantAssignment


@admin.register(StudentConsultantAssignment)
class StudentConsultantAssignmentAdmin(admin.ModelAdmin):
    list_display = ("student", "consultant", "assigned_by", "updated_at")
    list_select_related = ("student__user", "consultant", "assigned_by")
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "student__user__username",
        "consultant__first_name",
        "consultant__last_name",
        "consultant__username",
    )
