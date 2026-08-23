from django.urls import path
from . import views

app_name = 'landing_module'

urlpatterns = [
    path('', views.landing_home_view, name='index'),
]
