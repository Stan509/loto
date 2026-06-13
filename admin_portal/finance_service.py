"""
FinanceReportService pour rapports financiers (Phase D).

Formule: Bénéfice Net = Mises - Gains Dus - Commissions - Dépenses
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import models
from django.db.models import Sum, Count, Q

from accounts.models import Borlette, Tirage, Expense, Resultat
from agent_portal.models import (
    Ticket, TicketStatus, AgentLedgerEntry, LedgerEntryType
)


class FinanceReportService:
    """Service de rapports financiers pour une borlette."""
    
    def __init__(self, borlette: Borlette):
        self.borlette = borlette
    
    def totals(
        self,
        period_start: date,
        period_end: date,
        tirage_id: int | None = None
    ) -> dict[str, Any]:
        """
        Calcule les totaux financiers pour une période.
        
        Returns:
            dict avec total_mises, total_gains_dus, total_commissions,
            total_depenses, benefice_net, somme_soldes_agents
        """
        # Base queryset tickets VALIDE (exclut ANNULE)
        tickets_qs = Ticket.objects.filter(
            borlette=self.borlette,
            statut=TicketStatus.VALIDE,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        )
        
        if tirage_id:
            tickets_qs = tickets_qs.filter(tirage_id=tirage_id)
        
        # Totaux tickets
        ticket_agg = tickets_qs.aggregate(
            total_mises=Sum("total_mise"),
            total_gains_dus=Sum("total_gain_du"),
        )
        total_mises = ticket_agg["total_mises"] or Decimal("0")
        total_gains_dus = ticket_agg["total_gains_dus"] or Decimal("0")
        
        # Commissions agents (COMMISSION_EARNED)
        commission_qs = AgentLedgerEntry.objects.filter(
            borlette=self.borlette,
            entry_type=LedgerEntryType.COMMISSION_EARNED,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        )
        if tirage_id:
            commission_qs = commission_qs.filter(related_ticket__tirage_id=tirage_id)
        
        total_commissions = commission_qs.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        
        # Dépenses
        expense_qs = Expense.objects.filter(
            borlette=self.borlette,
            date__gte=period_start,
            date__lte=period_end,
        )
        if tirage_id:
            expense_qs = expense_qs.filter(tirage_id=tirage_id)
        
        total_depenses = expense_qs.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        
        # Bénéfice net
        benefice_net = total_mises - total_gains_dus - total_commissions - total_depenses
        
        # Somme soldes agents (balance commission)
        from accounts.models import Agent
        agents = Agent.objects.filter(borlette=self.borlette, is_active=True)
        somme_soldes = Decimal("0")
        for agent in agents:
            balance = AgentLedgerEntry.get_agent_balance(agent)
            somme_soldes += balance.get("balance", Decimal("0"))
        
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_mises": total_mises,
            "total_gains_dus": total_gains_dus,
            "total_commissions": total_commissions,
            "total_depenses": total_depenses,
            "benefice_net": benefice_net,
            "somme_soldes_agents": somme_soldes,
            "tickets_count": tickets_qs.count(),
            "winners_count": tickets_qs.filter(is_winner=True).count(),
        }
    
    def by_tirage(
        self,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        """
        Agrégats groupés par tirage pour une période.
        """
        tirages = Tirage.objects.filter(borlette=self.borlette)
        
        results = []
        for tirage in tirages:
            tickets_qs = Ticket.objects.filter(
                borlette=self.borlette,
                tirage=tirage,
                statut=TicketStatus.VALIDE,
                created_at__date__gte=period_start,
                created_at__date__lte=period_end,
            )
            
            agg = tickets_qs.aggregate(
                total_mises=Sum("total_mise"),
                total_gains_dus=Sum("total_gain_du"),
                count=Count("id"),
            )
            
            if agg["count"] > 0:
                results.append({
                    "tirage_id": tirage.id,
                    "tirage_nom": tirage.nom,
                    "tickets_count": agg["count"],
                    "total_mises": agg["total_mises"] or Decimal("0"),
                    "total_gains_dus": agg["total_gains_dus"] or Decimal("0"),
                    "winners_count": tickets_qs.filter(is_winner=True).count(),
                })
        
        return sorted(results, key=lambda x: x["total_mises"], reverse=True)
    
    def winners(
        self,
        period_start: date,
        period_end: date,
        tirage_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Liste des tickets gagnants avec détails lignes.
        """
        tickets_qs = Ticket.objects.filter(
            borlette=self.borlette,
            statut=TicketStatus.VALIDE,
            is_winner=True,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        ).select_related("agent", "tirage").prefetch_related("lignes")
        
        if tirage_id:
            tickets_qs = tickets_qs.filter(tirage_id=tirage_id)
        
        tickets_qs = tickets_qs.order_by("-total_gain_du")[:limit]
        
        results = []
        for ticket in tickets_qs:
            winning_lines = []
            for line in ticket.lignes.all():
                if line.is_winner:
                    winning_lines.append({
                        "jeu": line.jeu,
                        "valeur": line.valeur,
                        "mise": float(line.mise),
                        "gain_du": float(line.gain_du),
                        "win_context": line.win_context,
                    })
            
            results.append({
                "ticket_id": str(ticket.id),
                "numero": ticket.numero_ticket,
                "agent": ticket.agent.nom if ticket.agent else "N/A",
                "tirage": ticket.tirage.nom if ticket.tirage else "N/A",
                "total_mise": float(ticket.total_mise),
                "total_gain_du": float(ticket.total_gain_du),
                "total_gain_paye": float(ticket.total_gain_paye),
                "is_paid": ticket.is_paid,
                "created_at": ticket.created_at.isoformat(),
                "winning_lines": winning_lines,
            })
        
        return results
    
    def results(
        self,
        period_start: date,
        period_end: date,
        tirage_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Résultats des tirages pour une période (session courante).
        """
        tirages = Tirage.objects.filter(borlette=self.borlette)
        if tirage_id:
            tirages = tirages.filter(id=tirage_id)
        
        results = []
        for tirage in tirages:
            # Chercher résultat pour session courante
            resultat = Resultat.objects.filter(
                tirage=tirage,
                session_key=tirage.session_key,
            ).first()
            
            if resultat:
                results.append({
                    "tirage_id": tirage.id,
                    "tirage_nom": tirage.nom,
                    "session_key": str(tirage.session_key),
                    "lot1": resultat.lot1,
                    "lot2": resultat.lot2,
                    "lot3": resultat.lot3,
                    "chiffre_loto3": resultat.chiffre_loto3,
                    "loto3": resultat.loto3,
                    "loto4_opt1": resultat.loto4_opt1,
                    "loto4_opt2": resultat.loto4_opt2,
                    "loto4_opt3": resultat.loto4_opt3,
                    "loto5_opt1": resultat.loto5_opt1,
                    "loto5_opt2": resultat.loto5_opt2,
                    "loto5_opt3": resultat.loto5_opt3,
                    "computed_at": resultat.computed_at.isoformat() if resultat.computed_at else None,
                })
        
        return results
    
    def depenses_list(
        self,
        period_start: date,
        period_end: date,
        search: str | None = None,
        tirage_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Liste des dépenses avec filtres.
        """
        qs = Expense.objects.filter(
            borlette=self.borlette,
            date__gte=period_start,
            date__lte=period_end,
        ).select_related("category", "tirage", "created_by")
        
        if tirage_id:
            qs = qs.filter(tirage_id=tirage_id)
        
        if search:
            qs = qs.filter(
                Q(description__icontains=search) |
                Q(category__name__icontains=search)
            )
        
        qs = qs.order_by("-date", "-created_at")[:limit]
        
        results = []
        for expense in qs:
            results.append({
                "id": expense.id,
                "amount": float(expense.amount),
                "date": expense.date.isoformat(),
                "category": expense.category.name if expense.category else None,
                "description": expense.description,
                "tirage": expense.tirage.nom if expense.tirage else None,
                "created_by": expense.created_by.username if expense.created_by else None,
                "created_at": expense.created_at.isoformat(),
            })
        
        return results
