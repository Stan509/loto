from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.audit import log_audit
from accounts.models import AuditAction, Resultat, Tirage, TirageStatus
from core.services.lottery_fetcher import fetch_results


class Command(BaseCommand):
    help = "Sync automatique des résultats depuis une API externe (création en pending)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Exécute une seule fois puis quitte (mode Task Scheduler)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Affiche plus de détails",
        )

    def handle(self, *args, **options):
        verbose: bool = bool(options.get("verbose"))

        fetched = fetch_results()
        if verbose:
            self.stdout.write(self.style.SUCCESS(f"[sync_lottery_results] fetched={len(fetched)}"))

        created_count = 0
        skipped_count = 0
        error_count = 0

        for item in fetched:
            try:
                created = self._apply_one(
                    code=item.code,
                    numbers=item.numbers,
                    loto3_api=item.loto3,
                    d=item.date,
                    verbose=verbose,
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1
            except Exception as exc:
                error_count += 1
                if verbose:
                    self.stdout.write(self.style.ERROR(f"[sync_lottery_results] error for {item.code} {item.date}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"[sync_lottery_results] created={created_count} skipped={skipped_count} errors={error_count}"
            )
        )

    def _apply_one(self, *, code: str, numbers: list[int], loto3_api: str | None, d: date, verbose: bool) -> bool:
        code_norm = (code or "").strip().upper()
        if not code_norm:
            return False

        tirages = list(
            Tirage.objects.filter(code__iexact=code_norm, statut=TirageStatus.ACTIF).select_related("borlette")
        )
        if not tirages:
            if verbose:
                self.stdout.write(f"[sync_lottery_results] skip unknown code={code_norm}")
            return False

        created_any = False
        for tirage in tirages:
            created_any = self._apply_for_tirage(
                tirage=tirage,
                numbers=numbers,
                loto3_api=loto3_api,
                d=d,
                verbose=verbose,
            ) or created_any

        return created_any

    def _apply_for_tirage(self, *, tirage: Tirage, numbers: list[int], loto3_api: str | None, d: date, verbose: bool) -> bool:
        # Ne sync que les dates <= aujourd'hui
        today = timezone.localdate()
        if d > today:
            return False

        # Les lots sont stockés en '00'-'99'
        lot1_api = str(numbers[0]).zfill(2)
        lot2 = str(numbers[1]).zfill(2)
        lot3 = str(numbers[2]).zfill(2)

        if loto3_api is None or str(loto3_api).strip() == "":
            log_audit(
                action=AuditAction.RESULTS_SET,
                entity_type="Resultat",
                entity_id="missing_loto3",
                borlette=tirage.borlette,
                meta={
                    "mode": "auto_sync",
                    "error": "API ne fournit pas loto3 - données insuffisantes",
                    "tirage_id": tirage.id,
                    "tirage_nom": tirage.nom,
                    "tirage_code": tirage.code,
                    "date": d.isoformat(),
                    "numbers": numbers,
                },
            )
            return False

        loto3_str = str(loto3_api).zfill(3)
        complementaire = loto3_str[0]
        lot1_from_loto3 = loto3_str[1:]

        is_suspicious = lot1_api != lot1_from_loto3

        with transaction.atomic():
            try:
                r, created = Resultat.objects.update_or_create(
                    tirage=tirage,
                    date=d,
                    defaults={
                        "session_key": tirage.session_key,
                        "lot1": lot1_api,
                        "lot2": lot2,
                        "lot3": lot3,
                        "chiffre_loto3": complementaire,
                        "complementaire": complementaire,
                        "locked": False,
                        "computed_at": None,
                        "source": "API",
                        "statut": "pending",
                        "is_suspicious": is_suspicious,
                    },
                )
            except IntegrityError:
                return False

        log_audit(
            action=AuditAction.RESULTS_SET,
            entity_type="Resultat",
            entity_id=str(r.id),
            borlette=tirage.borlette,
            meta={
                "mode": "auto_sync",
                "tirage_id": tirage.id,
                "tirage_nom": tirage.nom,
                "tirage_code": tirage.code,
                "date": d.isoformat(),
                "lot1": lot1_api,
                "lot2": lot2,
                "lot3": lot3,
                "loto3": loto3_str,
                "complementaire": complementaire,
                "lot1_from_loto3": lot1_from_loto3,
                "is_suspicious": is_suspicious,
                "source": "API",
                "statut": "pending",
            },
        )

        if verbose:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[sync_lottery_results] {'created' if created else 'updated'} resultat={r.id} tirage={tirage.nom} date={d}"
                )
            )
        return created
