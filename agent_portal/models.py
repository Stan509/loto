from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models
from django.conf import settings

from accounts.models import Agent, Borlette, Tirage


class LedgerEntryType(models.TextChoices):
    """Types d'entrées dans le ledger agent."""
    COMMISSION_EARNED = "COMMISSION_EARNED", "Commission gagnée"
    COMMISSION_PAYOUT = "COMMISSION_PAYOUT", "Paiement commission"
    EXPENSE = "EXPENSE", "Dépense"
    ADJUSTMENT = "ADJUSTMENT", "Ajustement"


class AgentLedgerEntry(models.Model):
    """
    Entrée dans le ledger (livre de comptes) d'un agent.
    Source of truth pour le calcul du solde commission.
    
    Conventions:
    - COMMISSION_EARNED: amount positif (crédit)
    - COMMISSION_PAYOUT: amount négatif (débit - paiement à l'agent)
    - ADJUSTMENT: amount positif ou négatif selon correction
    - EXPENSE: stocké séparément, n'affecte PAS le solde commission
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="ledger_entries")
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="agent_ledger_entries")
    
    entry_type = models.CharField(max_length=20, choices=LedgerEntryType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="agent_ledger_entries_created"
    )
    
    # Lien optionnel vers ticket (pour COMMISSION_EARNED)
    related_ticket = models.ForeignKey(
        "Ticket",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ledger_entries"
    )
    
    # Clé période pour agrégations rapides (YYYY-MM-DD)
    period_key = models.CharField(max_length=10, blank=True, default="", db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["agent", "created_at"], name="idx_ledger_agent_dt"),
            models.Index(fields=["agent", "entry_type"], name="idx_ledger_agent_type"),
            models.Index(fields=["borlette", "created_at"], name="idx_ledger_borlette_dt"),
            models.Index(fields=["borlette", "agent", "created_at"], name="idx_ledger_bor_agent_dt"),
            models.Index(fields=["borlette", "entry_type", "created_at"], name="idx_ledger_bor_type_dt"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["related_ticket", "entry_type"],
                name="uniq_commission_per_ticket",
                condition=models.Q(entry_type="COMMISSION_EARNED"),
            ),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"{self.agent.nom} | {self.entry_type} | {self.amount}"
    
    def save(self, *args, **kwargs):
        # Auto-fill period_key si vide
        if not self.period_key and self.created_at:
            self.period_key = self.created_at.strftime("%Y-%m-%d")
        super().save(*args, **kwargs)
    
    @classmethod
    def get_agent_balance(cls, agent: Agent) -> dict:
        """
        Calcule le solde commission d'un agent.
        
        Solde = sum(COMMISSION_EARNED) + sum(ADJUSTMENT) + sum(COMMISSION_PAYOUT)
        Note: PAYOUT est négatif, donc on additionne tout.
        EXPENSE n'est PAS inclus dans le solde commission.
        
        Returns dict avec:
            - commission_earned: Total commissions gagnées
            - commission_payout: Total payé (valeur absolue)
            - adjustments: Total ajustements
            - balance: Solde actuel
            - expenses: Total dépenses (séparé)
        """
        from django.db.models import Sum, Q
        
        entries = cls.objects.filter(agent=agent)
        
        # Commissions gagnées (positif)
        earned = entries.filter(
            entry_type=LedgerEntryType.COMMISSION_EARNED
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Paiements (négatif dans la DB)
        payouts_sum = entries.filter(
            entry_type=LedgerEntryType.COMMISSION_PAYOUT
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Ajustements (peuvent être positifs ou négatifs)
        adjustments = entries.filter(
            entry_type=LedgerEntryType.ADJUSTMENT
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Dépenses (séparées, ne comptent pas dans solde commission)
        expenses = entries.filter(
            entry_type=LedgerEntryType.EXPENSE
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Solde = earned + adjustments + payouts (payouts sont négatifs)
        balance = earned + adjustments + payouts_sum
        
        return {
            "commission_earned": earned,
            "commission_payout": abs(payouts_sum),  # Valeur absolue pour affichage
            "adjustments": adjustments,
            "balance": balance,
            "expenses": abs(expenses),
        }


class TicketStatus(models.TextChoices):
    PREVIEW = "PREVIEW", "Preview"
    VALIDE = "VALIDE", "Validé"
    PAYE = "PAYE", "Payé"
    ANNULE = "ANNULE", "Annulé"


class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="tickets")
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="tickets")
    tirage = models.ForeignKey(Tirage, on_delete=models.CASCADE, related_name="tickets", null=True, blank=True)
    
    # Copie de la session_key du tirage au moment de la vente (pour isolation par session)
    tirage_session_key = models.UUIDField(null=True, blank=True, db_index=True)
    
    # Pour relier les tickets créés ensemble via multi-tirage
    group_id = models.UUIDField(null=True, blank=True, db_index=True)

    numero_ticket = models.CharField(max_length=40, db_index=True)

    total_mise = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gain = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Gains dus (recalculés quand résultats saisis)
    total_gain_du = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gain_paye = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_winner = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)  # True si total_gain_paye >= total_gain_du et gain > 0
    computed_at = models.DateTimeField(null=True, blank=True)

    statut = models.CharField(max_length=16, choices=TicketStatus.choices, default=TicketStatus.PREVIEW)

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["borlette", "agent", "created_at"], name="idx_ticket_agent_dt"),
            models.Index(fields=["borlette", "statut"], name="idx_ticket_borlette_statut"),
            models.Index(fields=["tirage", "tirage_session_key"], name="idx_ticket_tirage_sess"),
            models.Index(fields=["tirage", "tirage_session_key", "created_at"], name="idx_ticket_sess_dt"),
        ]

    def __str__(self) -> str:
        return self.numero_ticket

    def recompute_totals(self) -> None:
        agg = self.lignes.aggregate(
            total_mise=models.Sum("mise"),
            total_gain=models.Sum("potentiel_gain"),
        )
        self.total_mise = agg.get("total_mise") or Decimal("0")


class TicketLine(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="lignes")

    jeu = models.CharField(max_length=16)
    valeur = models.CharField(max_length=12)
    mise = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    potentiel_gain = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gratuit = models.BooleanField(default=False)
    option = models.PositiveIntegerField(default=1, help_text="Option LOTO (1, 2, 3)")
    
    # Résultats du calcul (remplis par ResultCalculationService)
    gain_du = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_winner = models.BooleanField(default=False)
    win_context = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["ticket", "jeu"], name="idx_tline_ticket_jeu"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket.numero_ticket} · {self.jeu}:{self.valeur}"


class TicketPayout(models.Model):
    """
    Paiement d'un ticket gagnant.
    Anti-fraude: empêche double paiement, audit complet.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="payouts")
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="ticket_payouts")
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="ticket_payouts")
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ticket_payouts_created"
    )
    note = models.TextField(blank=True, default="")
    
    class Meta:
        indexes = [
            models.Index(fields=["agent", "created_at"], name="idx_tpayout_agent_dt"),
            models.Index(fields=["borlette", "created_at"], name="idx_tpayout_bor_dt"),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"Payout {self.ticket.numero_ticket} | {self.amount} G"


class CashboxEntryType(models.TextChoices):
    """Types d'entrées dans la caisse terrain agent."""
    SALE_CASH_IN = "SALE_CASH_IN", "Vente (encaissement)"
    WIN_PAYOUT_CASH_OUT = "WIN_PAYOUT_CASH_OUT", "Paiement gain (décaissement)"
    WITHDRAWAL = "WITHDRAWAL", "Retrait caisse"
    REPLENISH = "REPLENISH", "Réapprovisionnement caisse"
    ADJUSTMENT = "ADJUSTMENT", "Ajustment"


class AgentCashboxEntry(models.Model):
    """
    Entrée dans la caisse terrain d'un agent.
    DISTINCT de AgentLedgerEntry (commission).
    
    Caisse terrain = argent physique:
    - SALE_CASH_IN: +mise (agent encaisse)
    - WIN_PAYOUT_CASH_OUT: -gain payé (agent décaisse)
    - ADJUSTMENT: correction manuelle
    
    Solde caisse = somme de tous les amounts
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="cashbox_entries")
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="agent_cashbox_entries")
    
    entry_type = models.CharField(max_length=25, choices=CashboxEntryType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # + entrée, - sortie
    description = models.TextField(blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Liens optionnels pour audit
    related_ticket = models.ForeignKey(
        Ticket,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cashbox_entries"
    )
    related_payout = models.ForeignKey(
        TicketPayout,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cashbox_entries"
    )
    
    period_key = models.CharField(max_length=10, blank=True, default="", db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["agent", "created_at"], name="idx_cashbox_agent_dt"),
            models.Index(fields=["borlette", "created_at"], name="idx_cashbox_bor_dt"),
            models.Index(fields=["borlette", "agent", "entry_type"], name="idx_cashbox_bor_ag_type"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["related_ticket", "entry_type"],
                name="uniq_cashbox_sale_per_ticket",
                condition=models.Q(entry_type="SALE_CASH_IN"),
            ),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"{self.agent.nom} | {self.entry_type} | {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.period_key and self.created_at:
            self.period_key = self.created_at.strftime("%Y-%m-%d")
        super().save(*args, **kwargs)
    
    @classmethod
    def get_agent_cashbox_balance(cls, agent: Agent) -> dict:
        """
        Calcule le solde caisse terrain d'un agent.

        Solde caisse = Mises encaissées - Gains payés aux joueurs - Retraits + Réapprovisionnements ± Ajustements

        Conventions d'amount :
          SALE_CASH_IN          → positif  (argent reçu des joueurs)
          WIN_PAYOUT_CASH_OUT   → négatif  (argent versé aux gagnants)
          WITHDRAWAL            → négatif  (retrait admin de la caisse)
          REPLENISH             → positif  (réapprovisionnement admin)
          ADJUSTMENT            → positif ou négatif selon correction
        """
        from django.db.models import Sum

        entries = cls.objects.filter(agent=agent)

        sales = entries.filter(
            entry_type=CashboxEntryType.SALE_CASH_IN
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        payouts = entries.filter(
            entry_type=CashboxEntryType.WIN_PAYOUT_CASH_OUT
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        withdrawals = entries.filter(
            entry_type=CashboxEntryType.WITHDRAWAL
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        replenishments = entries.filter(
            entry_type=CashboxEntryType.REPLENISH
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        adjustments = entries.filter(
            entry_type=CashboxEntryType.ADJUSTMENT
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        balance = sales + payouts + withdrawals + replenishments + adjustments

        return {
            "sales_in": sales,
            "payouts_out": abs(payouts),
            "withdrawals": abs(withdrawals),
            "replenishments": replenishments,
            "adjustments": adjustments,
            "balance": balance,
        }
