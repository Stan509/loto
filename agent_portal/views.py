from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import Tirage, UserRole
from core.services.risk_management_service import RiskManagementService
from tickets.services.ticket_preview_service import build_ticket_preview

from .models import Ticket, TicketLine


def _require_agent(request: HttpRequest):
    if request.user.is_superuser or request.user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        return redirect("/portal/dashboard/")
    if request.user.role != UserRole.AGENT:
        return redirect("/portal/dashboard/")
    try:
        _ = request.user.agent
    except Exception:
        return redirect("/portal/dashboard/")
    return None


def _parse_draw_ids(raw: str) -> list[int]:
    raw = (raw or "").replace(" ", "")
    out: list[int] = []
    for part in raw.split(","):
        if part.isdigit():
            out.append(int(part))
    return out


def _safe_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


@login_required
def fiche(request: HttpRequest):
    guard = _require_agent(request)
    if guard:
        return guard

    agent = request.user.agent
    admin = agent.borlette.user

    errors: list[str] = []
    preview = None
    saved_ticket = None

    available_draws = list(
        Tirage.objects.filter(borlette=agent.borlette)
        .order_by("ordre_affichage", "heure_tirage")
        .values("id", "nom", "type")
    )

    draw_ids: list[int] = []
    ticket_lines: list[dict] = []

    if request.method == "POST":
        action = (request.POST.get("action") or "preview").strip()

        draw_ids = _parse_draw_ids(request.POST.get("draw_ids") or "")

        raw_lines = request.POST.get("ticket_lines_json") or "[]"
        try:
            ticket_lines = json.loads(raw_lines)
            if not isinstance(ticket_lines, list):
                ticket_lines = []
                errors.append("Payload ticket invalide")
        except Exception:
            ticket_lines = []
            errors.append("Payload ticket invalide")

        preview = build_ticket_preview(admin=admin, agent=agent, ticket_lines=ticket_lines, draw_ids=draw_ids)

        if action == "confirm":
            if not preview.is_valid:
                errors.extend(preview.errors or ["Ticket invalide"])
            else:
                try:
                    saved_ticket = _confirm_ticket(agent=agent, ticket_number=preview.ticket_number, draw_ids=draw_ids, ticket_lines=ticket_lines)
                except ValidationError as e:
                    errors.append(str(e))
                except Exception:
                    errors.append("Erreur interne lors de la confirmation")

    else:
        preview = build_ticket_preview(admin=admin, agent=agent, ticket_lines=[], draw_ids=[])

    return render(
        request,
        "agent_portal/fiche.html",
        {
            "page_title": "Fiche",
            "errors": errors,
            "preview": preview,
            "available_draws": available_draws,
            "saved_ticket": saved_ticket,
            "draw_ids": ",".join([str(x) for x in draw_ids]) if draw_ids else "",
            "ticket_lines_json": json.dumps(ticket_lines, ensure_ascii=False) if ticket_lines else "[]",
        },
    )


@transaction.atomic
def _confirm_ticket(*, agent, ticket_number: str, draw_ids: list[int], ticket_lines: list[dict]) -> Ticket:
    from .models import TicketStatus

    borlette = agent.borlette

    draws = list(Tirage.objects.select_for_update().filter(id__in=draw_ids, borlette=borlette))
    if not draws:
        raise ValidationError("Tirage fermé ou invalide")

    # Utiliser le premier tirage pour le ticket (FK simple)
    primary_draw = draws[0]
    # S'assurer que la session est à jour
    primary_draw.ensure_current_session()

    ticket = Ticket.objects.create(
        borlette=borlette,
        agent=agent,
        tirage=primary_draw,
        tirage_session_key=primary_draw.session_key,
        numero_ticket=ticket_number,
        total_mise=Decimal("0"),
        statut=TicketStatus.VALIDE,
    )

    total_mise = Decimal("0")
    created_lines: list[TicketLine] = []

    for raw in ticket_lines or []:
        if not isinstance(raw, dict):
            continue
        jeu = (raw.get("jeu") or raw.get("game") or "").strip().lower()
        valeur = str(raw.get("valeur") or raw.get("value") or "").strip()
        mise = _safe_decimal(raw.get("mise") if raw.get("mise") is not None else raw.get("stake"))
        gratuit = bool(raw.get("gratuit", False))
        potentiel_gain = _safe_decimal(raw.get("potentiel_gain", 0))

        if mise <= 0 and not gratuit:
            continue

        line = TicketLine.objects.create(
            ticket=ticket,
            jeu=jeu,
            valeur=valeur,
            mise=mise,
            potentiel_gain=potentiel_gain,
            gratuit=gratuit,
        )
        created_lines.append(line)
        total_mise += mise

        # Update risk counters per selected draw.
        for d in draws:
            RiskManagementService.apply_bet(tirage=d, game=jeu, value=valeur, stake=mise)

    if not created_lines:
        raise ValidationError("Aucune ligne de mise valide")

    ticket.total_mise = total_mise
    ticket.save(update_fields=["total_mise"])
    return ticket


