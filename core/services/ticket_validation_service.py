from __future__ import annotations

import random
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from accounts.models import (
    AdminPaymentSettings,
    MariageBlock,
    Tirage,
    TirageCombiStats,
    TirageCombiType,
    TirageNumeroStats,
    TirageStatus,
)


@dataclass(frozen=True)
class _TicketLine:
    game: str
    value: str
    stake: Decimal


class TicketValidationService:
    @staticmethod
    def validate_ticket(*, admin, agent, ticket_lines, draw_ids) -> dict:
        errors: list[str] = []
        free_marriages: list[dict] = []

        admin_borlette = getattr(admin, "borlette", None)
        if admin_borlette is None:
            return {"is_valid": False, "errors": ["Tirage fermé ou invalide"], "free_marriages": []}

        if agent is None or getattr(agent, "borlette_id", None) != admin_borlette.id:
            return {"is_valid": False, "errors": ["Tirage fermé ou invalide"], "free_marriages": []}

        draws = TicketValidationService._validate_draws(admin_borlette_id=admin_borlette.id, draw_ids=draw_ids)
        if draws is None:
            errors.append("Tirage fermé ou invalide")

        settings = TicketValidationService._get_admin_settings_readonly(admin_borlette)

        parsed_lines: list[_TicketLine] = []
        existing_marriage_keys: set[str] = set()

        for raw in ticket_lines or []:
            line = TicketValidationService._parse_line(raw)
            if line is None:
                continue

            game = TicketValidationService._normalize_game(line.game)
            if game is None:
                continue

            value = (line.value or "").strip()
            stake = line.stake

            if not TicketValidationService._validate_format(game=game, value=value, errors=errors):
                continue

            if game == "mariage":
                key = TicketValidationService._marriage_key(value)
                if key:
                    existing_marriage_keys.add(key)

            if not TicketValidationService._validate_limits(game=game, stake=stake, settings=settings, errors=errors):
                continue

            parsed_lines.append(_TicketLine(game=game, value=value, stake=stake))

        if errors:
            return {"is_valid": False, "errors": errors, "free_marriages": []}

        if draws is not None:
            TicketValidationService._validate_risk_blocks(draws=draws, lines=parsed_lines, errors=errors)

        if errors:
            return {"is_valid": False, "errors": errors, "free_marriages": []}

        total_stake = sum(l.stake for l in parsed_lines)
        free_marriages = TicketValidationService._generate_free_marriages(
            settings=settings,
            draws=draws,
            total_stake=total_stake,
            existing_marriage_keys=existing_marriage_keys,
        )

        return {"is_valid": True, "errors": [], "free_marriages": free_marriages}

    @staticmethod
    def _get_blocked_boules(draw_ids: list[int]) -> set[str]:
        """Get set of blocked boules (both auto and admin blocked) for given draws."""
        stats = TirageNumeroStats.objects.filter(
            tirage_id__in=draw_ids
        ).only("numero", "bloque_admin", "bloque_auto")
        return {
            s.numero for s in stats
            if s.bloque_admin or s.bloque_auto
        }

    @staticmethod
    def _get_auto_mariage_blocks(draw_ids: list[int]) -> set[tuple[str, str]]:
        """
        Calculate auto-derived mariage blocks from blocked boules.
        Returns set of normalized tuples (a, b) where a < b.
        """
        from itertools import permutations

        blocked_boules = TicketValidationService._get_blocked_boules(draw_ids)
        if len(blocked_boules) < 2:
            return set()

        auto_blocks = set()
        for a, b in permutations(blocked_boules, 2):
            # Normalize: store with smaller first
            if int(a) < int(b):
                auto_blocks.add((a, b))
            else:
                auto_blocks.add((b, a))
        return auto_blocks

    @staticmethod
    def _is_mariage_blocked(draw_ids: list[int], value: str) -> tuple[bool, str | None]:
        """
        Check if a mariage combo is blocked (manual or auto-derived).
        Returns: (is_blocked, source) where source is "MANUAL", "AUTO", "BOTH", or None
        """
        # Parse the value (format: 44x30 or 44-30)
        m = re.fullmatch(r"(\d{2})[-xX](\d{2})", (value or "").strip())
        if not m:
            return (False, None)

        a, b = m.group(1), m.group(2)
        # Normalize order
        if int(a) > int(b):
            a, b = b, a

        # Check manual blocks
        is_manual = any(
            MariageBlock.is_blocked(tid, a, b) for tid in draw_ids
        )

        # Check auto blocks (derived from blocked boules)
        auto_blocks = TicketValidationService._get_auto_mariage_blocks(draw_ids)
        is_auto = (a, b) in auto_blocks

        if is_manual and is_auto:
            return (True, "BOTH")
        elif is_manual:
            return (True, "MANUAL")
        elif is_auto:
            return (True, "AUTO")
        else:
            return (False, None)

    @staticmethod
    def _validate_risk_blocks(*, draws: list[Tirage], lines: list[_TicketLine], errors: list[str]) -> None:
        draw_ids = [d.id for d in draws]

        # Phase J: Check mariage blocks (manual and auto-derived) FIRST
        for line in lines:
            if TicketValidationService._normalize_game(line.game) == "mariage":
                is_blocked, source = TicketValidationService._is_mariage_blocked(draw_ids, line.value)
                if is_blocked:
                    errors.append(f"Mariage bloqué ({source}): {line.value}")
                    return

        # We check per selected draw; any blocked item blocks the ticket.
        for line in lines:
            game = TicketValidationService._normalize_game(line.game)
            if game is None:
                continue

            value = (line.value or "").strip()
            stake = line.stake

            if game == "boule":
                numero = value
                stats = list(
                    TirageNumeroStats.objects.filter(tirage_id__in=draw_ids, numero=numero).only(
                        "tirage_id",
                        "numero",
                        "mises_total",
                        "plafond_admin",
                        "bloque_auto",
                        "bloque_admin",
                    )
                )

                for s in stats:
                    if s.bloque_admin or s.bloque_auto:
                        errors.append(f"Numéro bloqué: {numero}")
                        return
                    if s.plafond_admin and (s.mises_total + stake) > s.plafond_admin:
                        errors.append(f"Plafond atteint: {numero}")
                        return

            elif game in ("mariage", "loto3", "loto4", "loto5"):
                jeu_type = (
                    TirageCombiType.MARIAGE
                    if game == "mariage"
                    else (TirageCombiType.LOTO3 if game == "loto3" else (TirageCombiType.LOTO4 if game == "loto4" else TirageCombiType.LOTO5))
                )

                # valeur is stored in canonical form for lookup.
                valeur = value
                if game == "mariage":
                    valeur = TicketValidationService._marriage_key(value) or value

                stats = list(
                    TirageCombiStats.objects.filter(tirage_id__in=draw_ids, jeu_type=jeu_type, valeur=valeur).only(
                        "tirage_id",
                        "jeu_type",
                        "valeur",
                        "mises_total",
                        "plafond_admin",
                        "bloque_auto",
                        "bloque_admin",
                    )
                )

                for s in stats:
                    if s.bloque_admin or s.bloque_auto:
                        errors.append(f"Jeu bloqué: {game} {valeur}")
                        return
                    if s.plafond_admin and (s.mises_total + stake) > s.plafond_admin:
                        errors.append(f"Plafond atteint: {game} {valeur}")
                        return

    @staticmethod
    def _get_admin_settings_readonly(borlette) -> AdminPaymentSettings:
        settings = AdminPaymentSettings.objects.filter(borlette=borlette).first()
        if settings is not None:
            return settings
        return AdminPaymentSettings(borlette=borlette)

    @staticmethod
    def _validate_draws(*, admin_borlette_id: int, draw_ids) -> list[Tirage] | None:
        ids = list(draw_ids or [])
        if not ids:
            return None

        tirages = list(Tirage.objects.filter(id__in=ids, borlette_id=admin_borlette_id))
        if len(tirages) != len(set(ids)):
            return None

        for t in tirages:
            if t.statut != TirageStatus.ACTIF:
                return None
            if t.etat_ouverture != "OUVERT":
                return None

        return tirages

    @staticmethod
    def _parse_line(raw: Any) -> _TicketLine | None:
        if not isinstance(raw, dict):
            return None

        game = (raw.get("game") or raw.get("jeu") or "").strip()
        value = raw.get("value") or raw.get("valeur") or raw.get("numero") or ""

        if game.lower() == "mariage" and not value:
            a = raw.get("a") or raw.get("x")
            b = raw.get("b") or raw.get("y")
            if a is not None and b is not None:
                value = f"{a}x{b}"

        stake_raw = raw.get("stake")
        if stake_raw is None:
            stake_raw = raw.get("mise")
        if stake_raw is None:
            stake_raw = 0

        try:
            stake = Decimal(str(stake_raw))
        except (InvalidOperation, TypeError):
            stake = Decimal("0")

        return _TicketLine(game=game, value=str(value), stake=stake)
    
    @staticmethod
    def canonicalize_value(game: str, value: str) -> str:
        g = TicketValidationService._normalize_game(game)
        if g == "mariage":
            return TicketValidationService._marriage_key(value) or value
        return (value or "").strip()

    @staticmethod
    def _normalize_game(game: str) -> str | None:
        g = (game or "").strip().lower()
        mapping = {
            "boule": "boule",
            "borlette": "boule",
            "loto3": "loto3",
            "loto 3": "loto3",
            "loto4": "loto4",
            "loto 4": "loto4",
            "loto5": "loto5",
            "loto 5": "loto5",
            "mariage": "mariage",
        }
        return mapping.get(g)

    @staticmethod
    def _validate_format(*, game: str, value: str, errors: list[str]) -> bool:
        if game == "boule":
            if not re.fullmatch(r"\d{2}", value):
                errors.append(f"Format invalide pour {game} : {value}")
                return False
            n = int(value)
            if n < 0 or n > 99:
                errors.append(f"Format invalide pour {game} : {value}")
                return False
            return True

        if game == "loto3":
            if not re.fullmatch(r"\d{3}", value):
                errors.append(f"Format invalide pour {game} : {value}")
                return False
            return True

        if game == "loto4":
            if not re.fullmatch(r"\d{4}", value):
                errors.append(f"Format invalide pour {game} : {value}")
                return False
            return True

        if game == "loto5":
            if not re.fullmatch(r"\d{5}", value):
                errors.append(f"Format invalide pour {game} : {value}")
                return False
            return True

        if game == "mariage":
            m = re.fullmatch(r"(\d{2})[-xX](\d{2})", value)
            if not m:
                errors.append(f"Format invalide pour {game} : {value}")
                return False
            a = int(m.group(1))
            b = int(m.group(2))
            if a == b:
                errors.append(f"Format invalide pour {game} : {value}")
                return False
            return True

        errors.append(f"Format invalide pour {game} : {value}")
        return False

    @staticmethod
    def _validate_limits(*, game: str, stake: Decimal, settings, errors: list[str]) -> bool:
        if stake is None:
            stake = Decimal("0")
        if stake < 0:
            errors.append(f"Mise supérieure au plafond autorisé pour {game}")
            return False

        if game == "boule":
            plafond = settings.max_boule
        elif game == "loto3":
            plafond = settings.max_loto3
        elif game == "loto4":
            plafond = settings.max_loto4
        elif game == "loto5":
            plafond = settings.max_loto5
        elif game == "mariage":
            plafond = settings.max_mariage
        else:
            return True

        if plafond is None:
            plafond = Decimal("0")

        if plafond == 0:
            errors.append(f"Jeu {game} interdit par l’admin")
            return False

        if stake > plafond:
            errors.append(f"Mise supérieure au plafond autorisé pour {game}")
            return False

        return True

    @staticmethod
    def _count_numeric_bets(lines: list[_TicketLine]) -> int:
        numeric_games = {"boule", "loto3", "loto4", "loto5"}
        return sum(1 for l in lines if l.game in numeric_games)

    @staticmethod
    def _marriage_key(value: str) -> str | None:
        m = re.fullmatch(r"(\d{2})[-xX](\d{2})", (value or "").strip())
        if not m:
            return None
        a = m.group(1)
        b = m.group(2)
        if a == b:
            return None
        x, y = sorted([a, b])
        return f"{x}x{y}"

    @staticmethod
    def _generate_free_marriages(*, settings, draws: list[Tirage] | None, total_stake: Decimal, existing_marriage_keys: set[str]) -> list[dict]:
        # Automatic generation is disabled. Free marriages are now generated client-side on the APK.
        return []
