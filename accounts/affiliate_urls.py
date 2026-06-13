from django.urls import path

from . import affiliate_views

app_name = "affiliate"

urlpatterns = [
    path("dashboard/", affiliate_views.affiliate_dashboard, name="dashboard"),
    path("withdrawals/", affiliate_views.affiliate_withdrawals, name="withdrawals"),
    path("referrals/", affiliate_views.affiliate_referrals_list, name="referrals"),
    path("settings/", affiliate_views.affiliate_settings, name="settings"),
    path("api/referrals/", affiliate_views.affiliate_referrals_api, name="api_referrals"),
    path("api/submit-result/", affiliate_views.affiliate_submit_result, name="api_submit_result"),
]
