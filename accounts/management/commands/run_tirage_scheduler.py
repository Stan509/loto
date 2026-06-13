"""
Management command pour automatiser le cycle des tirages.

Usage:
    python manage.py run_tirage_scheduler --once     # Mode one-shot (Task Scheduler)
    python manage.py run_tirage_scheduler            # Mode boucle (service)
    python manage.py run_tirage_scheduler --interval 30  # Intervalle personnalisé

Règles:
    - Fermeture: quand now >= heure_fermeture et tirage était OUVERT
    - Ouverture: quand now >= heure_ouverture et tirage était FERME
      OU quand résultats saisis et 30 minutes écoulées
    - session_key change UNIQUEMENT à l'ouverture (nouvelle session)
"""
import time
import uuid
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.audit import log_audit
from accounts.models import AuditAction, Resultat, Tirage, TirageStatus


class Command(BaseCommand):
    help = "Gère automatiquement le cycle ouverture/fermeture des tirages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Exécute une seule fois puis quitte (mode Task Scheduler)",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=30,
            help="Intervalle en secondes entre les vérifications (mode boucle)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Affiche plus de détails",
        )

    def handle(self, *args, **options):
        once = options["once"]
        interval = options["interval"]
        verbose = options["verbose"]

        self.stdout.write(self.style.SUCCESS(
            f"[TirageScheduler] Démarrage {'(mode one-shot)' if once else f'(intervalle {interval}s)'}"
        ))

        if once:
            self._run_cycle(verbose)
        else:
            try:
                while True:
                    self._run_cycle(verbose)
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n[TirageScheduler] Arrêt demandé"))

    def _run_cycle(self, verbose: bool):
        """Exécute un cycle de vérification pour tous les tirages."""
        now = timezone.now()
        tirages = Tirage.objects.filter(statut=TirageStatus.ACTIF)
        
        opened_count = 0
        closed_count = 0

        for tirage in tirages:
            result = self._process_tirage(tirage, now, verbose)
            if result == "opened":
                opened_count += 1
            elif result == "closed":
                closed_count += 1

        if verbose or opened_count > 0 or closed_count > 0:
            self.stdout.write(
                f"[{now.strftime('%H:%M:%S')}] "
                f"Tirages: {tirages.count()} | "
                f"Ouverts: {opened_count} | "
                f"Fermés: {closed_count}"
            )

    def _process_tirage(self, tirage: Tirage, now: datetime, verbose: bool) -> str:
        """
        Traite un tirage et détecte les transitions d'état.
        
        Returns:
            "opened" si le tirage vient d'ouvrir
            "closed" si le tirage vient de fermer
            "" si pas de changement
        """
        current_state = tirage.etat_ouverture  # "OUVERT" ou "FERME"
        cached_state = tirage.cached_state
        
        # Première exécution: initialiser le cache
        if not cached_state:
            tirage.cached_state = current_state
            tirage.save(update_fields=["cached_state"])
            if verbose:
                self.stdout.write(f"  [{tirage.nom}] État initial: {current_state}")
            return ""
        
        # Vérifier si on doit réouvrir après les résultats (30 minutes après)
        if current_state == "FERME" and cached_state == "FERME":
            should_reopen = self._should_reopen_after_results(tirage, now, verbose)
            if should_reopen:
                self._handle_opening(tirage, now, verbose)
                return "opened"
        
        # Pas de changement
        if cached_state == current_state:
            return ""
        
        # Transition détectée!
        if cached_state == "FERME" and current_state == "OUVERT":
            # OUVERTURE: rotate session_key
            self._handle_opening(tirage, now, verbose)
            return "opened"
        
        elif cached_state == "OUVERT" and current_state == "FERME":
            # FERMETURE
            self._handle_closing(tirage, now, verbose)
            return "closed"
        
        return ""

    def _should_reopen_after_results(self, tirage: Tirage, now: datetime, verbose: bool) -> bool:
        """
        Vérifie si le tirage doit être réouvert 30 minutes après la saisie des résultats.
        
        Returns:
            True si résultats saisis et 30 minutes écoulées
        """
        # Chercher les résultats pour la session actuelle
        try:
            resultat = Resultat.objects.filter(
                tirage=tirage,
                session_key=tirage.session_key
            ).first()
            
            if not resultat:
                return False  # Pas de résultats, pas de réouverture
            
            # Vérifier si 30 minutes se sont écoulées depuis la création du résultat
            time_since_result = now - resultat.created_at
            if time_since_result >= timedelta(minutes=30):
                if verbose:
                    self.stdout.write(
                        f"  [{tirage.nom}] Résultats saisis il y a {time_since_result.total_seconds() / 60:.0f}min → Réouverture"
                    )
                return True
            
            return False
            
        except Exception as e:
            if verbose:
                self.stdout.write(f"  [{tirage.nom}] Erreur vérification résultats: {e}")
            return False

    def _handle_opening(self, tirage: Tirage, now: datetime, verbose: bool):
        """Gère l'ouverture d'un tirage: rotate session_key."""
        old_session = str(tirage.session_key)[:8]
        
        # Nouvelle session
        tirage.session_key = uuid.uuid4()
        tirage.session_started_at = now
        tirage.last_opened_at = now
        tirage.cached_state = "OUVERT"
        
        tirage.save(update_fields=[
            "session_key", 
            "session_started_at", 
            "last_opened_at", 
            "cached_state"
        ])
        
        new_session = str(tirage.session_key)[:8]

        log_audit(
            action=AuditAction.RESULTS_RESET,
            entity_type="Tirage",
            entity_id=str(tirage.id),
            borlette=tirage.borlette,
            meta={
                "tirage_id": tirage.id,
                "tirage_nom": tirage.nom,
                "old_session_key": old_session,
                "new_session_key": new_session,
            },
        )
        
        self.stdout.write(self.style.SUCCESS(
            f"  ✓ [{tirage.nom}] OUVERT | session: {old_session}→{new_session}"
        ))

    def _handle_closing(self, tirage: Tirage, now: datetime, verbose: bool):
        """Gère la fermeture d'un tirage."""
        tirage.last_closed_at = now
        tirage.cached_state = "FERME"
        
        tirage.save(update_fields=["last_closed_at", "cached_state"])
        
        self.stdout.write(self.style.WARNING(
            f"  ✗ [{tirage.nom}] FERMÉ | session: {str(tirage.session_key)[:8]}"
        ))
