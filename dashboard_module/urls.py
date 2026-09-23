from django.urls import path
from .views import dash_view, mark_content_notifications_read
urlpatterns = [
    path('', dash_view, name="dashboard"),
    path('notifications/read/', mark_content_notifications_read, name="notifications_read"),
]
