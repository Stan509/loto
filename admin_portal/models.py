import uuid
from django.db import models
from django.conf import settings

from accounts.models import Borlette


class NotificationType(models.TextChoices):
    """Types de notifications admin."""
    PAYOUT = "PAYOUT", "Paiement gain"
    COMMISSION_WITHDRAW = "COMMISSION_WITHDRAW", "Retrait commission"
    ALERT = "ALERT", "Alerte"
    INFO = "INFO", "Information"
    RESULT = "RESULT", "Résultat saisi"


class AdminNotification(models.Model):
    """
    Notifications pour l'admin dashboard.
    Utilisé pour alerter l'admin des événements importants en temps réel.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="admin_notifications")
    
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
    title = models.CharField(max_length=100)
    message = models.TextField()
    
    # Métadonnées optionnelles (JSON)
    meta = models.JSONField(default=dict, blank=True)
    
    # Statut lecture
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["borlette", "is_read", "-created_at"], name="idx_notif_bor_read_dt"),
            models.Index(fields=["borlette", "notification_type"], name="idx_notif_bor_type"),
        ]
    
    def __str__(self) -> str:
        return f"{self.notification_type}: {self.title}"
    
    @classmethod
    def create_payout_notification(cls, payout) -> "AdminNotification":
        """Crée une notification pour un paiement de gain."""
        from agent_portal.models import TicketPayout
        
        return cls.objects.create(
            borlette=payout.borlette,
            notification_type=NotificationType.PAYOUT,
            title=f"💰 Paiement: {payout.amount:,.0f} HTG",
            message=f"Agent {payout.agent.nom} a payé le ticket {payout.ticket.numero_ticket}",
            meta={
                "payout_id": str(payout.id),
                "ticket_id": str(payout.ticket.id),
                "ticket_no": payout.ticket.numero_ticket,
                "agent_id": payout.agent.id,
                "agent_nom": payout.agent.nom,
                "amount": float(payout.amount),
            }
        )
