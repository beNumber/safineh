from django.urls import path
from .views import dash_view, mark_content_notifications_read, module_settings, toggle_module
urlpatterns = [
    path('', dash_view, name="dashboard"),
    path('modules/', module_settings, name="module_settings"),
    path('notifications/read/', mark_content_notifications_read, name="notifications_read"),
    path('modules/<str:code>/toggle/', toggle_module, name="toggle_module"),
]
