from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    # مسیرهای CKEditor برای آپلود تصاویر داخل متن خبر
    path("ckeditor/", include("ckeditor_uploader.urls")),

    # هدایت صفحه اصلی سایت به صفحه اخبار
    path(
        "",
        lambda request: redirect("news_modal:article_list"),
    ),

    # آدرس‌های اپ اخبار
    path(
        "news/",
        include("news_modal.urls"),
    ),
]


# نمایش فایل‌های آپلودی فقط در حالت توسعه
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
