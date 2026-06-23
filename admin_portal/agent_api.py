"""
API Endpoints pour la gestion des agents (paiements via Ledger).
Source of truth: AgentLedgerEntry
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.db import models, transaction
from django.http import HttpRequest, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Agent, UserRole

from admin_portal.security import get_user_borlette, staff_can
from agent_portal.models import Ticket, TicketStatus, AgentLedgerEntry, LedgerEntryType


PERIOD_RANGES = {
    "today": 0,
    "7d": 6,
    "1m": 29,
    "1y": 364,
}


def _require_admin_api(request: HttpRequest) -> JsonResponse | None:
    """Vérifie que l'utilisateur est admin avec borlette."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Non authentifié"}, status=401)
    if request.user.role != UserRole.ADMIN:
        return JsonResponse({"error": "Accès refusé"}, status=403)
    borlette = get_user_borlette(request.user)
    if not borlette:
        return JsonResponse({"error": "Pas de borlette associée"}, status=403)
    return None


def calculate_agent_balance(agent: Agent) -> dict:
    """
    Calcule le solde d'un agent via le Ledger (source of truth).
    
    Returns dict with:
        - total_mises: Total des mises vendues
        - total_gains_du: Total des gains dus sur ses tickets
        - commission_earned: Total commissions gagnées (via ledger)
        - commission_payout: Total payé (via ledger)
        - adjustments: Total ajustements
        - balance: Solde actuel
        - expenses: Total dépenses (séparé)
    """
    # Stats tickets pour info
    tickets_agg = Ticket.objects.filter(
        agent=agent,
        statut=TicketStatus.VALIDE,
    ).aggregate(
        total_mises=models.Sum("total_mise"),
        total_gains_du=models.Sum("total_gain_du"),
    )
    
    total_mises = tickets_agg.get("total_mises") or Decimal("0")
    total_gains_du = tickets_agg.get("total_gains_du") or Decimal("0")
    
    # Solde via Ledger (source of truth)
    ledger_balance = AgentLedgerEntry.get_agent_balance(agent)
    
    return {
        "total_mises": total_mises,
        "total_gains_du": total_gains_du,
        "commission_rate": agent.commission or Decimal("0"),
        "commission_earned": ledger_balance["commission_earned"],
        "commission_payout": ledger_balance["commission_payout"],
        "adjustments": ledger_balance["adjustments"],
        "balance": ledger_balance["balance"],
        "expenses": ledger_balance["expenses"],
    }


@login_required
def api_agent_stats(request: HttpRequest, agent_id: int) -> JsonResponse:
    """
    GET /portal/api/agents/<id>/stats/
    Retourne les statistiques et solde d'un agent via Ledger.
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    borlette = get_user_borlette(request.user)
    agent = Agent.objects.filter(id=agent_id, borlette=borlette).first()
    
    if not agent:
        return JsonResponse({"error": "Agent non trouvé"}, status=404)

    stats = calculate_agent_balance(agent)
    
    return JsonResponse({
        "agent": {
            "id": agent.id,
            "nom": agent.nom,
            "telephone": agent.telephone,
            "commission_rate": float(stats["commission_rate"]),
            "latitude": float(agent.latitude) if agent.latitude is not None else None,
            "longitude": float(agent.longitude) if agent.longitude is not None else None,
            "last_location_updated_at": agent.last_location_updated_at.isoformat() if agent.last_location_updated_at else None,
        },
        "stats": {
            "total_mises": float(stats["total_mises"]),
            "total_gains_du": float(stats["total_gains_du"]),
            "commission_earned": float(stats["commission_earned"]),
            "commission_payout": float(stats["commission_payout"]),
            "adjustments": float(stats["adjustments"]),
            "balance": float(stats["balance"]),
            "expenses": float(stats["expenses"]),
        },
    })


@login_required
@require_POST
def api_agent_pay(request: HttpRequest, agent_id: int) -> JsonResponse:
    """
    POST /portal/api/agents/<id>/pay/
    Effectue un paiement commission à un agent via Ledger.
    
    Payload:
    {
        "mode": "total" | "partial",
        "amount": 5000,  // requis si mode=partial
        "description": "..."  // obligatoire
    }
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    if not staff_can(request.user, "can_manage_agents"):
        return JsonResponse({"error": "Permission refusée"}, status=403)

    borlette = get_user_borlette(request.user)
    agent = Agent.objects.filter(id=agent_id, borlette=borlette).first()
    
    if not agent:
        return JsonResponse({"error": "Agent non trouvé"}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)

    mode = data.get("mode", "total")
    description = data.get("description", "").strip()
    
    if not description:
        description = "Paiement commission"

    # Calculer solde actuel via Ledger
    stats = calculate_agent_balance(agent)
    current_balance = stats["balance"]

    if current_balance <= 0:
        return JsonResponse({"error": "Solde nul ou négatif, paiement impossible"}, status=400)

    # Déterminer montant
    if mode == "total":
        amount = current_balance
    elif mode == "partial":
        try:
            amount = Decimal(str(data.get("amount", 0)))
        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse({"error": "Montant invalide"}, status=400)
        
        if amount <= 0:
            return JsonResponse({"error": "Montant doit être > 0"}, status=400)
        
        if amount > current_balance:
            return JsonResponse({
                "error": f"Montant ({amount}) dépasse le solde ({current_balance})"
            }, status=400)
    else:
        return JsonResponse({"error": "Mode invalide (total ou partial)"}, status=400)

    # Créer entrée COMMISSION_PAYOUT dans le ledger (montant négatif)
    with transaction.atomic():
        today = timezone.localdate()
        entry = AgentLedgerEntry.objects.create(
            agent=agent,
            borlette=borlette,
            entry_type=LedgerEntryType.COMMISSION_PAYOUT,
            amount=-amount,  # Négatif car c'est une sortie
            description=description,
            created_by=request.user,
            period_key=today.strftime("%Y-%m-%d"),
        )

    # Recalculer nouveau solde
    new_stats = calculate_agent_balance(agent)

    return JsonResponse({
        "success": True,
        "entry_id": str(entry.id),
        "amount_paid": float(amount),
        "new_balance": float(new_stats["balance"]),
    })


