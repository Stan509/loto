"""
Dashboard Service - KPI Aggregations for Admin Dashboard
Scope: Strict par borlette
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import Agent, Borlette, Tirage, Expense, AgentPayout
from agent_portal.models import (
    Ticket, TicketStatus, TicketPayout, 
    AgentLedgerEntry, LedgerEntryType,
    AgentCashboxEntry, CashboxEntryType
)


def get_period_dates(period: str) -> tuple[date, date]:
    """
    Retourne (start_date, end_date) selon la période.
    Périodes: today, 7d, 15d, 1m, 3m, 6m, 1y
    """
    today = timezone.localdate()
    
    if period == "today":
        return today, today
    elif period == "7d":
        return today - timedelta(days=7), today
    elif period == "15d":
        return today - timedelta(days=15), today
    elif period == "1m":
        return today - timedelta(days=30), today
    elif period == "3m":
        return today - timedelta(days=90), today
    elif period == "6m":
        return today - timedelta(days=180), today
    elif period == "1y":
        return today - timedelta(days=365), today
    else:
        # Default: 7 days
        return today - timedelta(days=7), today


class DashboardService:
    """Service pour les agrégations du dashboard admin."""
    
    def __init__(self, borlette: Borlette):
        self.borlette = borlette
    
    # ═══════════════════════════════════════════════════════════════════════════
    # KPI CARDS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_kpi_summary(self, period: str = "7d") -> dict[str, Any]:
        """
        Retourne les KPI principaux pour la période.
        """
        start_date, end_date = get_period_dates(period)
        start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        # Tickets actifs (VALIDE ou PAYE, pas ANNULE ni PREVIEW)
        tickets = Ticket.objects.filter(
            borlette=self.borlette,
            statut__in=[TicketStatus.VALIDE, TicketStatus.PAYE],
            created_at__gte=start_dt,
            created_at__lte=end_dt
        )
        
        ticket_stats = tickets.aggregate(
            count=Count("id"),
            total_mise=Sum("total_mise"),
            total_gain_du=Sum("total_gain_du"),
            total_gain_paye=Sum("total_gain_paye")
        )
        
        # Commissions gagnées
        commissions = AgentLedgerEntry.objects.filter(
            borlette=self.borlette,
            entry_type=LedgerEntryType.COMMISSION_EARNED,
            created_at__gte=start_dt,
            created_at__lte=end_dt
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Dépenses
        expenses = Expense.objects.filter(
            borlette=self.borlette,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Calculs
        total_mise = ticket_stats["total_mise"] or Decimal("0")
        total_gain_du = ticket_stats["total_gain_du"] or Decimal("0")
        total_gain_paye = ticket_stats["total_gain_paye"] or Decimal("0")
        
        # Bénéfice net = mises - gains_dus - commissions - dépenses
        benefice_net = total_mise - total_gain_du - commissions - expenses
        
        # Cashbox totale agents
        cashbox_total = self._get_cashbox_total()
        
        # Solde commissions agents
        commission_balance_total = self._get_commission_balance_total()
        
        return {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "tickets_vendus": ticket_stats["count"] or 0,
            "total_mises": float(total_mise),
            "gains_dus": float(total_gain_du),
            "gains_payes": float(total_gain_paye),
            "commissions": float(commissions),
            "depenses": float(expenses),
            "benefice_net": float(benefice_net),
            "cashbox_terrain": float(cashbox_total),
            "commission_balance": float(commission_balance_total),
        }
    
    def _get_cashbox_total(self) -> Decimal:
        """Somme des soldes cashbox de tous les agents."""
        result = AgentCashboxEntry.objects.filter(
            borlette=self.borlette
        ).aggregate(total=Sum("amount"))
        return result["total"] or Decimal("0")
    
    def _get_commission_balance_total(self) -> Decimal:
        """Somme des soldes commission de tous les agents."""
        agents = Agent.objects.filter(borlette=self.borlette)
        total = Decimal("0")
        for agent in agents:
            balance = AgentLedgerEntry.get_agent_balance(agent)
            total += balance["balance"]
        return total
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AGENTS EN LIGNE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_agents_online(self, limit: int = 10) -> dict[str, Any]:
        """
        Retourne les agents en ligne (heartbeat < 2 min).
        """
        cutoff = timezone.now() - timedelta(minutes=2)
        
        agents_online = Agent.objects.filter(
            borlette=self.borlette,
            last_seen_at__gte=cutoff
        ).order_by("-last_seen_at")[:limit]
        
        total_online = Agent.objects.filter(
            borlette=self.borlette,
            last_seen_at__gte=cutoff
        ).count()
        
        total_agents = Agent.objects.filter(borlette=self.borlette).count()

        eligible_setting = int(getattr(self.borlette, "agents_eligible_share", 0) or 0)
        eligible_agents = min(eligible_setting, total_agents)
        non_eligible_agents = max(0, total_agents - eligible_agents)
        
        return {
            "total_online": total_online,
            "total_agents": total_agents,
            "eligible_agents": eligible_agents,
            "non_eligible_agents": non_eligible_agents,
            "eligible_setting": eligible_setting,
            "agents": [
                {
                    "id": a.id,
                    "nom": a.nom,
                    "zone": a.zone,
                    "last_seen": a.last_seen_at.isoformat() if a.last_seen_at else None,
                }
                for a in agents_online
            ]
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TIRAGES EN COURS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_tirages_status(self) -> dict[str, Any]:
        """
        Retourne les tirages ouverts et ceux en attente de résultats.
        Calcul de l'exposition et du volume de tickets par tirage.
        """
        from accounts.models import Resultat
        
        tirages = Tirage.objects.filter(borlette=self.borlette)
        
        tirages_ouverts = []
        tirages_attente_resultats = []
        
        for tirage in tirages:
            etat = tirage.etat_ouverture
            
            # Calculer stats de la session en cours
            stats = Ticket.objects.filter(
                borlette=self.borlette,
                tirage=tirage,
                tirage_session_key=tirage.session_key,
                statut__in=[TicketStatus.VALIDE, TicketStatus.PAYE]
            ).aggregate(
                total_mise=Sum("total_mise"),
                ticket_count=Count("id")
            )
            
            expo = float(stats["total_mise"] or 0)
            count = stats["ticket_count"] or 0
            
            if etat == "OUVERT":
                tirages_ouverts.append({
                    "id": tirage.id,
                    "nom": tirage.nom,
                    "heure_fermeture": tirage.heure_fermeture.strftime("%H:%M") if tirage.heure_fermeture else None,
                    "session_key": str(tirage.session_key),
                    "exposition": expo,
                    "tickets": count,
                })
            elif etat == "FERME":
                # Vérifier si résultats existent pour cette session
                has_result = Resultat.objects.filter(
                    tirage=tirage,
                    session_key=tirage.session_key
                ).exists()
                
                if not has_result:
                    tirages_attente_resultats.append({
                        "id": tirage.id,
                        "nom": tirage.nom,
                        "session_key": str(tirage.session_key),
                        "exposition": expo,
                        "tickets": count,
                    })
        
        return {
            "tirages_ouverts": tirages_ouverts,
            "tirages_attente_resultats": tirages_attente_resultats,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GRAPHIQUES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_charts_data(self, period: str = "7d") -> dict[str, Any]:
        """
        Retourne les données pour les graphiques.
        """
        start_date, end_date = get_period_dates(period)
        start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        # Tickets par jour
        tickets_by_day = Ticket.objects.filter(
            borlette=self.borlette,
            statut__in=[TicketStatus.VALIDE, TicketStatus.PAYE],
            created_at__gte=start_dt,
            created_at__lte=end_dt
        ).annotate(
            day=TruncDate("created_at")
        ).values("day").annotate(
            count=Count("id"),
            mises=Sum("total_mise"),
            gains_dus=Sum("total_gain_du"),
            gains_payes=Sum("total_gain_paye")
        ).order_by("day")
        
        # Commissions par jour
        commissions_by_day = AgentLedgerEntry.objects.filter(
            borlette=self.borlette,
            entry_type=LedgerEntryType.COMMISSION_EARNED,
            created_at__gte=start_dt,
            created_at__lte=end_dt
        ).annotate(
            day=TruncDate("created_at")
        ).values("day").annotate(
            total=Sum("amount")
        ).order_by("day")
        
        # Dépenses par jour
        expenses_by_day = Expense.objects.filter(
            borlette=self.borlette,
            date__gte=start_date,
            date__lte=end_date
        ).values("date").annotate(
            total=Sum("amount")
        ).order_by("date")
        
        # Construire les séries
        days = []
        tickets_data = []
        benefice_data = []
        gains_payes_data = []
        
        # Map pour lookup rapide
        tickets_map = {str(t["day"]): t for t in tickets_by_day}
        commissions_map = {str(c["day"]): float(c["total"]) for c in commissions_by_day}
        expenses_map = {str(e["date"]): float(e["total"]) for e in expenses_by_day}
        
        current = start_date
        while current <= end_date:
            day_str = current.isoformat()
            days.append(day_str)
            
            t = tickets_map.get(day_str, {})
            count = t.get("count", 0)
            mises = float(t.get("mises") or 0)
            gains_dus = float(t.get("gains_dus") or 0)
            gains_payes = float(t.get("gains_payes") or 0)
            
            commissions = commissions_map.get(day_str, 0)
            expenses = expenses_map.get(day_str, 0)
            
            benefice = mises - gains_dus - commissions - expenses
            
            tickets_data.append(count)
            benefice_data.append(round(benefice, 2))
            gains_payes_data.append(round(gains_payes, 2))
            
            current += timedelta(days=1)
        
        return {
            "labels": days,
            "tickets_vendus": tickets_data,
            "benefice_net": benefice_data,
            "gains_payes": gains_payes_data,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TABLES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_tables_data(self, period: str = "7d") -> dict[str, Any]:
        """
        Retourne les données pour les tables compactes.
        """
        start_date, end_date = get_period_dates(period)
        start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        # Top 5 tirages par mise
        top_tirages = Ticket.objects.filter(
            borlette=self.borlette,
            statut__in=[TicketStatus.VALIDE, TicketStatus.PAYE],
            created_at__gte=start_dt,
            created_at__lte=end_dt,
            tirage__isnull=False
        ).values(
            "tirage__id", "tirage__nom"
        ).annotate(
            total_mise=Sum("total_mise"),
            count=Count("id")
        ).order_by("-total_mise")[:5]
        
        # Top 5 agents par mises
        top_agents = Ticket.objects.filter(
            borlette=self.borlette,
            statut__in=[TicketStatus.VALIDE, TicketStatus.PAYE],
            created_at__gte=start_dt,
            created_at__lte=end_dt
        ).values(
            "agent__id", "agent__nom", "agent__zone"
        ).annotate(
            total_mise=Sum("total_mise"),
            count=Count("id")
        ).order_by("-total_mise")[:5]
        
        # Derniers 10 payouts
        recent_payouts = TicketPayout.objects.filter(
            borlette=self.borlette
        ).select_related("ticket", "agent").order_by("-created_at")[:10]
        
        # Dernières 10 dépenses
        recent_expenses = Expense.objects.filter(
            borlette=self.borlette
        ).select_related("category").order_by("-date")[:10]
        
        return {
            "top_tirages": [
                {
                    "id": t["tirage__id"],
                    "nom": t["tirage__nom"],
                    "total_mise": float(t["total_mise"]),
                    "tickets": t["count"],
                }
                for t in top_tirages
            ],
            "top_agents": [
                {
                    "id": a["agent__id"],
                    "nom": a["agent__nom"],
                    "zone": a["agent__zone"],
                    "total_mise": float(a["total_mise"]),
                    "tickets": a["count"],
                }
                for a in top_agents
            ],
            "recent_payouts": [
                {
                    "ticket_no": p.ticket.numero_ticket,
                    "agent": p.agent.nom,
                    "amount": float(p.amount),
                    "date": p.created_at.isoformat(),
                }
                for p in recent_payouts
            ],
            "recent_expenses": [
                {
                    "description": e.description[:50],
                    "category": e.category.name if e.category else "—",
                    "amount": float(e.amount),
                    "date": e.date.isoformat(),
                }
                for e in recent_expenses
            ],
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RECOMMANDATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_recommendations(self, period: str = "7d") -> list[dict[str, Any]]:
        """
        Génère des recommandations basées sur les signaux.
        """
        recommendations = []
        kpi = self.get_kpi_summary(period)
        tirages = self.get_tirages_status()
        
        # 1. Risque élevé si gains_dus / mises > 50%
        if kpi["total_mises"] > 0:
            ratio = kpi["gains_dus"] / kpi["total_mises"]
            if ratio > 0.5:
                recommendations.append({
                    "type": "warning",
                    "title": "Risque élevé",
                    "message": f"Les gains dus représentent {ratio*100:.0f}% des mises. Surveillez les limites.",
                    "priority": "high",
                })
        
        # 2. Résultats manquants
        if len(tirages["tirages_attente_resultats"]) > 0:
            noms = ", ".join([t["nom"] for t in tirages["tirages_attente_resultats"][:3]])
            recommendations.append({
                "type": "info",
                "title": "Résultats manquants",
                "message": f"{len(tirages['tirages_attente_resultats'])} tirage(s) en attente: {noms}",
                "priority": "medium",
            })
        
        # 3. Cashbox négatif
        if kpi["cashbox_terrain"] < 0:
            recommendations.append({
                "type": "alert",
                "title": "Contrôle caisse",
                "message": f"Solde caisse terrain négatif: {kpi['cashbox_terrain']:,.0f} HTG",
                "priority": "high",
            })
        
        # 4. Gains payés élevés
        if kpi["gains_payes"] > kpi["total_mises"] * 0.3:
            recommendations.append({
                "type": "info",
                "title": "Paiements élevés",
                "message": f"Les gains payés ({kpi['gains_payes']:,.0f} HTG) dépassent 30% des mises.",
                "priority": "medium",
            })
        
        # 5. Agents avec beaucoup de voids
        start_date, end_date = get_period_dates(period)
        start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        void_stats = Ticket.objects.filter(
            borlette=self.borlette,
            statut=TicketStatus.ANNULE,
            created_at__gte=start_dt,
            created_at__lte=end_dt
        ).values("agent__nom").annotate(
            void_count=Count("id")
        ).filter(void_count__gte=5).order_by("-void_count")[:3]
        
        for vs in void_stats:
            recommendations.append({
                "type": "warning",
                "title": "Surveillance agent",
                "message": f"{vs['agent__nom']} a annulé {vs['void_count']} tickets.",
                "priority": "medium",
            })
        
        # 6. Performance positive
        if kpi["benefice_net"] > 0 and len(recommendations) == 0:
            recommendations.append({
                "type": "success",
                "title": "Bonne performance",
                "message": f"Bénéfice net de {kpi['benefice_net']:,.0f} HTG sur la période.",
                "priority": "low",
            })
        
        return recommendations[:5]  # Max 5 recommandations
