from django.urls import path
from . import views

app_name = "news_module"

urlpatterns = [
    # نمایش عمومی اخبار
    path("", views.article_list, name="article_list"),
    path(
        "article/<str:slug>/",
        views.article_detail,
        name="article_detail",
    ),
    
    # مدیریت اخبار
    path(
        "manage/article/create/",
        views.article_create,
        name="article_create",
    ),
    path(
        "manage/article/<str:slug>/edit/",
        views.article_update,
        name="article_update",
    ),
    path(
        "manage/article/<str:slug>/delete/",
        views.article_delete,
        name="article_delete",
    ),
]
