from django.urls import path

from .views import people_activity

app_name = "reports_module"

urlpatterns = [
    path("activities/", people_activity, name="people_activity"),
]