@login_required
def historique(request: HttpRequest):
    guard = _require_agent(request)
    if guard:
        return guard

    agent = request.user.agent

    tickets = (
        Ticket.objects.filter(agent=agent, borlette=agent.borlette)
        .order_by("-created_at")
        .prefetch_related("lignes")[:10]
    )

    return render(
        request,
        "agent_portal/historique.html",
        {
            "page_title": "Historique",
            "tickets": tickets,
        },
    )


@login_required
def resultat(request: HttpRequest):
    guard = _require_agent(request)
    if guard:
        return guard

    agent = request.user.agent

    tirages = (
        Tirage.objects.filter(borlette=agent.borlette, resultat__isnull=False)
        .exclude(resultat="")
        .order_by("-date_resultat", "-heure_tirage")[:50]
    )

    return render(
        request,
        "agent_portal/resultat.html",
        {
            "page_title": "Résultat",
            "tirages": tirages,
        },
    )


@dataclass(frozen=True)
class ScoreSummary:
    tickets_vendus: int
    mises_cumulees: Decimal
    gains_cumules: Decimal
    pertes: Decimal
    benefices: Decimal
    commission_agent: Decimal


@login_required
def score(request: HttpRequest):
    guard = _require_agent(request)
    if guard:
        return guard

    agent = request.user.agent

    qs = Ticket.objects.filter(agent=agent, borlette=agent.borlette, statut="VALIDE")
    agg = qs.aggregate(
        tickets=Count("id"),
        mises=Sum("total_mise"),
        gains=Sum("total_gain"),
    )

    tickets_vendus = int(agg.get("tickets") or 0)
    mises_cumulees = agg.get("mises") or Decimal("0")
    gains_cumules = agg.get("gains") or Decimal("0")

    pertes = max(mises_cumulees - gains_cumules, Decimal("0"))
    benefices = gains_cumules - mises_cumulees

    commission_pct = getattr(agent, "commission", None) or Decimal("0")
    commission_agent = (mises_cumulees * commission_pct) / Decimal("100")

    summary = ScoreSummary(
        tickets_vendus=tickets_vendus,
        mises_cumulees=mises_cumulees,
        gains_cumules=gains_cumules,
        pertes=pertes,
        benefices=benefices,
        commission_agent=commission_agent,
    )

    return render(
        request,
        "agent_portal/score.html",
        {
            "page_title": "Score",
            "summary": summary,
        },
    )


def _extract_two_digits(resultat: str) -> list[str]:
    # best-effort: extract all pairs (00-99) from resultat text
    if not resultat:
        return []
    return re.findall(r"\b\d{2}\b", resultat)


@login_required
def statistiques(request: HttpRequest):
    guard = _require_agent(request)
    if guard:
        return guard

    agent = request.user.agent

    tirage_id_raw = (request.GET.get("tirage") or "").strip()
    tirage_id = int(tirage_id_raw) if tirage_id_raw.isdigit() else None

    date_from_raw = (request.GET.get("date_from") or "").strip()
    date_to_raw = (request.GET.get("date_to") or "").strip()

    def _parse_date(s: str):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    date_from = _parse_date(date_from_raw)
    date_to = _parse_date(date_to_raw)

    qs = Tirage.objects.filter(borlette=agent.borlette).exclude(resultat="").exclude(resultat__isnull=True)
    if tirage_id is not None:
        qs = qs.filter(id=tirage_id)
    if date_from is not None:
        qs = qs.filter(date_resultat__gte=date_from)
    if date_to is not None:
        qs = qs.filter(date_resultat__lte=date_to)

    # naive prediction: most frequent 2-digit occurrences in resultat history
    counts: dict[str, int] = {}
    for t in qs.order_by("-date_resultat")[:200]:
        for n in _extract_two_digits(t.resultat or ""):
            counts[n] = counts.get(n, 0) + 1

    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]

    tirages = list(Tirage.objects.filter(borlette=agent.borlette).order_by("ordre_affichage", "heure_tirage").values("id", "nom"))

    return render(
        request,
        "agent_portal/statistiques.html",
        {
            "page_title": "Statistiques",
            "top_numbers": top,
            "tirages": tirages,
            "filters": {
                "tirage": tirage_id_raw,
                "date_from": date_from_raw,
                "date_to": date_to_raw,
            },
        },
    )


@login_required
def tchala(request: HttpRequest):
    guard = _require_agent(request)
    if guard:
        return guard

    return render(request, "agent_portal/tchala.html", {"page_title": "Tchala"})
