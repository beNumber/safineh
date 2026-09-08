from django.urls import path

from . import views

app_name = "ticketing"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("new/", views.ticket_create, name="create"),
    path("moderation/", views.moderation_queue, name="moderation_queue"),
    path("messages/<int:message_id>/moderate/", views.moderate_message, name="moderate_message"),
    path("<int:pk>/", views.ticket_detail, name="detail"),
    path("<int:pk>/message/", views.add_message, name="add_message"),
    path("<int:pk>/refer/", views.refer_ticket, name="refer"),
    path("<int:pk>/edit/", views.edit_ticket, name="edit"),
]
