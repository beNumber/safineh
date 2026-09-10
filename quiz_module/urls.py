from django.urls import path
from . import views

app_name = 'quiz_module'
urlpatterns = [
    path('', views.quiz_dashboard, name='dashboard'),
    path('create/', views.quiz_create, name='create'),
    path('<int:pk>/edit/', views.quiz_edit, name='edit'),
    path('<int:pk>/delete/', views.quiz_delete, name='delete'),
    path('<int:pk>/questions/add/', views.question_add, name='question_add'),
    path('approval/', views.approval_queue, name='approval'),
    path('approval/<int:pk>/', views.review_quiz, name='review'),
    path('<int:pk>/start/', views.quiz_start, name='start'),
    path('attempt/<int:pk>/', views.quiz_attempt, name='attempt'),
    path('attempt/<int:pk>/submit/', views.quiz_submit, name='submit'),
    path('reports/', views.quiz_reports, name='reports'),
]
