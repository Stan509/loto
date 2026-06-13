"""
TirageResultsStatusService - Calcul du statut des résultats par tirage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from django.utils import timezone

from accounts.models import Borlette, Tirage, Resultat


@dataclass
class TirageResultStatus:
    """Statut des résultats d'un tirage."""
    tirage_id: int
    tirage_nom: str
    session_key: str
    is_open: bool
    has_results: bool
    closed_since_hours: float | None
    is_overdue: bool
    last_closed_at: datetime | None
    heure_fermeture: str
    

class TirageResultsStatusService:
    """Service pour calculer le statut des résultats des tirages."""
    
    def __init__(self, borlette: Borlette):
        self.borlette = borlette
    
    def get_all_statuses(self) -> List[TirageResultStatus]:
        """Retourne le statut des résultats pour tous les tirages actifs."""
        from accounts.models import TirageStatus
        
        tirages = Tirage.objects.filter(
            borlette=self.borlette,
            statut=TirageStatus.ACTIF
        ).order_by("heure_fermeture")
        
        return [self._get_status(t) for t in tirages]
    
    def get_pending_results(self) -> List[TirageResultStatus]:
        """Retourne uniquement les tirages fermés sans résultats."""
        all_statuses = self.get_all_statuses()
        return [s for s in all_statuses if not s.is_open and not s.has_results]
    
    def get_overdue_results(self) -> List[TirageResultStatus]:
        """Retourne les tirages avec résultats en retard (>24h)."""
        all_statuses = self.get_all_statuses()
        return [s for s in all_statuses if s.is_overdue]
    
    def _get_status(self, tirage: Tirage) -> TirageResultStatus:
        """Calcule le statut pour un tirage donné."""
        is_open = tirage.etat_ouverture == "OUVERT"
        session_key = str(tirage.session_key)
        
        # Vérifier si résultats existent pour cette session
        has_results = Resultat.objects.filter(
            tirage=tirage,
            session_key=tirage.session_key
        ).exists()
        
        # Calculer depuis combien de temps le tirage est fermé
        closed_since_hours = None
        last_closed_at = tirage.last_closed_at
        
        if not is_open:
            if last_closed_at:
                delta = timezone.now() - last_closed_at
                closed_since_hours = delta.total_seconds() / 3600
            elif tirage.heure_fermeture:
                # Fallback: utiliser l'heure de fermeture d'aujourd'hui
                now = timezone.localtime(timezone.now())
                today_close = timezone.make_aware(
                    datetime.combine(now.date(), tirage.heure_fermeture)
                )
                if now > today_close:
                    delta = now - today_close
                    closed_since_hours = delta.total_seconds() / 3600
        
        # Overdue: fermé + pas de résultats + > 24h
        is_overdue = (
            not is_open 
            and not has_results 
            and closed_since_hours is not None 
            and closed_since_hours >= 24
        )
        
        return TirageResultStatus(
            tirage_id=tirage.id,
            tirage_nom=tirage.nom,
            session_key=session_key[:8],
            is_open=is_open,
            has_results=has_results,
            closed_since_hours=round(closed_since_hours, 1) if closed_since_hours else None,
            is_overdue=is_overdue,
            last_closed_at=last_closed_at,
            heure_fermeture=tirage.heure_fermeture.strftime("%H:%M") if tirage.heure_fermeture else "--:--",
        )
    
    def to_dict(self, status: TirageResultStatus) -> dict:
        """Convertit un statut en dictionnaire pour l'API."""
        return {
            "tirage_id": status.tirage_id,
            "tirage_nom": status.tirage_nom,
            "session_key": status.session_key,
            "is_open": status.is_open,
            "has_results": status.has_results,
            "closed_since_hours": status.closed_since_hours,
            "is_overdue": status.is_overdue,
            "last_closed_at": status.last_closed_at.isoformat() if status.last_closed_at else None,
            "heure_fermeture": status.heure_fermeture,
        }
