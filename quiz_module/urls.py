from django.urls import path

from . import views

app_name = "quiz_module"

urlpatterns = [
    path("", views.quiz_list, name="quiz_list"),
    path("create/", views.quiz_create, name="quiz_create"),
    path("approval/", views.approval_queue, name="approval_queue"),
    path("api/students/", views.filter_students, name="filter_students"),
    path("<int:pk>/edit/", views.quiz_edit, name="quiz_edit"),
    path("<int:pk>/builder/", views.quiz_builder, name="quiz_builder"),
    path("<int:pk>/questions/create/", views.question_create, name="question_create"),
    path("<int:pk>/questions/<int:question_id>/edit/", views.question_edit, name="question_edit"),
    path("<int:pk>/questions/<int:question_id>/delete/", views.question_delete, name="question_delete"),
    path("<int:pk>/bank/", views.bank_import, name="bank_import"),
    path("<int:pk>/submit-review/", views.submit_for_review, name="submit_for_review"),
    path("<int:pk>/review/", views.review_quiz, name="review_quiz"),
    path("<int:pk>/start/", views.start_quiz, name="start_quiz"),
    path("<int:pk>/results/", views.quiz_results, name="quiz_results"),
    path("attempt/<int:attempt_id>/", views.attempt_view, name="attempt"),
    path("attempt/<int:attempt_id>/submit/", views.submit_attempt, name="submit_attempt"),
    path("attempt/<int:attempt_id>/result/", views.attempt_result, name="attempt_result"),
    path("attempt/<int:attempt_id>/grade/", views.grade_attempt, name="grade_attempt"),
    path("attempt/<int:attempt_id>/questions/<int:question_id>/save/", views.save_answer, name="save_answer"),
    path("attempt/<int:attempt_id>/events/", views.track_event, name="track_event"),
]
