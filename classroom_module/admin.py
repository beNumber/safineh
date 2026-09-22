from django.contrib import admin
from .models import OnlineClass

@admin.register(OnlineClass)
class OnlineClassAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active",)
