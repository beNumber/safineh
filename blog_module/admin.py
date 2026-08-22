from django.contrib import admin
from .models import Category, Post, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "published_at")
    list_filter = ("status", "category", "tags")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    fields = (
        "title",
        "slug",
        "summary",
        "cover",
        "content_image",
        "content_video",
        "body",
        "category",
        "author",
        "tags",
        "status",
        "published_at",
    )
