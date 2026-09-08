from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Consultant, ProvinceTrustee, Student, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("اطلاعات سامانه", {"fields": ("role", "national_code", "phone_number", "gender")}),
    )
    list_display = ("username", "get_full_name", "role", "phone_number", "is_active")
    list_filter = UserAdmin.list_filter + ("role", "gender")


@admin.register(Consultant)
class ConsultantScopeAdmin(admin.ModelAdmin):
    list_display = (
        "consultant", "province", "school", "grade", "field", "subject",
        "can_answer_tickets", "can_answer_psychology",
    )
    list_filter = (
        "gender", "province", "can_manage_question_bank", "can_answer_tickets",
        "can_answer_psychology", "can_create_exam", "can_upload_course",
    )
    autocomplete_fields = ("consultant",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("user", "field")
    autocomplete_fields = ("user",)


@admin.register(ProvinceTrustee)
class ProvinceTrusteeAdmin(admin.ModelAdmin):
    list_display = ("user", "province")
    list_filter = ("province",)
    autocomplete_fields = ("user",)
