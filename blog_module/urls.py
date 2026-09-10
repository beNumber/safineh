from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="post_list"),
    # Use ``path`` instead of Django's ASCII-only ``slug`` converter so
    # Persian/Unicode slugs generated in the admin resolve correctly.
    path("post/<path:slug>/", views.post_detail, name="post_detail"),
    path("category/<path:slug>/", views.category_posts, name="category_posts"),
    path("tag/<path:slug>/", views.tag_posts, name="tag_posts"),
    path("search/", views.post_search, name="post_search"),
]
