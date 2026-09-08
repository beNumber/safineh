from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    path("blog/", include("blog_module.urls")),
    path(
        "news/",
        include("news_module.urls"),
    ),
    path('dashboard/',include('dashboard_module.urls')),
    path('auth/',include('auth_module.urls')),
    path('questions/', include('questions_module.urls')),
    path('', include("landing_module.urls")),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
