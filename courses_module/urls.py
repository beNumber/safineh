from django.urls import path

from . import views

app_name = "courses_module"

urlpatterns = [
    path("", views.CourseListView.as_view(), name="course_list"),
    path("my/", views.MyCoursesView.as_view(), name="my_courses"),
    path("create/", views.CourseCreateView.as_view(), name="course_create"),
    path("edit/<int:pk>/", views.CourseUpdateView.as_view(), name="course_edit"),
    path("review/", views.CourseReviewListView.as_view(), name="review_list"),
    path("review/<int:pk>/", views.CourseReviewView.as_view(), name="course_review"),
    path("admin/<int:pk>/close/", views.AdminCourseCloseView.as_view(), name="course_close"),
    path("admin/<int:pk>/delete/", views.AdminCourseDeleteView.as_view(), name="course_delete"),
    # ``path`` accepts Unicode slugs (including Persian) while the built-in
    # slug converter only accepts ASCII characters.
    path("<path:slug>/enroll/", views.EnrollCourseView.as_view(), name="course_enroll"),
    path("<path:slug>/rate/", views.RateCourseView.as_view(), name="course_rate"),
    path("<path:slug>/", views.CourseDetailView.as_view(), name="course_detail"),
]
