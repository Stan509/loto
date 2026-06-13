from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("preview/", views.ticket_preview, name="preview"),
    path("preview/confirm/", views.ticket_confirm, name="confirm"),
]
