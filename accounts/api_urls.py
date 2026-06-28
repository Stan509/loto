from django.urls import path

from . import api_views
from . import pricing_api
from . import signup_api

app_name = "accounts_api"

urlpatterns = [
    path("signup/", signup_api.api_signup, name="signup"),
    path("signup/verify-code/", signup_api.api_verify_code, name="signup_verify_code"),
    path("affiliate/register/", api_views.api_affiliate_register, name="affiliate_register"),
    path("affiliate/update-code/", api_views.api_affiliate_update_code, name="affiliate_update_code"),
    path("affiliate/withdraw/", api_views.api_affiliate_withdraw, name="affiliate_withdraw"),
    path("affiliate/balance/", api_views.api_affiliate_balance, name="affiliate_balance"),
    path("affiliate/withdrawals/", api_views.api_affiliate_withdrawals, name="affiliate_withdrawals"),
    path("superadmin/withdraw/<int:withdrawal_id>/approve/", api_views.api_superadmin_withdraw_approve, name="superadmin_withdraw_approve"),
    path("superadmin/withdraw/<int:withdrawal_id>/reject/", api_views.api_superadmin_withdraw_reject, name="superadmin_withdraw_reject"),
    path("superadmin/withdraw/<int:withdrawal_id>/mark-paid/", api_views.api_superadmin_withdraw_mark_paid, name="superadmin_withdraw_mark_paid"),
    # Pricing API endpoints
    path("pricing/summary/", pricing_api.pricing_summary_api, name="pricing_summary"),
    path("pricing/calculate/", pricing_api.calculate_price_api, name="pricing_calculate"),
    path("pricing/examples/", pricing_api.example_calculations_api, name="pricing_examples"),
    path("pricing/affiliate-commission/", pricing_api.calculate_affiliate_commission_api, name="pricing_affiliate_commission"),
    path("pricing/affiliate-total/", pricing_api.calculate_affiliate_total_api, name="pricing_affiliate_total"),
]
