from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Consultant, ProvinceTrustee, Student, User


@admin.register(User)
class ProjectUserAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'role', 'is_active', 'is_superuser')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('اطلاعات و دسترسی‌های سامانه', {
            'fields': ('role', 'national_code', 'phone_number', 'gender', 'accesses'),
            'description': 'فقط سوپریوزر می‌تواند دسترسی کاربران غیر دانش‌آموز را تعیین کند.',
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('اطلاعات و دسترسی‌های سامانه', {
            'fields': ('role', 'national_code', 'phone_number', 'gender', 'accesses'),
        }),
    )
    filter_horizontal = ('groups', 'user_permissions', 'accesses')

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.extend(('accesses', 'is_superuser', 'user_permissions', 'groups'))
        return readonly

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.role == 'STUDENT':
            form.instance.accesses.clear()
        elif request.user.is_superuser and form.instance.accesses.filter(
            name__in=('create_question', 'create_chapter', 'create_subject')
        ).exists() and not form.instance.is_staff:
            form.instance.is_staff = True
            form.instance.save(update_fields=['is_staff'])


admin.site.register(Consultant)
admin.site.register(Student)
admin.site.register(ProvinceTrustee)
