"""
API Endpoints pour les rapports admin.
Tous les endpoints filtrent par borlette/admin courant (isolation stricte).
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO

from django.db import models
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from accounts.models import Agent, AgentPayout, Expense, Resultat, Tirage, TirageStatus, UserRole

from admin_portal.security import get_user_borlette, staff_can


def _require_admin_api(request):
    """Vérifie que l'utilisateur est admin avec borlette."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Non authentifié"}, status=401)
    if request.user.role != UserRole.ADMIN:
        return JsonResponse({"error": "Accès refusé"}, status=403)
    borlette = get_user_borlette(request.user)
    if not borlette:
        return JsonResponse({"error": "Pas de borlette associée"}, status=403)
    return None


def _require_finance_perm(request: HttpRequest) -> JsonResponse | None:
    if not staff_can(request.user, "can_view_finance"):
        return JsonResponse({"error": "Permission refusée"}, status=403)
    return None


def _parse_period(period_str: str) -> tuple[date, date]:
    """Parse une période en dates de début et fin."""
    today = timezone.localdate()
    
    if period_str == "today":
        return today, today
    elif period_str == "7d":
        return today - timedelta(days=6), today
    elif period_str == "15d":
        return today - timedelta(days=14), today
    elif period_str == "1m":
        return today - timedelta(days=29), today
    elif period_str == "3m":
        return today - timedelta(days=89), today
    elif period_str == "6m":
        return today - timedelta(days=179), today
    elif period_str == "1y":
        return today - timedelta(days=364), today
    else:
        # Défaut: 7 jours
        return today - timedelta(days=6), today


