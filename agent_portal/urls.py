from django.urls import path

from . import views

app_name = "agent"

urlpatterns = [
    path("fiche/", views.fiche, name="fiche"),
    path("historique/", views.historique, name="historique"),
    path("resultat/", views.resultat, name="resultat"),
    path("score/", views.score, name="score"),
    path("statistiques/", views.statistiques, name="statistiques"),
    path("tchala/", views.tchala, name="tchala"),
]
