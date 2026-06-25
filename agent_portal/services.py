"""
Services métier pour agent_portal (Phase B).
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction


class TicketPayoutService:
    """
    Service de paiement des tickets gagnants.
    
    Anti-fraude:
    - Vérifie que le ticket est gagnant
    - Empêche double paiement
    - Crée audit trail (TicketPayout + AgentCashboxEntry)
    """
    
    @staticmethod
    def pay_ticket(ticket, agent, note: str = "") -> dict:
        """
        Paye un ticket gagnant (TOTAL uniquement, pas de paiement partiel).
        
        Args:
            ticket: Ticket à payer
            agent: Agent qui effectue le paiement
            note: Note optionnelle
        
        Returns:
            dict avec résultat du paiement
        """
        from agent_portal.models import (
            Ticket, TicketPayout, AgentCashboxEntry, CashboxEntryType
        )
        
        # Vérifications
        if not ticket.is_winner:
            return {"success": False, "error": "Ticket non gagnant"}
        
        if ticket.is_paid:
            return {"success": False, "error": "Ticket déjà entièrement payé"}
        
        remaining = ticket.total_gain_du - ticket.total_gain_paye
        
        if remaining <= 0:
            return {"success": False, "error": "Rien à payer"}
        
        # Paiement TOTAL uniquement (pas de partiel)
        pay_amount = remaining
        
        # Vérifier si l'agent a assez de fonds dans sa caisse
        if pay_amount > agent.solde_caisse_calculé:
            return {"success": False, "error": "Solde de caisse insuffisant pour payer ce gain"}
        
        # Vérifier ownership
        if ticket.agent != agent:
            return {"success": False, "error": "Ce ticket n'appartient pas à cet agent"}
        
        with transaction.atomic():
            # Créer TicketPayout
            payout = TicketPayout.objects.create(
                ticket=ticket,
                agent=agent,
                borlette=agent.borlette,
                amount=pay_amount,
                created_by=agent.user,
                note=note,
            )
            
            # Créer AgentCashboxEntry (décaissement)
            AgentCashboxEntry.objects.create(
                agent=agent,
                borlette=agent.borlette,
                entry_type=CashboxEntryType.WIN_PAYOUT_CASH_OUT,
                amount=-pay_amount,  # Négatif car sortie de caisse
                description=f"Paiement gain ticket {ticket.numero_ticket}",
                related_ticket=ticket,
                related_payout=payout,
            )
            
            # Mettre à jour ticket
            ticket.total_gain_paye += pay_amount
            ticket.is_paid = ticket.total_gain_paye >= ticket.total_gain_du
            ticket.save(update_fields=["total_gain_paye", "is_paid"])
            
            # Créer notification admin
            from admin_portal.models import AdminNotification
            AdminNotification.create_payout_notification(payout)
        
        return {
            "success": True,
            "payout_id": str(payout.id),
            "amount_paid": pay_amount,
            "remaining": ticket.total_gain_du - ticket.total_gain_paye,
            "is_fully_paid": ticket.is_paid,
        }


def create_cashbox_entry_for_sale(ticket) -> None:
    """
    Crée une entrée caisse pour une vente de ticket.
    Appelé après validation du ticket.
    Idempotent (vérifie si déjà existant).
    """
    from agent_portal.models import AgentCashboxEntry, CashboxEntryType
    
    # Vérifier si déjà existant
    exists = AgentCashboxEntry.objects.filter(
        related_ticket=ticket,
        entry_type=CashboxEntryType.SALE_CASH_IN
    ).exists()
    
    if exists:
        return
    
    AgentCashboxEntry.objects.create(
        agent=ticket.agent,
        borlette=ticket.borlette,
        entry_type=CashboxEntryType.SALE_CASH_IN,
        amount=ticket.total_mise,
        description=f"Vente ticket {ticket.numero_ticket}",
        related_ticket=ticket,
    )


def void_ticket_with_cashbox_reversal(ticket) -> dict:
    """
    Annule un ticket en le supprimant de la base de données.
    Supprime également toutes les entrées de caisse et de grand livre associées.
    """
    from agent_portal.models import TicketStatus
    
    if ticket.statut == TicketStatus.ANNULE:
        return {"success": False, "error": "Ticket déjà annulé"}
    
    if ticket.total_gain_paye > 0:
        return {"success": False, "error": "Impossible d'annuler: gains déjà payés"}
    
    with transaction.atomic():
        ticket_no = ticket.numero_ticket
        
        # Supprimer les entrées de caisse associées
        ticket.cashbox_entries.all().delete()
        
        # Supprimer les entrées de grand livre (ledger / commissions) associées
        ticket.ledger_entries.all().delete()
        
        # Supprimer le ticket (les lignes de ticket sont supprimées en cascade)
        ticket.delete()
        
    return {
        "success": True,
        "message": f"Ticket {ticket_no} supprimé avec succès",
        "cashbox_reversed": True,
    }

