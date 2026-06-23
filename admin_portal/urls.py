from django.urls import include, path

from . import views
from . import rapports_api
from . import agent_api
from . import results_api
from . import dashboard_api
from . import mariage_risk_api
from . import affiliate_admin
from . import partner_admin

app_name = "admin_portal"

urlpatterns = [
    path("login/", views.portal_login, name="login"),
    path("auto-login/", views.portal_auto_login, name="auto_login"),
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/data/", views.dashboard_data, name="dashboard_data"),
    path("information/", views.information, name="information"),
    path("audit/", views.audit_logs_list, name="audit_logs_list"),
    path("agents/", views.agents_list, name="agents"),
    path("agents/nouveau/", views.agent_create, name="agent_create"),
    path("agents/<int:agent_id>/", views.agent_detail, name="agent_detail"),
    path("agents/<int:agent_id>/modifier/", views.agent_edit, name="agent_edit"),
    path("agents/<int:agent_id>/suspendre/", views.agent_suspend, name="agent_suspend"),
    path("agents/<int:agent_id>/supprimer/", views.agent_delete, name="agent_delete"),
    path("agents/<int:agent_id>/reset-password/", views.agent_reset_password, name="agent_reset_password"),
    path("agents/<int:agent_id>/payer/", views.agent_payout, name="agent_payout"),
    path("agents/<int:agent_id>/retrait-caisse/", views.agent_cashbox_withdraw, name="agent_cashbox_withdraw"),
    path("agents/<int:agent_id>/reapprovisionner-caisse/", views.agent_cashbox_replenish, name="agent_cashbox_replenish"),
    path("tirages/", views.tirages_list, name="tirages"),
    path("tirages/nouveau/", views.tirage_create, name="tirage_create"),
    path("tirages/<int:tirage_id>/modifier/", views.tirage_edit, name="tirage_edit"),
    path("tirages/<int:tirage_id>/boules/", views.tirage_boules, name="tirage_boules"),
    path("tirages/<int:tirage_id>/mariages/", views.tirage_mariages, name="tirage_mariages"),
    path("tirages/<int:tirage_id>/loto3/", views.tirage_loto3, name="tirage_loto3"),
    path("tirages/<int:tirage_id>/loto4/", views.tirage_loto4, name="tirage_loto4"),
    path("tirages/<int:tirage_id>/loto5/", views.tirage_loto5, name="tirage_loto5"),
    path("tirages/<int:tirage_id>/risques/", views.tirage_risques, name="tirage_risques"),
    path("tirages/<int:tirage_id>/resultats/", views.tirage_resultats, name="tirage_resultats"),
    path("tirages/<int:tirage_id>/suspendre/", views.tirage_suspend, name="tirage_suspend"),
    path("tirages/<int:tirage_id>/supprimer/", views.tirage_delete, name="tirage_delete"),
    path("rapports/", views.rapports, name="rapports"),
    path("parametres/", views.parametres, name="parametres"),
    path("team/", views.team, name="team"),
    path("team/<int:staff_id>/edit/", views.team_edit, name="team_edit"),
    path("team/<int:staff_id>/suspend/", views.team_suspend, name="team_suspend"),
    path("team/<int:staff_id>/delete/", views.team_delete, name="team_delete"),
    path("tickets/", include(("tickets.urls", "tickets"), namespace="tickets")),
    # Dépenses
    path("depenses/", views.depenses_list, name="depenses_list"),
    path("depenses/nouveau/", views.depense_create, name="depense_create"),
    path("depenses/<int:depense_id>/modifier/", views.depense_edit, name="depense_edit"),
    path("depenses/<int:depense_id>/supprimer/", views.depense_delete, name="depense_delete"),
    # API Rapports
    path("api/rapports/summary/", rapports_api.api_rapports_summary, name="api_rapports_summary"),
    path("api/rapports/tirages/", rapports_api.api_rapports_tirages, name="api_rapports_tirages"),
    path("api/rapports/winners/", rapports_api.api_rapports_winners, name="api_rapports_winners"),
    path("api/rapports/results/", rapports_api.api_rapports_results, name="api_rapports_results"),
    path("api/rapports/depenses/", rapports_api.api_rapports_depenses, name="api_rapports_depenses"),
    path("api/rapports/export.csv", rapports_api.api_rapports_export, name="api_rapports_export"),
    path("api/tirages/", rapports_api.api_tirages_list, name="api_tirages_list"),
    # API Agents (Caisse via Ledger)
    path("api/agents/<int:agent_id>/stats/", agent_api.api_agent_stats, name="api_agent_stats"),
    path("api/agents/<int:agent_id>/pay/", agent_api.api_agent_pay, name="api_agent_pay"),
    path("api/agents/<int:agent_id>/ledger/", agent_api.api_agent_ledger, name="api_agent_ledger"),
    path("api/agents/<int:agent_id>/adjustment/", agent_api.api_agent_adjustment, name="api_agent_adjustment"),
    path("api/agents/<int:agent_id>/performance/", agent_api.api_agent_performance, name="api_agent_performance"),
    # API Résultats & Tickets (Phase B)
    path("api/tirages/results_status/", results_api.api_tirages_results_status, name="api_tirages_results_status"),
    path("api/tirages/<int:tirage_id>/results/", results_api.api_tirage_results, name="api_tirage_results"),
    path("api/tirages/<int:tirage_id>/winners/", results_api.api_winners_by_tirage, name="api_tirage_winners"),
    path("api/resultats/<int:resultat_id>/validate/", results_api.api_resultat_validate, name="api_resultat_validate"),
    path("api/resultats/<int:resultat_id>/reject/", results_api.api_resultat_reject, name="api_resultat_reject"),
    path("api/resultats/<int:resultat_id>/pending/", results_api.api_resultat_pending, name="api_resultat_pending"),
    path("api/resultats/<int:resultat_id>/flag/", results_api.api_resultat_flag, name="api_resultat_flag"),
    path("api/tickets/search/", results_api.api_ticket_search, name="api_ticket_search"),
    path("api/tickets/<str:ticket_id>/void/", results_api.api_ticket_void, name="api_ticket_void"),
    path("api/tickets/<str:ticket_id>/pay/", results_api.api_ticket_pay_admin, name="api_ticket_pay"),
    # API Mariage Risk (Phase J)
    path("api/tirages/<int:tirage_id>/mariage-blocks/", mariage_risk_api.api_mariage_blocks_list, name="api_mariage_blocks_list"),
    path("api/tirages/<int:tirage_id>/mariage-blocks/add/", mariage_risk_api.api_mariage_block_add, name="api_mariage_block_add"),
    path("api/tirages/<int:tirage_id>/mariage-blocks/remove/", mariage_risk_api.api_mariage_block_remove, name="api_mariage_block_remove"),
    # Dashboard API v1
    path("api/dashboard/summary/", dashboard_api.api_dashboard_summary, name="api_dashboard_summary"),
    path("api/dashboard/charts/", dashboard_api.api_dashboard_charts, name="api_dashboard_charts"),
    path("api/dashboard/tables/", dashboard_api.api_dashboard_tables, name="api_dashboard_tables"),
    path("api/dashboard/recommendations/", dashboard_api.api_dashboard_recommendations, name="api_dashboard_recommendations"),
    path("api/dashboard/full/", dashboard_api.api_dashboard_full, name="api_dashboard_full"),
    # Notifications API
    path("api/notifications/", dashboard_api.api_notifications_list, name="api_notifications_list"),
    path("api/notifications/mark-read/", dashboard_api.api_notifications_mark_read, name="api_notifications_mark_read"),
    # Affiliate Management (Admin)
    path("affiliates/", affiliate_admin.admin_affiliate_list, name="affiliate_list"),
    path("affiliates/withdrawals/", affiliate_admin.admin_affiliate_withdrawals, name="affiliate_withdrawals"),
    path("affiliates/withdrawals/<int:withdrawal_id>/approve/", affiliate_admin.admin_approve_withdrawal, name="approve_withdrawal"),
    # Partner Management (Admin)
    path("partners/", partner_admin.admin_partner_list, name="partner_list"),
    path("partners/create/", partner_admin.admin_create_partner, name="create_partner"),
    path("partners/<int:partner_id>/edit/", partner_admin.admin_edit_partner, name="edit_partner"),
    path("partners/<int:partner_id>/toggle/", partner_admin.admin_toggle_partner, name="toggle_partner"),
    path("partners/<int:partner_id>/delete/", partner_admin.admin_delete_partner, name="delete_partner"),
    # Subscription Billing (Stripe / MonCash)
    path("payment/", views.payment_view, name="payment"),
    path("payment/stripe/checkout/", views.stripe_checkout, name="stripe_checkout"),
    path("payment/moncash/checkout/", views.moncash_checkout, name="moncash_checkout"),
    path("payment/callback/stripe/", views.stripe_callback, name="stripe_callback"),
    path("payment/callback/moncash/", views.moncash_callback, name="moncash_callback"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("payment/cancel/", views.payment_cancel, name="payment_cancel"),
]

