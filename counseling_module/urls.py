from django.urls import path

from . import views

app_name = "counseling"

urlpatterns = [
    path("manage/", views.manage_assignments, name="manage"),
    path("manage/<int:student_id>/assign/", views.assign_student, name="assign"),
    path("manage/<int:student_id>/remove/", views.remove_assignment, name="remove"),
    path("my-students/", views.my_students, name="my_students"),
    path("my-consultant/", views.my_consultant, name="my_consultant"),
    path("my-consultant/ticket/", views.create_private_ticket, name="private_ticket"),
]