@login_required
def api_agent_ledger(request: HttpRequest, agent_id: int) -> JsonResponse:
    """
    GET /portal/api/agents/<id>/ledger/
    Historique complet du ledger d'un agent (20 dernières entrées).
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    borlette = get_user_borlette(request.user)
    agent = Agent.objects.filter(id=agent_id, borlette=borlette).first()
    
    if not agent:
        return JsonResponse({"error": "Agent non trouvé"}, status=404)

    entries = AgentLedgerEntry.objects.filter(agent=agent).select_related("created_by")[:20]

    data = []
    for e in entries:
        data.append({
            "id": str(e.id),
            "entry_type": e.entry_type,
            "entry_type_display": e.get_entry_type_display(),
            "amount": float(e.amount),
            "description": e.description,
            "created_at": e.created_at.isoformat(),
            "created_by": e.created_by.username if e.created_by else None,
            "related_ticket": str(e.related_ticket_id) if e.related_ticket_id else None,
        })

    return JsonResponse({"entries": data})


@login_required
def api_agent_performance(request: HttpRequest, agent_id: int) -> JsonResponse:
    """GET /portal/api/agents/<id>/performance/?period=today|7d|1m|1y"""
    guard = _require_admin_api(request)
    if guard:
        return guard

    period = request.GET.get("period", "7d")
    if period not in PERIOD_RANGES:
        period = "7d"

    borlette = get_user_borlette(request.user)
    agent = Agent.objects.filter(id=agent_id, borlette=borlette).first()
    if not agent:
        return JsonResponse({"error": "Agent non trouvé"}, status=404)

    today = timezone.localdate()
    days = PERIOD_RANGES[period]
    start_date = today - timezone.timedelta(days=days)

    tickets_qs = Ticket.objects.filter(
        agent=agent,
        borlette=borlette,
        statut=TicketStatus.VALIDE,
        created_at__date__gte=start_date,
    )
    agg = tickets_qs.aggregate(
        total_mises=models.Sum("total_mise"),
        total_gains=models.Sum("total_gain_du"),
    )

    total_mises = agg.get("total_mises") or Decimal("0")
    total_gains = agg.get("total_gains") or Decimal("0")
    commission_pct = agent.commission or Decimal("0")
    commission = (total_mises * commission_pct) / Decimal("100")
    benefice = total_mises - commission - total_gains

    return JsonResponse({
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": today.isoformat(),
        "stats": {
            "total_mises": float(total_mises),
            "total_gains_du": float(total_gains),
            "commission": float(commission),
            "benefice": float(benefice),
        }
    })


@login_required
@require_POST
def api_agent_adjustment(request: HttpRequest, agent_id: int) -> JsonResponse:
    """
    POST /portal/api/agents/<id>/adjustment/
    Créer un ajustement manuel (correction).
    
    Payload:
    {
        "amount": 500,  // positif ou négatif
        "description": "..."  // obligatoire
    }
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    if not staff_can(request.user, "can_manage_agents"):
        return JsonResponse({"error": "Permission refusée"}, status=403)

    borlette = get_user_borlette(request.user)
    agent = Agent.objects.filter(id=agent_id, borlette=borlette).first()
    
    if not agent:
        return JsonResponse({"error": "Agent non trouvé"}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)

    description = data.get("description", "").strip()
    if not description:
        return JsonResponse({"error": "Description obligatoire"}, status=400)

    try:
        amount = Decimal(str(data.get("amount", 0)))
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse({"error": "Montant invalide"}, status=400)
    
    if amount == 0:
        return JsonResponse({"error": "Montant ne peut pas être 0"}, status=400)

    with transaction.atomic():
        today = timezone.localdate()
        entry = AgentLedgerEntry.objects.create(
            agent=agent,
            borlette=borlette,
            entry_type=LedgerEntryType.ADJUSTMENT,
            amount=amount,
            description=description,
            created_by=request.user,
            period_key=today.strftime("%Y-%m-%d"),
        )

    new_stats = calculate_agent_balance(agent)

    return JsonResponse({
        "success": True,
        "entry_id": str(entry.id),
        "new_balance": float(new_stats["balance"]),
    })
