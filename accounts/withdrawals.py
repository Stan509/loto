from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from accounts.models import FinancialSplit, FinancialSplitRole, WithdrawalRequest, WithdrawalStatus, User


def get_affiliate_balance(user: User) -> Decimal:
    total_earned = (
        FinancialSplit.objects.filter(user=user, role=FinancialSplitRole.AFFILIATE)
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0")
    )

    total_withdrawn = (
        WithdrawalRequest.objects.filter(user=user, status=WithdrawalStatus.PAID)
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0")
    )

    return (total_earned or Decimal("0")) - (total_withdrawn or Decimal("0"))
