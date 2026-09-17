from django.urls import path
from . import views

app_name = "questions_module"

urlpatterns = [
    # مدیریت سوالات
    path("", views.question_list, name="question_list"),
    path("create/", views.question_create, name="question_create"),
    path("chapters/create/", views.chapter_create, name="chapter_create"),
    path("subjects/create/", views.subject_create, name="subject_create"),
    path("<int:pk>/edit/", views.question_edit, name="question_edit"),
    path("<int:pk>/delete/", views.question_delete, name="question_delete"),
    path("approval/", views.approval_queue, name="approval_queue"),
    path("approval/<int:pk>/review/", views.review_question, name="review_question"),

    # ویزارد ۳ مرحله‌ای
    path("wizard/mode/", views.choose_mode, name="choose_mode"),
    path("wizard/courses/", views.select_courses, name="select_courses"),
    path("wizard/chapters/", views.select_chapters, name="select_chapters"),
    path("wizard/reset/", views.reset_wizard, name="reset_wizard"),

    # تمرین
    path("practice/start/", views.start_practice, name="start_practice"),
    path("practice/<int:pk>/", views.practice_session_view, name="practice_session"),
    path("practice/<int:pk>/submit/", views.practice_submit, name="practice_submit"),
    path("practice/<int:pk>/questions/<int:question_id>/answer/", views.practice_answer, name="practice_answer"),
    path("practice/<int:pk>/questions/<int:question_id>/reveal/", views.practice_reveal, name="practice_reveal"),
    path("practice/<int:pk>/result/", views.practice_result, name="practice_result"),

    # آزمون
    path("exam/start/", views.start_exam, name="start_exam"),
    path("exam/<int:pk>/", views.exam_session_view, name="exam_session"),
    path("exam/<int:pk>/submit/", views.exam_submit, name="exam_submit"),
    path("exam/<int:pk>/questions/<int:question_id>/save/", views.exam_save_answer, name="exam_save_answer"),
    path("exam/<int:pk>/result/", views.exam_result, name="exam_result"),
]
