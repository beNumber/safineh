from django.urls import path

from . import views

app_name = "courses_module"

urlpatterns = [
    # لیست و مدیریت عمومی دوره‌ها
    path("", views.CourseListView.as_view(), name="course_list"),
    path("my/", views.MyCoursesView.as_view(), name="my_courses"),
    path("create/", views.CourseCreateView.as_view(), name="course_create"),
    path("edit/<int:pk>/", views.CourseUpdateView.as_view(), name="course_edit"),
    path("delete/<int:pk>/", views.CourseDeleteView.as_view(), name="course_delete"),

    # بررسی و تأیید دوره‌ها توسط معتمد / مدیر
    path("review/", views.CourseReviewListView.as_view(), name="review_list"),
    path("review/<int:pk>/", views.CourseReviewView.as_view(), name="course_review"),

    # عملیات ادمین
    path("admin/<int:pk>/close/", views.AdminCourseCloseView.as_view(), name="course_close"),
    path("admin/<int:pk>/delete/", views.AdminCourseDeleteView.as_view(), name="admin_course_delete"),
    path("admin/<int:course_pk>/resources/create/", views.CourseResourceCreateView.as_view(), name="resource_create"),

    # مدیریت سرفصل‌ها (Course Sections)
    path("sections/<int:course_pk>/create/", views.SectionCreateView.as_view(), name="section_create"),
    path("sections/<int:pk>/edit/", views.SectionUpdateView.as_view(), name="section_edit"),
    path("sections/<int:pk>/delete/", views.SectionDeleteView.as_view(), name="section_delete"),

    # مدیریت جلسات و فایل‌ها (Course Episodes)
    path("episodes/<int:section_pk>/create/", views.EpisodeCreateView.as_view(), name="episode_create"),
    path("episodes/<int:pk>/edit/", views.EpisodeUpdateView.as_view(), name="episode_edit"),
    path("episodes/<int:pk>/delete/", views.EpisodeDeleteView.as_view(), name="episode_delete"),
    path("episodes/<int:pk>/download/", views.EpisodeDownloadView.as_view(), name="episode_download"),

    # تعاملات دوره و صفحه جزئیات
    # توجه: این مسیرها در انتها قرار گرفته‌اند تا الگوی <path:slug> مانع مسیرهای بالا نشود
    path("<path:slug>/enroll/", views.EnrollCourseView.as_view(), name="course_enroll"),
    path("<path:slug>/rate/", views.RateCourseView.as_view(), name="course_rate"),
    path("<path:slug>/", views.CourseDetailView.as_view(), name="course_detail"),
]
