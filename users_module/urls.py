from django.urls import path

from .views import curriculum_import, curriculum_template, user_create

app_name = "users_module"
urlpatterns = [
    path("create/", user_create, name="user_create"),
    path("curriculum/import/", curriculum_import, name="curriculum_import"),
    path("curriculum/import/<str:kind>/", curriculum_import, name="curriculum_import_kind"),
    path("curriculum/template/<str:kind>/", curriculum_template, name="curriculum_template"),
]
