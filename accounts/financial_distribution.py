from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.http import HttpRequest
from django.db import transaction

from accounts.audit import log_audit
from accounts.models import (
    AuditAction,
    Borlette,
    User,
    PromoCode,
    FinancialTransaction,
    FinancialTransactionType,
    FinancialSplit,
    FinancialSplitRole,
)

logger = logging.getLogger(__name__)


_DEC_0 = Decimal("0")


def _d(v: Any) -> Decimal:
    if isinstance(v, Decimal):
        return v
    if v is None:
        return _DEC_0
    return Decimal(str(v))


@dataclass(frozen=True)
class DistributionResult:
    owner: Decimal
    associate_1: Decimal
    associate_2: Decimal
    affiliate: Decimal
    cash: Decimal

    meta: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "associate_1": self.associate_1,
            "associate_2": self.associate_2,
            "affiliate": self.affiliate,
            "cash": self.cash,
            "meta": self.meta,
        }


def calculate_distribution(
    borlette: Borlette,
    total_agents: int,
    *,
    months_active: int,
    actor_user: User | None = None,
    request: HttpRequest | None = None,
) -> dict[str, Decimal]:
    """Calcul centralisé de la distribution financière.

    IMPORTANT:
    - Backend only
    - Un seul endroit calcule l’argent

    Formules (verbatim) basées sur la spec du projet:
    eligible = borlette.agents_eligible_share
    non_eligible = total_agents - eligible

    price_per_agent = 1250
    eligible_revenue = eligible * price_per_agent
    non_eligible_revenue = non_eligible * price_per_agent

    base = 1000
    bonus = 250

    eligible_base = eligible * base
    eligible_bonus = eligible * bonus

    owner = 0.40 * eligible_base
    associate_1 = 0.25 * eligible_base
    associate_2 = 0.25 * eligible_base
    cash = 0.10 * eligible_base

    if months_active <= 6:
        affiliate = eligible_bonus
        owner_bonus = 0
    else:
        affiliate = 0
        owner_bonus = eligible_bonus

    owner += non_eligible_revenue
    owner += owner_bonus
    """

    total_agents_i = max(0, int(total_agents or 0))

    eligible_setting_i = int(getattr(borlette, "agents_eligible_share", 0) or 0)
    eligible_i = min(max(0, eligible_setting_i), total_agents_i)
    non_eligible_i = max(0, total_agents_i - eligible_i)

    price_per_agent = _d(1250)
    base = _d(1000)
    bonus = _d(250)

    eligible_revenue = _d(eligible_i) * price_per_agent
    non_eligible_revenue = _d(non_eligible_i) * price_per_agent

    eligible_base = _d(eligible_i) * base
    eligible_bonus = _d(eligible_i) * bonus

    owner = _d("0.40") * eligible_base
    associate_1 = _d("0.25") * eligible_base
    associate_2 = _d("0.25") * eligible_base
    cash = _d("0.10") * eligible_base

    if int(months_active or 0) <= 6:
        affiliate = eligible_bonus
        owner_bonus = _DEC_0
    else:
        affiliate = _DEC_0
        owner_bonus = eligible_bonus

    owner = owner + non_eligible_revenue
    owner = owner + owner_bonus

    payload_meta: dict[str, Any] = {
        "total_agents": total_agents_i,
        "eligible_setting": eligible_setting_i,
        "eligible": eligible_i,
        "non_eligible": non_eligible_i,
        "months_active": int(months_active or 0),
        "price_per_agent": str(price_per_agent),
        "base": str(base),
        "bonus": str(bonus),
        "eligible_revenue": str(eligible_revenue),
        "non_eligible_revenue": str(non_eligible_revenue),
        "eligible_base": str(eligible_base),
        "eligible_bonus": str(eligible_bonus),
        "owner_bonus": str(owner_bonus),
        "result": {
            "owner": str(owner),
            "associate_1": str(associate_1),
            "associate_2": str(associate_2),
            "affiliate": str(affiliate),
            "cash": str(cash),
        },
    }

    logger.info(
        "FINANCIAL_DISTRIBUTION_CALC borlette_id=%s total_agents=%s eligible=%s non_eligible=%s months_active=%s result_owner=%s",
        getattr(borlette, "id", None),
        total_agents_i,
        eligible_i,
        non_eligible_i,
        int(months_active or 0),
        str(owner),
    )

    log_audit(
        action=AuditAction.FINANCIAL_DISTRIBUTION_CALC,
        entity_type="Borlette",
        entity_id=str(getattr(borlette, "id", "")),
        borlette=borlette,
        actor_user=actor_user,
        meta=payload_meta,
        request=request,
    )

    return {
        "owner": owner,
        "associate_1": associate_1,
        "associate_2": associate_2,
        "affiliate": affiliate,
        "cash": cash,
    }


