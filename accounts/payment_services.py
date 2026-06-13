from decimal import Decimal

from .models import AdminPaymentSettings, Borlette


def get_admin_payment_settings(borlette: Borlette) -> AdminPaymentSettings:
    settings, _ = AdminPaymentSettings.objects.get_or_create(borlette=borlette)
    return settings


def get_admin_bet_limits(borlette: Borlette) -> dict:
    settings = get_admin_payment_settings(borlette)
    return {
        "max_boule": settings.max_boule,
        "max_loto3": settings.max_loto3,
        "max_loto4": settings.max_loto4,
        "max_loto5": settings.max_loto5,
        "max_mariage": settings.max_mariage,
    }


def compute_gain_mise_x_coeff(mise: Decimal, coeff: Decimal) -> Decimal:
    return (mise or Decimal("0")) * (coeff or Decimal("0"))


def compute_mariage_gratuit_gain(settings: AdminPaymentSettings) -> Decimal:
    return settings.mariage_gratuit_montant_fixe


def compute_mariage_gratuit_qty(settings: AdminPaymentSettings, paris_count: int) -> int:
    if not settings.mariage_gratuit_actif:
        return 0

    n = int(paris_count or 0)
    if n > settings.mariage_gratuit_seuil2:
        return int(settings.mariage_gratuit_qty2)
    if n > settings.mariage_gratuit_seuil1:
        return int(settings.mariage_gratuit_qty1)
    return 0
