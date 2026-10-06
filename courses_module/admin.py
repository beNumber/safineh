from django.contrib import admin
from .models import (
    Course,
    CourseEnrollment,
    CourseEpisode,
    CourseRating,
    CourseSection,
    CourseResource,
)


class CourseEpisodeInline(admin.TabularInline):
    model = CourseEpisode
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "approval_status", "start_date", "is_active")
    list_filter = ("approval_status", "is_active", "level")
    search_fields = ("title", "topic", "author__username")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("subjects", "allowed_fields", "allowed_grades", "allowed_provinces")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # سوپرادمین همه دوره‌ها رو می‌بینه، ادمین عادی فقط دوره‌های خودش رو
        if request.user.is_superuser:
            return qs
        return qs.filter(author=request.user)

    def save_model(self, request, obj, form, change):
        # اگر ادمین عادی در حال ایجاد دوره بود، خودکار نویسنده دوره ست شود
        if not change and not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_active")
    search_fields = ("title", "course__title")
    list_filter = ("is_active",)
    autocomplete_fields = ("course",)  # قابلیت سرچ زنده و تایپ کردن نام دوره
    inlines = [CourseEpisodeInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(course__author=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # محدود کردن لیست دوره‌ها در زمان انتخاب دوره برای سرفصل
        if db_field.name == "course" and not request.user.is_superuser:
            kwargs["queryset"] = Course.objects.filter(author=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(CourseEnrollment)
admin.site.register(CourseRating)
admin.site.register(CourseResource)
