from django.contrib import admin
from .models import Access, FieldOfStudy, Grade, Province, School, Subject


class SuperuserManagedAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Access)
class AccessAdmin(SuperuserManagedAdmin):
    list_display = ('get_name_display', 'subject')
    list_filter = ('name', 'subject')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'code', 'field', 'is_active')
    list_filter = ('is_active', 'field')
    search_fields = ('title', 'code')

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return (
            request.user.role != 'STUDENT'
            and request.user.accesses.filter(
                name=Access.Code.CREATE_SUBJECT,
                subject__isnull=True,
            ).exists()
        )

    def has_module_permission(self, request):
        return request.user.is_superuser or request.user.has_project_access(
            Access.Code.CREATE_SUBJECT
        )

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_project_access(
            Access.Code.CREATE_SUBJECT, obj
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        accesses = request.user.accesses.filter(name=Access.Code.CREATE_SUBJECT)
        if accesses.filter(subject__isnull=True).exists():
            return queryset
        return queryset.filter(pk__in=accesses.values_list('subject_id', flat=True))

    def has_change_permission(self, request, obj=None):
        return request.user.has_project_access(Access.Code.CREATE_SUBJECT, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


admin.site.register(Province)
admin.site.register(School)
admin.site.register(Grade)
admin.site.register(FieldOfStudy)
