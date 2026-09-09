from django.contrib import admin

from .models import Course, CourseEnrollment, CourseEpisode, CourseRating, CourseSection


class CourseEpisodeInline(admin.TabularInline):
    model = CourseEpisode
    extra = 1


@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order")
    inlines = [CourseEpisodeInline]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "approval_status", "start_date", "is_active")
    list_filter = ("approval_status", "is_active", "level")
    search_fields = ("title", "topic", "author__username")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("subjects", "allowed_fields", "allowed_grades", "allowed_provinces")


admin.site.register(CourseEnrollment)
admin.site.register(CourseRating)
