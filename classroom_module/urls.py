from django.urls import path
from . import views

app_name = "classroom_module"
urlpatterns = [
    path("", views.class_list, name="list"),
    path("new/", views.class_form, name="create"),
    path("<int:pk>/edit/", views.class_form, name="edit"),
    path("<int:pk>/delete/", views.class_delete, name="delete"),
]
