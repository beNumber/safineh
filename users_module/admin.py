from django.contrib import admin
from .models import Province, School, Grade, FieldOfStudy, Subject, Access


# ==========================================
# Inlines for nested inline management
# ==========================================

class AccessInline(admin.TabularInline):
    model = Access
    extra = 1


class SubjectInline(admin.TabularInline):
    model = Subject
    extra = 1
    show_change_link = True


class FieldOfStudyInline(admin.TabularInline):
    model = FieldOfStudy
    extra = 1
    show_change_link = True


class GradeInline(admin.TabularInline):
    model = Grade
    extra = 1
    show_change_link = True


class SchoolInline(admin.TabularInline):
    model = School
    extra = 1
    show_change_link = True


# ==========================================
# Model Admins
# ==========================================

@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_display', 'schools_count')
    list_filter = ('name',)
    search_fields = ('name',)
    inlines = [SchoolInline]

    @admin.display(description='نام استان')
    def name_display(self, obj):
        return obj.get_name_display()

    @admin.display(description='تعداد مدارس')
    def schools_count(self, obj):
        return obj.schools.count()


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'province_display', 'grades_count')
    list_filter = ('province',)
    search_fields = ('name', 'province__name')
    autocomplete_fields = ('province',)
    inlines = [GradeInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('province')

    @admin.display(description='استان', ordering='province__name')
    def province_display(self, obj):
        return obj.province.get_name_display()

    @admin.display(description='تعداد پایه‌ها')
    def grades_count(self, obj):
        return obj.grades.count()


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'code', 'school', 'province_name', 'is_active')
    list_filter = ('is_active', 'school__province', 'school')
    search_fields = ('title', 'code', 'school__name')
    autocomplete_fields = ('school',)
    list_editable = ('is_active',)
    inlines = [FieldOfStudyInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('school__province')

    @admin.display(description='استان', ordering='school__province__name')
    def province_name(self, obj):
        return obj.school.province.get_name_display()


@admin.register(FieldOfStudy)
class FieldOfStudyAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'code', 'grade', 'school_name', 'is_active')
    list_filter = ('is_active', 'grade__school__province', 'grade__school')
    search_fields = ('title', 'code', 'grade__title', 'grade__school__name')
    autocomplete_fields = ('grade',)
    list_editable = ('is_active',)
    inlines = [SubjectInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('grade__school__province')

    @admin.display(description='مدرسه', ordering='grade__school__name')
    def school_name(self, obj):
        return obj.grade.school.name


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'code', 'field', 'grade_title', 'school_name', 'is_active')
    list_filter = ('is_active', 'field__grade__school__province', 'field__grade__school')
    search_fields = ('title', 'code', 'field__title', 'field__grade__title', 'field__grade__school__name')
    autocomplete_fields = ('field',)
    list_editable = ('is_active',)
    inlines = [AccessInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'field__grade__school__province'
        )

    @admin.display(description='پایه', ordering='field__grade__title')
    def grade_title(self, obj):
        return obj.field.grade.title

    @admin.display(description='مدرسه', ordering='field__grade__school__name')
    def school_name(self, obj):
        return obj.field.grade.school.name


@admin.register(Access)
class AccessAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_display', 'subject', 'subject_field', 'subject_grade', 'subject_school')
    list_filter = ('name', 'subject__field__grade__school__province')
    search_fields = ('name', 'subject__title', 'subject__code')
    autocomplete_fields = ('subject',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'subject__field__grade__school__province'
        )

    @admin.display(description='نوع دسترسی', ordering='name')
    def name_display(self, obj):
        return obj.get_name_display()

    @admin.display(description='رشته', ordering='subject__field__title')
    def subject_field(self, obj):
        return obj.subject.field.title

    @admin.display(description='پایه', ordering='subject__field__grade__title')
    def subject_grade(self, obj):
        return obj.subject.field.grade.title

    @admin.display(description='مدرسه', ordering='subject__field__grade__school__name')
    def subject_school(self, obj):
        return obj.subject.field.grade.school.name
