from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone

from accounts.models import Tirage
from core.services.ticket_validation_service import TicketValidationService


def _generate_ticket_number(now: datetime) -> str:
    # unique in-memory, human readable
    return f"CB-{now.year}-{now.strftime('%m%d%H%M%S%f')[-10:]}"


@dataclass(frozen=True)
class TicketPreview:
    is_valid: bool
    errors: list[str]
    free_marriages: list[dict]
    ticket_number: str
    date_str: str
    time_str: str
    admin_display_name: str
    borlette_name: str
    borlette_slogan: str
    borlette_tel: str
    borlette_city: str
    agent_name: str
    draw_names: list[str]
    ticket_lines: list[dict]
    ticket_lines_print: list[str]
    free_marriages_print: list[str]
    # New fields for ticket footer and QR code
    ticket_footer_text: str
    mariage_gratuit_actif: bool
    mariage_gratuit_montant: str
    qr_code_url: str
    borlette_logo_url: str


def build_ticket_preview(*, admin, agent, ticket_lines: list[dict], draw_ids: list[int]) -> TicketPreview:
    now = timezone.localtime(timezone.now())
    ticket_number = _generate_ticket_number(now)

    borlette = agent.borlette

    validation = TicketValidationService.validate_ticket(
        admin=admin,
        agent=agent,
        ticket_lines=ticket_lines,
        draw_ids=draw_ids,
    )

    draw_names: list[str] = []
    if draw_ids:
        draw_names = list(
            Tirage.objects.filter(id__in=draw_ids, borlette=borlette)
            .order_by("ordre_affichage", "heure_tirage")
            .values_list("nom", flat=True)
        )

    normalized_lines = _normalize_lines(ticket_lines)
    
    # Generate QR code URL for ticket verification
    qr_code_url = f"https://www.gaboombos.com/ticket/{ticket_number}"
    
    # Get borlette logo URL if available
    borlette_logo_url = ""
    if borlette.logo_borlette:
        borlette_logo_url = borlette.logo_borlette.url
    
    return TicketPreview(
        is_valid=bool(validation.get("is_valid")),
        errors=list(validation.get("errors") or []),
        free_marriages=list(validation.get("free_marriages") or []),
        ticket_number=ticket_number,
        date_str=now.strftime("%d/%m/%Y"),
        time_str=now.strftime("%H:%M"),
        admin_display_name=getattr(admin, "username", ""),
        borlette_name=getattr(borlette, "nom_borlette", ""),
        borlette_slogan=getattr(borlette, "slogan", ""),
        borlette_tel=getattr(borlette, "telephone", ""),
        borlette_city="Port-au-Prince",
        agent_name=getattr(agent, "nom", ""),
        draw_names=draw_names,
        ticket_lines=normalized_lines,
        ticket_lines_print=_format_ticket_lines_print(normalized_lines),
        free_marriages_print=_format_free_marriages_print(validation.get("free_marriages") or []),
        # New fields
        ticket_footer_text=getattr(borlette, "ticket_footer_text", "La fiche est payable une seule fois au porteur. Le montant gagné devra être réclamé avant 90 jours"),
        mariage_gratuit_actif=getattr(borlette, "mariage_gratuit_actif", False),
        mariage_gratuit_montant=str(getattr(borlette, "mariage_gratuit_montant", 0)),
        qr_code_url=qr_code_url,
        borlette_logo_url=borlette_logo_url,
    )


def _normalize_lines(lines: list[dict]) -> list[dict]:
    out: list[dict] = []
    for raw in lines or []:
        if not isinstance(raw, dict):
            continue
        jeu = (raw.get("jeu") or raw.get("game") or "").strip().upper()
        valeur = str(raw.get("valeur") or raw.get("value") or "").strip()
        mise_raw = raw.get("mise")
        if mise_raw is None:
            mise_raw = raw.get("stake")
        try:
            mise = Decimal(str(mise_raw)) if mise_raw is not None else Decimal("0")
        except Exception:
            mise = Decimal("0")

        if jeu == "MARIAGE":
            valeur = valeur.replace("-", "x")

        out.append({"jeu": jeu, "valeur": valeur, "mise": mise})
    return out


def _format_ticket_lines_print(lines: list[dict]) -> list[str]:
    out: list[str] = []
    for l in lines:
        jeu = str(l.get("jeu") or "").upper()
        valeur = str(l.get("valeur") or "")
        mise = l.get("mise")
        try:
            mise_str = str(Decimal(str(mise)))
        except Exception:
            mise_str = "0"

        # Fixed-width, thermal-friendly alignment
        out.append(f"{jeu:<7} {valeur:<6} {mise_str:>6} G")
    return out


def _format_free_marriages_print(free_marriages: list[dict]) -> list[str]:
    out: list[str] = []
    for m in free_marriages or []:
        if not isinstance(m, dict):
            continue
        valeur = str(m.get("valeur") or "").strip()
        if not valeur:
            continue
        # display as 29x12
        valeur = valeur.replace("-", "x")
        out.append(f"MARIAGE {valeur}")
    return out
