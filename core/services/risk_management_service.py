from __future__ import annotations

from decimal import Decimal
from itertools import permutations

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import Tirage, TirageCombiStats, TirageCombiType, TirageNumeroStats


class RiskManagementService:
    @staticmethod
    def get_stats(*, tirage_id: int, jeu: str, borlette_id: int | None = None) -> dict:
        qs = Tirage.objects.filter(id=tirage_id).select_related("borlette")
        if borlette_id is not None:
            qs = qs.filter(borlette_id=borlette_id)

        tirage = qs.first()
        if tirage is None:
            raise ValidationError("Tirage introuvable")

        jeu = (jeu or "").strip().lower()
        if jeu not in ("boule", "mariage", "loto3", "loto4", "loto5"):
            raise ValidationError("Jeu invalide")

        if jeu == "boule":
            RiskManagementService.ensure_numero_stats_rows(tirage=tirage)
            rows = []
            for s in TirageNumeroStats.objects.filter(tirage=tirage).order_by("numero"):
                risk_level = "ok"
                if s.bloque_auto:
                    risk_level = "blocked_auto"
                elif s.bloque_admin:
                    risk_level = "blocked_admin"
                elif s.plafond_admin and s.plafond_admin > 0:
                    try:
                        ratio = (s.mises_total or 0) / s.plafond_admin
                    except Exception:
                        ratio = 0
                    if ratio >= Decimal("0.90"):
                        risk_level = "warning"

                rows.append(
                    {
                        "type": "boule",
                        "numero": s.numero,
                        "valeur": s.numero,
                        "mises_total": s.mises_total,
                        "plafond_admin": s.plafond_admin,
                        "bloque_auto": s.bloque_auto,
                        "bloque_admin": s.bloque_admin,
                        "risk_level": risk_level,
                    }
                )
            return {"tirage": tirage, "jeu": jeu, "rows": rows}

        rows = []
        for s in TirageCombiStats.objects.filter(tirage=tirage, jeu_type=jeu).order_by("valeur"):
            risk_level = "ok"
            if s.bloque_auto:
                risk_level = "blocked_auto"
            elif s.bloque_admin:
                risk_level = "blocked_admin"
            elif s.plafond_admin and s.plafond_admin > 0:
                try:
                    ratio = (s.mises_total or 0) / s.plafond_admin
                except Exception:
                    ratio = 0
                if ratio >= Decimal("0.90"):
                    risk_level = "warning"

            rows.append(
                {
                    "type": jeu,
                    "valeur": s.valeur,
                    "mises_total": s.mises_total,
                    "plafond_admin": s.plafond_admin,
                    "bloque_auto": s.bloque_auto,
                    "bloque_admin": s.bloque_admin,
                    "risk_level": risk_level,
                }
            )
        return {"tirage": tirage, "jeu": jeu, "rows": rows}

    @staticmethod
    def list_available_numbers(*, tirage: Tirage) -> list[str]:
        blocked = set(
            TirageNumeroStats.objects.filter(tirage=tirage)
            .filter(bloque_auto=True)
            .values_list("numero", flat=True)
        ) | set(
            TirageNumeroStats.objects.filter(tirage=tirage)
            .filter(bloque_admin=True)
            .values_list("numero", flat=True)
        )
        return [f"{i:02d}" for i in range(100) if f"{i:02d}" not in blocked]

    @staticmethod
    def list_available_combis(*, tirage: Tirage, jeu_type: str) -> list[str]:
        qs = TirageCombiStats.objects.filter(tirage=tirage, jeu_type=jeu_type).only(
            "valeur", "bloque_auto", "bloque_admin", "bloque_derived"
        )
        return [c.valeur for c in qs if not (c.bloque_auto or c.bloque_admin or c.bloque_derived)]

    @staticmethod
    def ensure_numero_stats_rows(*, tirage: Tirage) -> None:
        existing = set(TirageNumeroStats.objects.filter(tirage=tirage).values_list("numero", flat=True))
        to_create = []
        for i in range(100):
            n = f"{i:02d}"
            if n not in existing:
                to_create.append(TirageNumeroStats(tirage=tirage, numero=n))
        if to_create:
            TirageNumeroStats.objects.bulk_create(to_create, ignore_conflicts=True)

    @staticmethod
    @transaction.atomic
    def set_numero_admin_controls(
        *, tirage: Tirage, numero: str, plafond_admin: Decimal | None, bloque_admin: bool | None
    ) -> TirageNumeroStats:
        obj, _ = TirageNumeroStats.objects.select_for_update().get_or_create(tirage=tirage, numero=numero)
        if plafond_admin is not None:
            try:
                obj.plafond_admin = max(Decimal("0"), Decimal(str(plafond_admin)))
            except Exception:
                obj.plafond_admin = Decimal("0")
            obj.bloque_auto = bool(obj.plafond_admin and obj.mises_total > obj.plafond_admin)
        if bloque_admin is not None:
            obj.bloque_admin = bool(bloque_admin)
        obj.save(update_fields=["plafond_admin", "bloque_auto", "bloque_admin", "updated_at"])
        return obj

    @staticmethod
    @transaction.atomic
    def set_combi_admin_controls(
        *, tirage: Tirage, jeu_type: str, valeur: str, plafond_admin: Decimal | None, bloque_admin: bool | None
    ) -> TirageCombiStats:
        obj, _ = TirageCombiStats.objects.select_for_update().get_or_create(tirage=tirage, jeu_type=jeu_type, valeur=valeur)
        if plafond_admin is not None:
            try:
                obj.plafond_admin = max(Decimal("0"), Decimal(str(plafond_admin)))
            except Exception:
                obj.plafond_admin = Decimal("0")
            obj.bloque_auto = bool(obj.plafond_admin and obj.mises_total > obj.plafond_admin)
        if bloque_admin is not None:
            obj.bloque_admin = bool(bloque_admin)
        obj.save(update_fields=["plafond_admin", "bloque_auto", "bloque_admin", "updated_at"])
        return obj

    @staticmethod
    @transaction.atomic
    def apply_bet(*, tirage: Tirage, game: str, value: str, stake: Decimal) -> None:
        stake = Decimal(stake)
        if stake <= 0:
            raise ValidationError("Mise invalide")

        if game == "boule":
            obj, _ = TirageNumeroStats.objects.select_for_update().get_or_create(tirage=tirage, numero=value)
            if obj.bloque_admin or obj.bloque_auto:
                raise ValidationError("Numéro bloqué")

            new_total = obj.mises_total + stake
            if obj.plafond_admin and new_total > obj.plafond_admin:
                obj.bloque_auto = True
                obj.save(update_fields=["bloque_auto", "updated_at"])
                raise ValidationError("Plafond atteint")

            obj.mises_total = new_total
            obj.bloque_auto = bool(obj.plafond_admin and obj.mises_total > obj.plafond_admin)
            obj.save(update_fields=["mises_total", "bloque_auto", "updated_at"])
            return

        if game not in ("mariage", "loto3", "loto4", "loto5"):
            raise ValidationError("Jeu invalide")

        jeu_type = (
            TirageCombiType.MARIAGE
            if game == "mariage"
            else (TirageCombiType.LOTO3 if game == "loto3" else (TirageCombiType.LOTO4 if game == "loto4" else TirageCombiType.LOTO5))
        )

        obj, _ = TirageCombiStats.objects.select_for_update().get_or_create(
            tirage=tirage, jeu_type=jeu_type, valeur=value
        )
        if obj.bloque_admin or obj.bloque_auto or obj.bloque_derived:
            raise ValidationError("Jeu bloqué")

        new_total = obj.mises_total + stake
        if obj.plafond_admin and new_total > obj.plafond_admin:
            obj.bloque_auto = True
            obj.save(update_fields=["bloque_auto", "updated_at"])
            raise ValidationError("Plafond atteint")

        obj.mises_total = new_total
        obj.bloque_auto = bool(obj.plafond_admin and obj.mises_total > obj.plafond_admin)
        obj.save(update_fields=["mises_total", "bloque_auto", "updated_at"])

    @staticmethod
    @transaction.atomic
    def sync_mariage_derived(*, tirage: Tirage) -> int:
        """
        Synchronise les blocages dérivés pour les mariages.
        Quand des boules sont bloquées (bloque_admin=True), toutes les paires
        ordonnées (a,b) avec a≠b sont automatiquement bloquées en mariage.
        
        Retourne le nombre de combinaisons dérivées actives.
        """
        # 1. Récupérer les boules bloquées admin pour ce tirage
        blocked_numeros = set(
            TirageNumeroStats.objects.filter(tirage=tirage, bloque_admin=True)
            .values_list("numero", flat=True)
        )

        # 2. Générer toutes les paires ordonnées attendues (a×b avec a≠b)
        expected_pairs: set[str] = set()
        for a, b in permutations(blocked_numeros, 2):
            # Format: "44x30" (a×b)
            expected_pairs.add(f"{a}x{b}")

        # 3. Récupérer tous les mariages existants avec bloque_derived=True
        existing_derived = {
            obj.valeur: obj
            for obj in TirageCombiStats.objects.filter(
                tirage=tirage, jeu_type=TirageCombiType.MARIAGE, bloque_derived=True
            )
        }

        # 4. Ajouter/mettre à jour les dérivés attendus
        to_create = []
        for valeur in expected_pairs:
            if valeur in existing_derived:
                # Déjà marqué comme dérivé, rien à faire
                continue
            # Vérifier si existe déjà (peut avoir bloque_admin mais pas bloque_derived)
            obj = TirageCombiStats.objects.filter(
                tirage=tirage, jeu_type=TirageCombiType.MARIAGE, valeur=valeur
            ).first()
            if obj:
                obj.bloque_derived = True
                obj.save(update_fields=["bloque_derived", "updated_at"])
            else:
                to_create.append(
                    TirageCombiStats(
                        tirage=tirage,
                        jeu_type=TirageCombiType.MARIAGE,
                        valeur=valeur,
                        bloque_derived=True,
                    )
                )

        if to_create:
            TirageCombiStats.objects.bulk_create(to_create, ignore_conflicts=True)

        # 5. Retirer bloque_derived des paires qui ne sont plus attendues
        obsolete_valeurs = set(existing_derived.keys()) - expected_pairs
        for valeur in obsolete_valeurs:
            obj = existing_derived[valeur]
            obj.bloque_derived = False
            # Si ni admin ni auto ni derived, on peut supprimer si mises_total=0
            if not obj.bloque_admin and not obj.bloque_auto and obj.mises_total == 0:
                obj.delete()
            else:
                obj.save(update_fields=["bloque_derived", "updated_at"])

        return len(expected_pairs)

    @staticmethod
    def is_mariage_blocked(*, tirage: Tirage, valeur: str) -> bool:
        """
        Vérifie si une combinaison mariage est bloquée (admin, auto ou dérivé).
        """
        obj = TirageCombiStats.objects.filter(
            tirage=tirage, jeu_type=TirageCombiType.MARIAGE, valeur=valeur
        ).first()
        if obj and (obj.bloque_admin or obj.bloque_auto or obj.bloque_derived):
            return True
        return False
