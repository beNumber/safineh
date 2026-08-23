from django.urls import path
from .views import dash_view
urlpatterns = [
    path('',dash_view)
]