from django.contrib import admin
from django.utils.html import format_html

from .models import Article, Category, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "status",
        "is_featured",
        "published_at",
        "views_count",
        "view_on_site_link",
    )
    list_filter = ("status", "is_featured", "category", "tags")
    search_fields = ("title", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("status", "is_featured")
    list_select_related = ("category", "author")
    filter_horizontal = ("tags",)
    readonly_fields = ("views_count", "created_at", "updated_at")
    date_hierarchy = "published_at"

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": ("title", "slug", "category", "tags", "author")
        }),
        ("محتوا", {
            "fields": ("summary", "content", "image")
        }),
        ("انتشار", {
            "fields": ("status", "is_featured", "published_at")
        }),
        ("آمار و تاریخچه", {
            "fields": ("views_count", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def save_model(self, request, obj, form, change):
        """ثبت خودکار کاربر واردشده به‌عنوان نویسندهٔ خبر جدید."""
        if not change and not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="نمایش در سایت")
    def view_on_site_link(self, obj):
        """دکمهٔ مشاهده مستقیم خبر از داخل جدول لیست اخبار"""
        return format_html(
            '<a class="button" href="{}" target="_blank" style="padding: 3px 8px; background-color: #2563eb; color: white; border-radius: 4px; text-decoration: none;">مشاهده خبر</a>',
            obj.get_absolute_url()
        )
