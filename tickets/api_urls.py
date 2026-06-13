from django.urls import path

from . import api_views

urlpatterns = [
    path(
        "signup-admin/",
        api_views.signup_admin_borlette,
        name="signup_admin_borlette",
    ),
    path(
        "tirage/<int:tirage_id>/numeros_disponibles/",
        api_views.tirage_numeros_disponibles,
        name="tirage_numeros_disponibles",
    ),
]
