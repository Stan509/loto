"""URL configuration for partner views."""
from django.urls import path

from . import partner_views

app_name = "partner"

urlpatterns = [
    path("dashboard/", partner_views.partner_dashboard, name="dashboard"),
    path("borlettes/", partner_views.partner_borlettes, name="borlettes"),
    path("subscriptions/", partner_views.partner_subscriptions, name="subscriptions"),
    path("tirages/", partner_views.partner_tirages, name="tirages"),
    path("results/", partner_views.partner_results, name="results"),
    path("affiliates/", partner_views.partner_affiliates, name="affiliates"),
    path("withdrawals/", partner_views.partner_withdrawals, name="withdrawals"),
    path("bulk-renew/", partner_views.bulk_renew_subscriptions, name="bulk_renew"),
    path("submit-result/<int:tirage_id>/", partner_views.partner_submit_result, name="submit_result"),
    path("confirm-withdrawal/<int:withdrawal_id>/", partner_views.partner_confirm_withdrawal, name="confirm_withdrawal"),
    path("renew-subscription/<int:subscription_id>/", partner_views.partner_renew_subscription, name="renew_subscription"),
    path("toggle-affiliate/<int:user_id>/", partner_views.toggle_affiliate_status, name="toggle_affiliate"),
]
