"""
AgentCommissionService: Calcul des commissions et solde agent.

Solde agent = somme(commissions sur mises) - somme(payouts)
La commission n'est jamais supprimée, elle est "payée" via AgentPayout.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.db import models, transaction
from django.utils import timezone

if TYPE_CHECKING:
    from accounts.models import Agent, User


class AgentCommissionService:
    """Service de gestion des commissions et paiements agents."""

    @staticmethod
    def get_agent_stats(*, agent, period_start: date | None = None, period_end: date | None = None) -> dict:
        """
        Calcule les statistiques d'un agent sur une période.
        
        Args:
            agent: L'agent concerné
            period_start: Date de début (défaut: début du mois)
            period_end: Date de fin (défaut: aujourd'hui)
        
        Returns:
            dict avec: total_mises, total_gains_du, commission_earned, total_payouts, solde
        """
        from agent_portal.models import Ticket, TicketStatus

        if period_start is None:
            today = timezone.localdate()
            period_start = today.replace(day=1)
        if period_end is None:
            period_end = timezone.localdate()

        # Mises et gains sur la période
        tickets = Ticket.objects.filter(
            agent=agent,
            borlette=agent.borlette,
            statut=TicketStatus.VALIDE,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        )

        agg = tickets.aggregate(
            total_mises=models.Sum("total_mise"),
            total_gains_du=models.Sum("total_gain_du"),
            tickets_count=models.Count("id"),
            winners_count=models.Count("id", filter=models.Q(is_winner=True)),
        )

        total_mises = agg.get("total_mises") or Decimal("0")
        total_gains_du = agg.get("total_gains_du") or Decimal("0")
        tickets_count = agg.get("tickets_count") or 0
        winners_count = agg.get("winners_count") or 0

        # Commission = pourcentage sur mises
        commission_pct = agent.commission or Decimal("0")
        commission_earned = (total_mises * commission_pct) / Decimal("100")

        return {
            "period_start": period_start,
            "period_end": period_end,
            "tickets_count": tickets_count,
            "winners_count": winners_count,
            "total_mises": total_mises,
            "total_gains_du": total_gains_du,
            "benefice_borlette": total_mises - total_gains_du,
            "commission_pct": commission_pct,
            "commission_earned": commission_earned,
        }

    @staticmethod
    def get_agent_balance(*, agent) -> dict:
        """
        Calcule le solde actuel d'un agent.
        
        Solde = commissions totales cumulées - payouts totaux
        
        Returns:
            dict avec: total_commission, total_payouts, solde
        """
        from accounts.models import AgentPayout
        from agent_portal.models import Ticket, TicketStatus

        # Total des mises de l'agent (toutes périodes confondues)
        total_mises = Ticket.objects.filter(
            agent=agent,
            borlette=agent.borlette,
            statut=TicketStatus.VALIDE,
        ).aggregate(total=models.Sum("total_mise"))["total"] or Decimal("0")

        # Commission cumulée
        commission_pct = agent.commission or Decimal("0")
        total_commission = (total_mises * commission_pct) / Decimal("100")

        # Total des paiements effectués
        total_payouts = AgentPayout.objects.filter(
            agent=agent
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

        solde = total_commission - total_payouts

        return {
            "total_mises": total_mises,
            "commission_pct": commission_pct,
            "total_commission": total_commission,
            "total_payouts": total_payouts,
            "solde": solde,
        }

    @staticmethod
    @transaction.atomic
    def create_payout(*, agent, amount: Decimal, created_by, note: str = "") -> "AgentPayout":
        """
        Crée un paiement pour l'agent.
        
        Args:
            agent: L'agent à payer
            amount: Montant du paiement
            created_by: Utilisateur admin qui effectue le paiement
            note: Note optionnelle
        
        Returns:
            AgentPayout créé
        """
        from accounts.models import AgentPayout

        if amount <= 0:
            raise ValueError("Le montant doit être positif")

        payout = AgentPayout.objects.create(
            agent=agent,
            amount=amount,
            created_by=created_by,
            note=note,
        )

        return payout

    @staticmethod
    def get_payout_history(*, agent, limit: int = 50) -> list:
        """
        Récupère l'historique des paiements d'un agent.
        
        Returns:
            Liste des payouts
        """
        from accounts.models import AgentPayout

        payouts = AgentPayout.objects.filter(
            agent=agent
        ).select_related("created_by").order_by("-created_at")[:limit]

        return list(payouts)

    @staticmethod
    def get_commission_by_period(*, agent, periods: list[tuple[date, date]]) -> list[dict]:
        """
        Calcule les commissions par période pour un agent.
        
        Args:
            agent: L'agent concerné
            periods: Liste de tuples (start_date, end_date)
        
        Returns:
            Liste de dicts avec stats par période
        """
        results = []
        for start, end in periods:
            stats = AgentCommissionService.get_agent_stats(
                agent=agent,
                period_start=start,
                period_end=end,
            )
            results.append(stats)
        return results