@login_required
def api_rapports_summary(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/rapports/summary?period=...&tirage=...
    Retourne les totaux de la période.
    """
    from agent_portal.models import Ticket, TicketStatus
    from core.services.agent_commission_service import AgentCommissionService

    guard = _require_admin_api(request)
    if guard:
        return guard

    p = _require_finance_perm(request)
    if p:
        return p

    borlette = get_user_borlette(request.user)
    period = request.GET.get("period", "7d")
    tirage_id = request.GET.get("tirage", "")

    start_date, end_date = _parse_period(period)

    # Base queryset
    tickets_qs = Ticket.objects.filter(
        borlette=borlette,
        statut=TicketStatus.VALIDE,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )

    if tirage_id and tirage_id.isdigit():
        tickets_qs = tickets_qs.filter(tirage_id=int(tirage_id))

    # Agrégations
    agg = tickets_qs.aggregate(
        total_mises=models.Sum("total_mise"),
        total_gains_du=models.Sum("total_gain_du"),
        tickets_count=models.Count("id"),
        winners_count=models.Count("id", filter=models.Q(is_winner=True)),
    )

    total_mises = agg.get("total_mises") or Decimal("0")
    total_gains_du = agg.get("total_gains_du") or Decimal("0")

    # Commission agents totale (sur la période)
    agents = Agent.objects.filter(borlette=borlette)
    total_commission_due = Decimal("0")
    for agent in agents:
        agent_mises = tickets_qs.filter(agent=agent).aggregate(
            total=models.Sum("total_mise")
        )["total"] or Decimal("0")
        commission = (agent_mises * agent.commission) / Decimal("100")
        total_commission_due += commission

    # Dépenses sur la période
    expenses_qs = Expense.objects.filter(
        borlette=borlette,
        date__gte=start_date,
        date__lte=end_date,
    )
    if tirage_id and tirage_id.isdigit():
        expenses_qs = expenses_qs.filter(tirage_id=int(tirage_id))
    
    total_depenses = expenses_qs.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    # Bénéfice Net = Mises - Gains Dus - Commissions - Dépenses
    benefice_net = total_mises - total_gains_du - total_commission_due - total_depenses

    return JsonResponse({
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "label": period,
        },
        "summary": {
            "total_mises": float(total_mises),
            "total_gains_du": float(total_gains_du),
            "total_commissions": float(total_commission_due),
            "total_depenses": float(total_depenses),
            "benefice_net": float(benefice_net),
            "tickets_count": agg.get("tickets_count") or 0,
            "winners_count": agg.get("winners_count") or 0,
            "total_commission_due": float(total_commission_due),
        },
    })


@login_required
def api_rapports_tirages(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/rapports/tirages?period=...
    Retourne pertes/bénéfices par tirage.
    """
    from agent_portal.models import Ticket, TicketStatus

    guard = _require_admin_api(request)
    if guard:
        return guard

    borlette = get_user_borlette(request.user)
    period = request.GET.get("period", "7d")

    start_date, end_date = _parse_period(period)

    tirages = Tirage.objects.filter(borlette=borlette).order_by("ordre_affichage", "nom")

    data = []
    for tirage in tirages:
        tickets_qs = Ticket.objects.filter(
            borlette=borlette,
            tirage=tirage,
            statut=TicketStatus.VALIDE,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )

        agg = tickets_qs.aggregate(
            total_mises=models.Sum("total_mise"),
            total_gains_du=models.Sum("total_gain_du"),
            tickets_count=models.Count("id"),
            winners_count=models.Count("id", filter=models.Q(is_winner=True)),
        )

        mises = agg.get("total_mises") or Decimal("0")
        gains = agg.get("total_gains_du") or Decimal("0")
        benefice = mises - gains

        data.append({
            "tirage_id": tirage.id,
            "tirage_nom": tirage.nom,
            "tirage_type": tirage.type,
            "mises": float(mises),
            "gains_du": float(gains),
            "benefice_net": float(benefice),
            "perte": float(benefice) if benefice < 0 else 0,
            "tickets_count": agg.get("tickets_count") or 0,
            "winners_count": agg.get("winners_count") or 0,
        })

    return JsonResponse({
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "tirages": data,
    })


@login_required
def api_rapports_winners(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/rapports/winners?period=...&tirage=...
    Retourne les tickets gagnants avec détails.
    """
    from agent_portal.models import Ticket, TicketStatus

    guard = _require_admin_api(request)
    if guard:
        return guard

    borlette = get_user_borlette(request.user)
    period = request.GET.get("period", "7d")
    tirage_id = request.GET.get("tirage", "")
    limit = min(int(request.GET.get("limit", 100)), 500)

    start_date, end_date = _parse_period(period)

    tickets_qs = Ticket.objects.filter(
        borlette=borlette,
        statut=TicketStatus.VALIDE,
        is_winner=True,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).select_related("agent", "tirage").prefetch_related("lignes").order_by("-created_at")

    if tirage_id and tirage_id.isdigit():
        tickets_qs = tickets_qs.filter(tirage_id=int(tirage_id))

    tickets_qs = tickets_qs[:limit]

    data = []
    for ticket in tickets_qs:
        winning_lines = []
        for line in ticket.lignes.filter(is_winner=True):
            winning_lines.append({
                "jeu": line.jeu.upper(),
                "valeur": line.valeur,
                "mise": float(line.mise),
                "gain_du": float(line.gain_du),
                "win_context": line.win_context,
            })

        data.append({
            "ticket_id": str(ticket.id),
            "ticket_no": ticket.numero_ticket,
            "agent_id": ticket.agent.id,
            "agent_nom": ticket.agent.nom,
            "tirage_id": ticket.tirage.id if ticket.tirage else None,
            "tirage_nom": ticket.tirage.nom if ticket.tirage else "",
            "total_mise": float(ticket.total_mise),
            "total_gain_du": float(ticket.total_gain_du),
            "created_at": ticket.created_at.isoformat(),
            "winning_lines": winning_lines,
        })

    return JsonResponse({
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "winners": data,
        "count": len(data),
    })


@login_required
def api_rapports_results(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/rapports/results?period=...&tirage=...
    Retourne les résultats des tirages (numéros gagnants).
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    borlette = get_user_borlette(request.user)
    period = request.GET.get("period", "7d")
    tirage_id = request.GET.get("tirage", "")

    start_date, end_date = _parse_period(period)

    resultats_qs = Resultat.objects.filter(
        tirage__borlette=borlette,
        date__gte=start_date,
        date__lte=end_date,
    ).select_related("tirage").order_by("-date", "-created_at")

    if tirage_id and tirage_id.isdigit():
        resultats_qs = resultats_qs.filter(tirage_id=int(tirage_id))

    data = []
    for r in resultats_qs[:100]:
        data.append({
            "id": r.id,
            "tirage_id": r.tirage.id,
            "tirage_nom": r.tirage.nom,
            "date": r.date.isoformat(),
            "session_key": str(r.session_key),
            "lot1": r.lot1,
            "lot2": r.lot2,
            "lot3": r.lot3,
            "loto3": r.loto3,
            "loto4_opt1": r.loto4_opt1,
            "loto4_opt2": r.loto4_opt2,
            "loto4_opt3": r.loto4_opt3,
            "loto5_opt1": r.loto5_opt1,
            "loto5_opt2": r.loto5_opt2,
            "loto5_opt3": r.loto5_opt3,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
            "source": getattr(r, "source", ""),
            "statut": getattr(r, "statut", "pending"),
            "is_suspicious": bool(getattr(r, "is_suspicious", False)),
            "validated_at": r.validated_at.isoformat() if getattr(r, "validated_at", None) else None,
            "validated_by": r.validated_by.username if getattr(r, "validated_by", None) else None,
            "rejected_at": r.rejected_at.isoformat() if getattr(r, "rejected_at", None) else None,
            "rejected_by": r.rejected_by.username if getattr(r, "rejected_by", None) else None,
        })

    return JsonResponse({
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "results": data,
    })


@login_required
def api_rapports_export(request: HttpRequest) -> StreamingHttpResponse:
    """
    GET /portal/api/rapports/export.csv?type=...&period=...&tirage=...
    Export CSV streaming.
    """
    from agent_portal.models import Ticket, TicketStatus

    guard = _require_admin_api(request)
    if guard:
        return guard

    p = _require_finance_perm(request)
    if p:
        return p

    borlette = get_user_borlette(request.user)
    export_type = request.GET.get("type", "summary")
    period = request.GET.get("period", "7d")
    tirage_id = request.GET.get("tirage", "")

    start_date, end_date = _parse_period(period)

    def generate_csv():
        output = StringIO()
        writer = csv.writer(output)

        if export_type == "tirages":
            writer.writerow(["Tirage", "Type", "Mises", "Gains Dus", "Bénéfice", "Tickets", "Gagnants"])
            output.seek(0)
            yield output.read()
            output.seek(0)
            output.truncate()

            tirages = Tirage.objects.filter(borlette=borlette).order_by("nom")
            for tirage in tirages:
                tickets_qs = Ticket.objects.filter(
                    borlette=borlette,
                    tirage=tirage,
                    statut=TicketStatus.VALIDE,
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date,
                )
                agg = tickets_qs.aggregate(
                    mises=models.Sum("total_mise"),
                    gains=models.Sum("total_gain_du"),
                    count=models.Count("id"),
                    winners=models.Count("id", filter=models.Q(is_winner=True)),
                )
                mises = agg.get("mises") or 0
                gains = agg.get("gains") or 0
                writer.writerow([
                    tirage.nom,
                    tirage.type,
                    float(mises),
                    float(gains),
                    float(mises - gains),
                    agg.get("count") or 0,
                    agg.get("winners") or 0,
                ])
                output.seek(0)
                yield output.read()
                output.seek(0)
                output.truncate()

        elif export_type == "winners":
            writer.writerow(["Ticket", "Agent", "Tirage", "Date", "Mise", "Gain Dû", "Détails"])
            output.seek(0)
            yield output.read()
            output.seek(0)
            output.truncate()

            tickets_qs = Ticket.objects.filter(
                borlette=borlette,
                statut=TicketStatus.VALIDE,
                is_winner=True,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            ).select_related("agent", "tirage").prefetch_related("lignes").order_by("-created_at")

            if tirage_id and tirage_id.isdigit():
                tickets_qs = tickets_qs.filter(tirage_id=int(tirage_id))

            for ticket in tickets_qs[:1000]:
                details = "; ".join([
                    f"{l.jeu}:{l.valeur} ({l.win_context}) {l.gain_du}G"
                    for l in ticket.lignes.filter(is_winner=True)
                ])
                writer.writerow([
                    ticket.numero_ticket,
                    ticket.agent.nom,
                    ticket.tirage.nom if ticket.tirage else "",
                    ticket.created_at.strftime("%Y-%m-%d %H:%M"),
                    float(ticket.total_mise),
                    float(ticket.total_gain_du),
                    details,
                ])
                output.seek(0)
                yield output.read()
                output.seek(0)
                output.truncate()

        elif export_type == "results":
            writer.writerow(["Tirage", "Date", "Lot1", "Lot2", "Lot3", "Loto3", "Loto4-1", "Loto4-2", "Loto4-3"])
            output.seek(0)
            yield output.read()
            output.seek(0)
            output.truncate()

            resultats = Resultat.objects.filter(
                tirage__borlette=borlette,
                date__gte=start_date,
                date__lte=end_date,
            ).select_related("tirage").order_by("-date")

            if tirage_id and tirage_id.isdigit():
                resultats = resultats.filter(tirage_id=int(tirage_id))

            for r in resultats[:500]:
                writer.writerow([
                    r.tirage.nom,
                    r.date.isoformat(),
                    r.lot1,
                    r.lot2,
                    r.lot3,
                    r.loto3,
                    r.loto4_opt1,
                    r.loto4_opt2,
                    r.loto4_opt3,
                ])
                output.seek(0)
                yield output.read()
                output.seek(0)
                output.truncate()

        elif export_type == "depenses":
            writer.writerow(["Date", "Montant", "Catégorie", "Description", "Tirage", "Créé par"])
            output.seek(0)
            yield output.read()
            output.seek(0)
            output.truncate()

            expenses_qs = Expense.objects.filter(
                borlette=borlette,
                date__gte=start_date,
                date__lte=end_date,
            ).select_related("category", "tirage", "created_by").order_by("-date")

            if tirage_id and tirage_id.isdigit():
                expenses_qs = expenses_qs.filter(tirage_id=int(tirage_id))

            for e in expenses_qs[:1000]:
                writer.writerow([
                    e.date.isoformat(),
                    float(e.amount),
                    e.category.name if e.category else "",
                    e.description,
                    e.tirage.nom if e.tirage else "",
                    e.created_by.username if e.created_by else "",
                ])
                output.seek(0)
                yield output.read()
                output.seek(0)
                output.truncate()

        else:
            # Summary par défaut
            writer.writerow(["Métrique", "Valeur"])
            output.seek(0)
            yield output.read()
            output.seek(0)
            output.truncate()

            tickets_qs = Ticket.objects.filter(
                borlette=borlette,
                statut=TicketStatus.VALIDE,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            )
            if tirage_id and tirage_id.isdigit():
                tickets_qs = tickets_qs.filter(tirage_id=int(tirage_id))

            agg = tickets_qs.aggregate(
                mises=models.Sum("total_mise"),
                gains=models.Sum("total_gain_du"),
                count=models.Count("id"),
                winners=models.Count("id", filter=models.Q(is_winner=True)),
            )
            mises = agg.get("mises") or 0
            gains = agg.get("gains") or 0

            for row in [
                ["Période", f"{start_date} - {end_date}"],
                ["Total Mises", float(mises)],
                ["Total Gains Dus", float(gains)],
                ["Bénéfice Net", float(mises - gains)],
                ["Tickets", agg.get("count") or 0],
                ["Gagnants", agg.get("winners") or 0],
            ]:
                writer.writerow(row)
                output.seek(0)
                yield output.read()
                output.seek(0)
                output.truncate()

    response = StreamingHttpResponse(generate_csv(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="rapport_{export_type}_{period}.csv"'
    return response


@login_required
def api_tirages_list(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/tirages/
    Liste des tirages pour les filtres + recherche avancée.

    Params optionnels:
    - q
    - statut: open|closed
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    borlette = request.user.borlette
    qs = Tirage.objects.filter(borlette=borlette).order_by("ordre_affichage", "nom")

    q = (request.GET.get("q") or "").strip()
    statut = (request.GET.get("statut") or "").strip().lower()

    if q:
        qs = qs.filter(nom__icontains=q)

    now_t = timezone.localtime(timezone.now()).time()
    is_open_q = models.Q(heure_ouverture__lte=now_t, heure_fermeture__gte=now_t)

    if statut == "open":
        qs = qs.filter(is_open_q)
    elif statut == "closed":
        qs = qs.exclude(is_open_q)

    tirages = list(qs[:500])

    def sort_key(t: Tirage):
        is_open = t.etat_ouverture == "OUVERT" and t.statut == TirageStatus.ACTIF
        minutes = t.minutes_to_close()
        imminent_rank = 0
        if is_open and 0 < minutes <= 2:
            imminent_rank = 2
        elif is_open and 0 < minutes <= 5:
            imminent_rank = 1
        return (
            0 if is_open else 1,
            0 if imminent_rank > 0 else 1,
            0 if imminent_rank == 2 else 1,
            minutes if is_open else 10**9,
            t.heure_fermeture or t.heure_tirage,
            t.ordre_affichage,
            t.nom,
        )

    tirages.sort(key=sort_key)

    data = [
        {
            "id": t.id,
            "nom": t.nom,
            "type": t.type,
            "code": t.code,
            "statut": t.statut,
            "heure_ouverture": t.heure_ouverture.strftime("%H:%M") if t.heure_ouverture else None,
            "heure_fermeture": t.heure_fermeture.strftime("%H:%M") if t.heure_fermeture else None,
            "heure_tirage": t.heure_tirage.strftime("%H:%M") if t.heure_tirage else None,
            "etat": t.etat_ouverture,
        }
        for t in tirages
    ]

    return JsonResponse({"tirages": data, "ids": [t.id for t in tirages]})


@login_required
def api_rapports_depenses(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/rapports/depenses?period=...&tirage=...&q=...
    Liste des dépenses sur la période.
    """
    from accounts.models import ExpenseCategory

    guard = _require_admin_api(request)
    if guard:
        return guard

    borlette = request.user.borlette
    period = request.GET.get("period", "7d")
    tirage_id = request.GET.get("tirage", "")
    search_q = request.GET.get("q", "").strip()

    start_date, end_date = _parse_period(period)

    expenses_qs = Expense.objects.filter(
        borlette=borlette,
        date__gte=start_date,
        date__lte=end_date,
    ).select_related("category", "tirage", "created_by").order_by("-date")

    if tirage_id and tirage_id.isdigit():
        expenses_qs = expenses_qs.filter(tirage_id=int(tirage_id))

    if search_q:
        expenses_qs = expenses_qs.filter(
            models.Q(description__icontains=search_q) |
            models.Q(category__name__icontains=search_q)
        )

    # Limiter à 200 résultats
    expenses = expenses_qs[:200]

    data = []
    for e in expenses:
        data.append({
            "id": e.id,
            "date": e.date.isoformat(),
            "amount": float(e.amount),
            "category": e.category.name if e.category else None,
            "description": e.description,
            "tirage_nom": e.tirage.nom if e.tirage else None,
            "created_by": e.created_by.username if e.created_by else None,
            "created_at": e.created_at.isoformat(),
        })

    # Total
    total = expenses_qs.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    return JsonResponse({
        "depenses": data,
        "total": float(total),
        "count": len(data),
    })
