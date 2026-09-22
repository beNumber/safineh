from django.urls import path

from .views import user_create

app_name = "users_module"
urlpatterns = [path("create/", user_create, name="user_create")]