@transaction.atomic
def create_ledger_transaction_after_distribution(
    *,
    borlette: Borlette,
    tx_type: str,
    total_amount: Decimal,
    total_agents: int,
    months_active: int,
    promo_code: PromoCode | None = None,
    actor_user: User | None = None,
    request: HttpRequest | None = None,
) -> FinancialTransaction:
    total_agents_i = max(0, int(total_agents or 0))
    eligible_setting_i = int(getattr(borlette, "agents_eligible_share", 0) or 0)
    eligible_i = min(max(0, eligible_setting_i), total_agents_i)

    dist = calculate_distribution(
        borlette,
        total_agents_i,
        months_active=months_active,
        actor_user=actor_user,
        request=request,
    )

    tx = FinancialTransaction.objects.create(
        borlette=borlette,
        promo_code=promo_code,
        type=tx_type,
        total_amount=_d(total_amount),
        months_active=max(0, int(months_active or 0)),
        agents_count=total_agents_i,
        eligible_agents=eligible_i,
    )

    affiliate_user = getattr(promo_code, "owner", None) if promo_code else None

    FinancialSplit.objects.bulk_create(
        [
            FinancialSplit(transaction=tx, user=None, role=FinancialSplitRole.OWNER, amount=_d(dist["owner"])),
            FinancialSplit(transaction=tx, user=None, role=FinancialSplitRole.ASSOCIATE_1, amount=_d(dist["associate_1"])),
            FinancialSplit(transaction=tx, user=None, role=FinancialSplitRole.ASSOCIATE_2, amount=_d(dist["associate_2"])),
            FinancialSplit(transaction=tx, user=affiliate_user, role=FinancialSplitRole.AFFILIATE, amount=_d(dist["affiliate"])),
            FinancialSplit(transaction=tx, user=None, role=FinancialSplitRole.CASH, amount=_d(dist["cash"])),
        ]
    )

    log_audit(
        action=AuditAction.FINANCIAL_DISTRIBUTION_CALC,
        entity_type="FinancialTransaction",
        entity_id=str(tx.pk),
        borlette=borlette,
        actor_user=actor_user,
        meta={
            "transaction_type": tx_type,
            "total_amount": str(tx.total_amount),
            "agents_count": tx.agents_count,
            "eligible_agents": tx.eligible_agents,
            "months_active": tx.months_active,
            "promo_code": getattr(promo_code, "code", None),
        },
        request=request,
    )

    return tx


def create_subscription_ledger_transaction(
    *,
    borlette: Borlette,
    total_agents: int,
    months_active: int,
    promo_code: PromoCode | None = None,
    actor_user: User | None = None,
    request: HttpRequest | None = None,
) -> FinancialTransaction:
    total_agents_i = max(0, int(total_agents or 0))
    total_amount = _d(total_agents_i) * _d(1250)
    return create_ledger_transaction_after_distribution(
        borlette=borlette,
        tx_type=FinancialTransactionType.SUBSCRIPTION,
        total_amount=total_amount,
        total_agents=total_agents_i,
        months_active=months_active,
        promo_code=promo_code,
        actor_user=actor_user,
        request=request,
    )
