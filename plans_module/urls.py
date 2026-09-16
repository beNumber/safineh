from django.urls import path

from . import views

app_name = "plans_module"

urlpatterns = [
    path("", views.plan_board, name="board"),
    path("<int:pk>/edit/", views.plan_edit, name="edit"),
    path("<int:pk>/delete/", views.plan_delete, name="delete"),
    path("<int:pk>/toggle/", views.toggle_completion, name="toggle_completion"),
]
