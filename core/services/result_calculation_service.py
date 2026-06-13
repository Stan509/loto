"""
ResultCalculationService: Calcul instantané et idempotent des gains sur tickets.

Déclenché quand admin enregistre les résultats d'un tirage fermé.
Recalcule gain_du, is_winner, win_context sur chaque TicketLine de la session.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

if TYPE_CHECKING:
    from accounts.models import Resultat, Tirage


class ResultCalculationService:
    """Service de calcul des gains sur tickets après saisie des résultats."""

    @staticmethod
    @transaction.atomic
    def calculate_gains(*, tirage: Tirage, resultat: Resultat) -> dict:
        """
        Calcule les gains pour tous les tickets de la session courante du tirage.
        
        Args:
            tirage: Le tirage concerné
            resultat: Le résultat saisi (doit avoir session_key == tirage.session_key)
        
        Returns:
            dict avec stats: tickets_count, winners_count, total_gain_du
        """
        from accounts.models import AdminPaymentSettings
        from agent_portal.models import Ticket, TicketLine, TicketStatus

        # Vérifications
        if tirage.etat_ouverture == "OUVERT":
            raise ValueError("Impossible de calculer les gains: tirage encore ouvert")
        
        if resultat.session_key != tirage.session_key:
            raise ValueError("Session key du résultat ne correspond pas au tirage")

        # Récupérer les coefficients de paiement
        try:
            settings = AdminPaymentSettings.objects.get(borlette=tirage.borlette)
        except AdminPaymentSettings.DoesNotExist:
            settings = None

        coeff_1er = Decimal(str(getattr(settings, "boule_1er_lot_coeff", 0) or 0))
        coeff_2eme = Decimal(str(getattr(settings, "boule_2eme_lot_coeff", 0) or 0))
        coeff_3eme = Decimal(str(getattr(settings, "boule_3eme_lot_coeff", 0) or 0))
        coeff_loto3 = Decimal(str(getattr(settings, "loto3_coeff", 0) or 0))
        coeff_loto4 = Decimal(str(getattr(settings, "loto4_coeff", 0) or 0))
        coeff_loto5 = Decimal(str(getattr(settings, "loto5_coeff", 0) or 0))
        coeff_mariage = Decimal(str(getattr(settings, "mariage_normal_coeff", 0) or 0))

        # Extraire les numéros gagnants du résultat
        lot1 = resultat.lot1
        lot2 = resultat.lot2
        lot3 = resultat.lot3
        lots_set = {lot1, lot2, lot3}
        
        loto3_val = resultat.loto3
        loto4_vals = {resultat.loto4_opt1, resultat.loto4_opt2, resultat.loto4_opt3}
        loto5_vals = {resultat.loto5_opt1, resultat.loto5_opt2, resultat.loto5_opt3}

        # Sélectionner tous les tickets de cette session
        tickets = Ticket.objects.filter(
            tirage=tirage,
            tirage_session_key=tirage.session_key,
            statut=TicketStatus.VALIDE,
        ).prefetch_related("lignes")

        stats = {
            "tickets_count": 0,
            "winners_count": 0,
            "total_gain_du": Decimal("0"),
        }

        now = timezone.now()

        for ticket in tickets:
            stats["tickets_count"] += 1
            ticket_gain_du = Decimal("0")
            ticket_is_winner = False

            for line in ticket.lignes.all():
                gain_du, is_winner, win_context = ResultCalculationService._calculate_line(
                    line=line,
                    lot1=lot1,
                    lot2=lot2,
                    lot3=lot3,
                    lots_set=lots_set,
                    loto3_val=loto3_val,
                    loto4_vals=loto4_vals,
                    loto5_vals=loto5_vals,
                    coeff_1er=coeff_1er,
                    coeff_2eme=coeff_2eme,
                    coeff_3eme=coeff_3eme,
                    coeff_loto3=coeff_loto3,
                    coeff_loto4=coeff_loto4,
                    coeff_loto5=coeff_loto5,
                    coeff_mariage=coeff_mariage,
                )

                # Mise à jour de la ligne (idempotent)
                line.gain_du = gain_du
                line.is_winner = is_winner
                line.win_context = win_context
                line.save(update_fields=["gain_du", "is_winner", "win_context"])

                ticket_gain_du += gain_du
                if is_winner:
                    ticket_is_winner = True

            # Mise à jour du ticket
            ticket.total_gain_du = ticket_gain_du
            ticket.is_winner = ticket_is_winner
            ticket.computed_at = now
            ticket.save(update_fields=["total_gain_du", "is_winner", "computed_at"])

            if ticket_is_winner:
                stats["winners_count"] += 1
            stats["total_gain_du"] += ticket_gain_du

        # Marquer le résultat comme calculé
        resultat.computed_at = now
        resultat.save(update_fields=["computed_at"])

        return stats

    @staticmethod
    def _calculate_line(
        *,
        line,
        lot1: str,
        lot2: str,
        lot3: str,
        lots_set: set,
        loto3_val: str,
        loto4_vals: set,
        loto5_vals: set,
        coeff_1er: Decimal,
        coeff_2eme: Decimal,
        coeff_3eme: Decimal,
        coeff_loto3: Decimal,
        coeff_loto4: Decimal,
        coeff_loto5: Decimal,
        coeff_mariage: Decimal,
    ) -> tuple[Decimal, bool, str]:
        """
        Calcule le gain pour une ligne de ticket.
        
        Returns:
            (gain_du, is_winner, win_context)
        """
        jeu = (line.jeu or "").strip().lower()
        valeur = (line.valeur or "").strip()
        mise = line.mise or Decimal("0")

        if mise <= 0 and not line.gratuit:
            return Decimal("0"), False, ""

        # Pour les mariages gratuits, on utilise une mise fictive pour le calcul
        effective_mise = mise if mise > 0 else Decimal("1")

        if jeu == "boule":
            return ResultCalculationService._calc_boule(
                valeur=valeur,
                mise=effective_mise,
                lot1=lot1,
                lot2=lot2,
                lot3=lot3,
                coeff_1er=coeff_1er,
                coeff_2eme=coeff_2eme,
                coeff_3eme=coeff_3eme,
            )

        elif jeu == "mariage":
            return ResultCalculationService._calc_mariage(
                valeur=valeur,
                mise=effective_mise,
                lots_set=lots_set,
                coeff_mariage=coeff_mariage,
                is_gratuit=line.gratuit,
            )

        elif jeu == "loto3":
            return ResultCalculationService._calc_loto3(
                valeur=valeur,
                mise=effective_mise,
                loto3_val=loto3_val,
                coeff_loto3=coeff_loto3,
            )

        elif jeu == "loto4":
            return ResultCalculationService._calc_loto4(
                valeur=valeur,
                mise=effective_mise,
                loto4_vals=loto4_vals,
                coeff_loto4=coeff_loto4,
            )

        elif jeu == "loto5":
            return ResultCalculationService._calc_loto5(
                valeur=valeur,
                mise=effective_mise,
                loto5_vals=loto5_vals,
                coeff_loto5=coeff_loto5,
            )

        return Decimal("0"), False, ""

    @staticmethod
    def _calc_boule(
        *,
        valeur: str,
        mise: Decimal,
        lot1: str,
        lot2: str,
        lot3: str,
        coeff_1er: Decimal,
        coeff_2eme: Decimal,
        coeff_3eme: Decimal,
    ) -> tuple[Decimal, bool, str]:
        """Boule gagne si numéro == lot1/lot2/lot3."""
        if valeur == lot1:
            return mise * coeff_1er, True, "1er lot"
        if valeur == lot2:
            return mise * coeff_2eme, True, "2ème lot"
        if valeur == lot3:
            return mise * coeff_3eme, True, "3ème lot"
        return Decimal("0"), False, ""

    @staticmethod
    def _calc_mariage(
        *,
        valeur: str,
        mise: Decimal,
        lots_set: set,
        coeff_mariage: Decimal,
        is_gratuit: bool,
    ) -> tuple[Decimal, bool, str]:
        """Mariage gagne si les deux numéros sont dans les lots (ordre indifférent)."""
        # Format: "44x30" ou "44-30"
        parts = valeur.replace("-", "x").split("x")
        if len(parts) != 2:
            return Decimal("0"), False, ""
        
        n1, n2 = parts[0].strip(), parts[1].strip()
        if n1 in lots_set and n2 in lots_set:
            gain = mise * coeff_mariage if not is_gratuit else coeff_mariage
            return gain, True, "Mariage gagnant"
        return Decimal("0"), False, ""

    @staticmethod
    def _calc_loto3(
        *,
        valeur: str,
        mise: Decimal,
        loto3_val: str,
        coeff_loto3: Decimal,
    ) -> tuple[Decimal, bool, str]:
        """Loto3 gagne si valeur == loto3 du résultat."""
        if valeur == loto3_val:
            return mise * coeff_loto3, True, "Loto3"
        return Decimal("0"), False, ""

    @staticmethod
    def _calc_loto4(
        *,
        valeur: str,
        mise: Decimal,
        loto4_vals: set,
        coeff_loto4: Decimal,
    ) -> tuple[Decimal, bool, str]:
        """Loto4 gagne si valeur == une des 3 options loto4."""
        if valeur in loto4_vals:
            # Déterminer quelle option
            opt = "Loto4"
            return mise * coeff_loto4, True, opt
        return Decimal("0"), False, ""

    @staticmethod
    def _calc_loto5(
        *,
        valeur: str,
        mise: Decimal,
        loto5_vals: set,
        coeff_loto5: Decimal,
    ) -> tuple[Decimal, bool, str]:
        """Loto5 gagne si valeur == une des 3 options loto5."""
        if valeur in loto5_vals:
            return mise * coeff_loto5, True, "Loto5"
        return Decimal("0"), False, ""
