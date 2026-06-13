"""
URLs API REST Agent
"""
from django.urls import path

from . import api_views

app_name = "agent_api"

urlpatterns = [
    # Auth
    path("auth/login/", api_views.api_login, name="login"),

    # Tirages
    path("tirages/", api_views.api_tirages_actifs, name="tirages"),
    path("tirage/<int:tirage_id>/disponibles/", api_views.api_tirage_disponibles, name="tirage_disponibles"),

    # Tickets
    path("ticket/preview/", api_views.api_ticket_preview, name="ticket_preview"),
    path("ticket/create/", api_views.api_ticket_create, name="ticket_create"),
    path("ticket/create-multi/", api_views.api_ticket_create_multi, name="ticket_create_multi"),
    path("ticket/<str:ticket_id>/", api_views.api_ticket_detail, name="ticket_detail"),
    path("ticket/<str:ticket_id>/print/", api_views.api_ticket_print, name="ticket_print"),
    path("ticket/<str:ticket_id>/pdf/", api_views.api_ticket_pdf, name="ticket_pdf"),

    # Historique & Résultats
    path("historique/", api_views.api_historique, name="historique"),
    path("resultats/", api_views.api_resultats, name="resultats"),

    # Dashboard
    path("dashboard/", api_views.api_dashboard, name="dashboard"),

    # Caisse Agent
    path("caisse/", api_views.api_agent_caisse, name="caisse"),

    # Commission Agent (retrait + historique)
    path("commission/withdraw/", api_views.api_withdraw_commission, name="commission_withdraw"),
    path("commission/history/", api_views.api_commission_history, name="commission_history"),

    # Recherche & Paiement tickets (Phase B)
    path("tickets/list/", api_views.api_ticket_list_agent, name="ticket_list"),
    path("tickets/search/", api_views.api_ticket_search_agent, name="ticket_search"),
    path("tickets/group/<str:group_id>/", api_views.api_ticket_group_search, name="ticket_group_search"),
    path("ticket/<str:ticket_id>/pay/", api_views.api_ticket_pay_agent, name="ticket_pay"),
    path("ticket/<str:ticket_id>/void/", api_views.api_ticket_void_agent, name="ticket_void"),
    
    # Blueprint pour refaire fiche (Phase C2)
    path("ticket/<str:ticket_id>/blueprint/", api_views.api_ticket_blueprint, name="ticket_blueprint"),
    
    # Heartbeat (agent online status)
    path("heartbeat/", api_views.api_agent_heartbeat, name="heartbeat"),
    
    # Health check (no auth - for connection test)
    path("health/", api_views.api_health, name="health"),
    
    # Device registration (offline HMAC)
    path("device/register/", api_views.api_device_register, name="device_register"),
    
    # Agent config (offline settings)
    path("config/", api_views.api_agent_config, name="agent_config"),
]
