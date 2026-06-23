"""
API REST pour Agent - Architecture universelle
Endpoints sécurisés avec filtrage strict par borlette
"""
from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from typing import Any

from functools import wraps

logger = logging.getLogger(__name__)

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import models, transaction
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Count
from django.conf import settings

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from reportlab.lib.pagesizes import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

from accounts.models import Agent, Borlette, Tirage, Resultat, TirageNumeroStats, TirageStatus, UserRole, AdminPaymentSettings
from core.services.risk_management_service import RiskManagementService
from core.services.ticket_validation_service import TicketValidationService
from core.services.ticket_batch_service import TicketBatchService
from tickets.services.ticket_preview_service import build_ticket_preview

from .models import Ticket, TicketLine, TicketStatus, AgentLedgerEntry, LedgerEntryType


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def jwt_required(view_func):
    """Décorateur pour authentifier via JWT."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _json_error("Token manquant", 401)
        
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(auth_header.split(" ")[1])
            user = jwt_auth.get_user(validated_token)
            request.user = user
        except (InvalidToken, TokenError) as e:
            return _json_error(f"Token invalide: {str(e)}", 401)
        except Exception as e:
            return _json_error("Erreur authentification", 401)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def _get_agent_from_request(request: HttpRequest) -> Agent | None:
    """Extrait l'agent authentifié depuis la requête."""
    if not request.user.is_authenticated:
        return None
    if request.user.role != UserRole.AGENT:
        return None
    try:
        return request.user.agent
    except Exception:
        return None


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"success": False, "error": message}, status=status)


def _json_success(data: dict | None = None) -> JsonResponse:
    response = {"success": True}
    if data:
        response.update(data)
    return JsonResponse(response)


def _get_mariage_actif(borlette: Borlette) -> bool:
    """Lit mariage_gratuit_actif depuis AdminPaymentSettings (source unique) avec fallback"""
    settings = AdminPaymentSettings.objects.filter(borlette=borlette).first()
    if settings:
        return settings.mariage_gratuit_actif
    return borlette.mariage_gratuit_actif or False


def _get_mariage_montant(borlette: Borlette) -> Decimal:
    """Lit mariage_gratuit_montant depuis AdminPaymentSettings (source unique) avec fallback"""
    settings = AdminPaymentSettings.objects.filter(borlette=borlette).first()
    if settings:
        return settings.mariage_gratuit_montant_fixe or Decimal("0")
    return borlette.mariage_gratuit_montant or Decimal("0")


def _safe_int(value, default=1) -> int:
    """Convertit une valeur en entier avec fallback"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _rate_limit_or_429(*, request: HttpRequest, agent: Agent, scope: str, limit: int, window_seconds: int) -> JsonResponse | None:
    ip = request.META.get("REMOTE_ADDR") or "unknown"
    key = f"rl:agent:{agent.id}:ip:{ip}:scope:{scope}"
    try:
        added = cache.add(key, 1, timeout=window_seconds)
        if added:
            return None
        try:
            count = cache.incr(key)
        except Exception:
            count = (cache.get(key) or 0) + 1
            cache.set(key, count, timeout=window_seconds)
        if int(count) > int(limit):
            return _json_error("Trop de requêtes, réessayez plus tard", 429)
        return None
    except Exception:
        return None


def _safe_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _verify_hmac_signature(request: HttpRequest, agent, payload_json: str, session_key: str) -> tuple[bool, str]:
    """
    Verify HMAC signature for offline ticket sync.
    Returns (is_valid, error_message).
    """
    from accounts.models import AgentDevice, AuditAction
    from accounts.audit import log_audit
    import hmac
    import hashlib
    
    device_id = request.headers.get("X-DEVICE-ID", "")
    payload_sign = request.headers.get("X-PAYLOAD-SIGN", "")
    
    if not device_id or not payload_sign:
        return False, "Missing device signature headers"
    
    # Find device
    try:
        device = AgentDevice.objects.get(device_id=device_id, agent=agent, is_active=True)
    except AgentDevice.DoesNotExist:
        # Log tamper attempt
        log_audit(
            borlette=agent.borlette,
            actor_user=agent.user,
            actor_agent=agent,
            action=AuditAction.OFFLINE_TAMPER_BLOCKED,
            entity_type="AgentDevice",
            entity_id=device_id,
            meta={"reason": "device_not_found", "device_id": device_id}
        )
        return False, "Invalid device"
    
    # Build expected signature: HMAC_SHA256(secret, payload_json + session_key)
    message = f"{payload_json}{session_key}"
    expected_sign = hmac.new(
        device.device_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(payload_sign, expected_sign):
        # Log tamper attempt
        log_audit(
            borlette=agent.borlette,
            actor_user=agent.user,
            actor_agent=agent,
            action=AuditAction.OFFLINE_TAMPER_BLOCKED,
            entity_type="AgentDevice",
            entity_id=str(device.id),
            meta={"reason": "signature_mismatch", "device_id": device_id}
        )
        return False, "Invalid payload signature - data may have been tampered"
    
    # Update last_used_at
    device.mark_used()
    return True, ""


def _generate_ticket_number() -> str:
    now = timezone.localtime(timezone.now())
    return f"CB-{now.year}-{now.strftime('%m%d%H%M%S%f')[-10:]}"


def _create_commission_entry(ticket: Ticket) -> AgentLedgerEntry | None:
    """
    Crée une entrée COMMISSION_EARNED pour un ticket.
    Idempotent: ne crée pas si déjà existante.
    
    Commission = total_mise * agent.commission / 100
    """
    # Vérifier si commission déjà enregistrée (idempotence)
    existing = AgentLedgerEntry.objects.filter(
        related_ticket=ticket,
        entry_type=LedgerEntryType.COMMISSION_EARNED,
    ).exists()
    
    if existing:
        return None
    
    agent = ticket.agent
    commission_rate = agent.commission or Decimal("0")
    
    if commission_rate <= 0:
        return None
    
    commission_amount = (ticket.total_mise * commission_rate) / Decimal("100")
    
    if commission_amount <= 0:
        return None
    
    entry = AgentLedgerEntry.objects.create(
        agent=agent,
        borlette=ticket.borlette,
        entry_type=LedgerEntryType.COMMISSION_EARNED,
        amount=commission_amount,
        description=f"Commission ticket {ticket.numero_ticket}",
        related_ticket=ticket,
        period_key=timezone.localdate().strftime("%Y-%m-%d"),
    )
    
    return entry


# ═══════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def api_login(request: HttpRequest) -> JsonResponse:
    """
    POST /api/agent/auth/login/
    Body: {"username": "...", "password": "..."}
    Returns: agent info + JWT tokens
    """
    from rest_framework_simplejwt.tokens import RefreshToken

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return _json_error("Invalid JSON", 400)

    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        return _json_error("Username et password requis", 400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return _json_error("Identifiants invalides", 401)

    if user.role != UserRole.AGENT:
        return _json_error("Accès réservé aux agents", 403)

    try:
        agent = user.agent
    except Exception:
        return _json_error("Profil agent non trouvé", 403)

    # Générer tokens JWT
    refresh = RefreshToken.for_user(user)

    return _json_success({
        "agent": {
            "id": agent.id,
            "nom": agent.nom,
            "telephone": agent.telephone,
            "zone": agent.zone,
            "commission": float(agent.commission),
        },
        "borlette": {
            "id": agent.borlette.id,
            "nom": agent.borlette.nom_borlette,
            "telephone": agent.borlette.telephone,
            "slogan": agent.borlette.slogan or "",
            "adresse": agent.borlette.adresse or "",
            "logo_url": request.build_absolute_uri(agent.borlette.logo_borlette.url) if agent.borlette.logo_borlette else "",
            "ticket_footer_text": agent.borlette.ticket_footer_text or "La fiche est payable une seule fois au porteur. Le montant gagné devra être réclamé avant 90 jours",
            "mariage_gratuit_actif": _get_mariage_actif(agent.borlette),
            "mariage_gratuit_montant": str(_get_mariage_montant(agent.borlette)),
        },
        "tokens": {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        },
    })


# ═══════════════════════════════════════════════════════════════════════════
# TIRAGES ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@jwt_required
@require_http_methods(["GET"])
def api_tirages_actifs(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/tirages/
    Liste des tirages actifs pour la borlette de l'agent
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    from accounts.models import AdminTiragePreference

    # Récupérer l'admin de la borlette
    admin_user = agent.borlette.user

    # Récupérer les tirages désactivés par cet admin
    disabled_tirage_ids = set(
        AdminTiragePreference.objects.filter(
            user=admin_user,
            actif=False
        ).values_list('tirage_id', flat=True)
    )

    tirages = Tirage.objects.filter(
        borlette=agent.borlette,
        statut=TirageStatus.ACTIF,
    ).exclude(
        id__in=disabled_tirage_ids
    ).order_by("ordre_affichage", "heure_tirage")

    now = timezone.localtime(timezone.now())
    data = []
    for t in tirages:
        data.append({
            "id": t.id,
            "nom": t.nom,
            "type": t.type,
            "heure_ouverture": t.heure_ouverture.strftime("%H:%M") if t.heure_ouverture else "--:--",
            "heure_fermeture": t.heure_fermeture.strftime("%H:%M") if t.heure_fermeture else "--:--",
            "heure_tirage": t.heure_tirage.strftime("%H:%M") if t.heure_tirage else "--:--",
            "etat": t.etat_ouverture,
        })

    return _json_success({
        "tirages": data,
        "server_time": now.isoformat(),
    })


@jwt_required
@require_http_methods(["GET"])
def api_tirage_disponibles(request: HttpRequest, tirage_id: int) -> JsonResponse:
    """
    GET /api/agent/tirage/<id>/disponibles/
    Retourne numéros et combis jouables pour ce tirage
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    tirage = Tirage.objects.filter(
        id=tirage_id,
        borlette=agent.borlette,
    ).first()

    if not tirage:
        return _json_error("Tirage non trouvé", 404)

    numeros = RiskManagementService.list_available_numbers(tirage=tirage)
    combis = {
        "mariage": RiskManagementService.list_available_combis(tirage=tirage, jeu_type="mariage"),
        "loto3": RiskManagementService.list_available_combis(tirage=tirage, jeu_type="loto3"),
        "loto4": RiskManagementService.list_available_combis(tirage=tirage, jeu_type="loto4"),
        "loto5": RiskManagementService.list_available_combis(tirage=tirage, jeu_type="loto5"),
    }

    return _json_success({
        "tirage_id": tirage.id,
        "tirage_nom": tirage.nom,
        "etat": tirage.etat_ouverture,
        "numeros": numeros,
        "combis": combis,
    })


# ═══════════════════════════════════════════════════════════════════════════
# TICKET ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@csrf_exempt
@jwt_required
@require_http_methods(["POST"])
def api_ticket_preview(request: HttpRequest) -> JsonResponse:
    """
    POST /api/agent/ticket/preview/
    Body: {"draw_ids": [1,2], "lines": [...]}
    Retourne preview sans écriture DB
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return _json_error("Invalid JSON", 400)

    draw_ids = body.get("draw_ids", [])
    lines = body.get("lines", [])

    admin = agent.borlette.user
    preview = build_ticket_preview(
        admin=admin,
        agent=agent,
        ticket_lines=lines,
        draw_ids=draw_ids,
    )

    return _json_success({
        "is_valid": preview.is_valid,
        "errors": preview.errors,
        "ticket_number": preview.ticket_number,
        "date": preview.date_str,
        "time": preview.time_str,
        "borlette_name": preview.borlette_name,
        "borlette_slogan": preview.borlette_slogan,
        "borlette_tel": preview.borlette_tel,
        "agent_name": preview.agent_name,
        "draw_names": preview.draw_names,
        "lines": preview.ticket_lines,
        "lines_print": preview.ticket_lines_print,
        "free_marriages": preview.free_marriages,
        "free_marriages_print": preview.free_marriages_print,
    })


@csrf_exempt
@jwt_required
@require_http_methods(["POST"])
@transaction.atomic
def api_ticket_create(request: HttpRequest) -> JsonResponse:
    """
    POST /api/agent/ticket/create/
    Body: {"draw_ids": [1,2], "lines": [...]}
    Crée le ticket en DB avec validation complète
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return _json_error("Invalid JSON", 400)

    draw_ids = body.get("draw_ids", [])
    lines = body.get("lines", [])

    if not draw_ids:
        return _json_error("Aucun tirage sélectionné", 400)
    if not lines:
        return _json_error("Aucune ligne de mise", 400)

    borlette = agent.borlette
    admin = borlette.user

    # Validation via service métier
    validation = TicketValidationService.validate_ticket(
        admin=admin,
        agent=agent,
        ticket_lines=lines,
        draw_ids=draw_ids,
    )

    if not validation.get("is_valid"):
        errors = validation.get("errors", ["Ticket invalide"])
        logger.info(f"[TICKET_CREATE] Validation failed: {errors}")
        return _json_error("; ".join(errors), 400)

    # Récupérer tirage (un seul pour ticket simple)
    draw = Tirage.objects.select_for_update().filter(
        id=draw_ids[0],
        borlette=borlette,
        statut=TirageStatus.ACTIF,
    ).first()
    if not draw:
        return _json_error("Tirage fermé ou invalide", 400)
    
    # Vérifier que le tirage est ouvert
    if draw.etat_ouverture != "OUVERT":
        return _json_error("Ce tirage est fermé", 400)

    # S'assurer que la session est à jour (rotation si nouveau jour/ouverture)
    draw.ensure_current_session()

    # Créer ticket
    ticket_number = _generate_ticket_number()
    ticket = Ticket.objects.create(
        borlette=borlette,
        agent=agent,
        tirage=draw,
        tirage_session_key=draw.session_key,
        numero_ticket=ticket_number,
        total_mise=Decimal("0"),
        statut=TicketStatus.VALIDE,
    )

    # Créer lignes + mettre à jour risques
    total_mise = Decimal("0")
    created_lines = []
    free_marriages = validation.get("free_marriages", [])

    for raw in lines:
        if not isinstance(raw, dict):
            continue

        jeu = (raw.get("jeu") or raw.get("game") or "").strip().lower()
        valeur = TicketValidationService.canonicalize_value(jeu, str(raw.get("valeur") or raw.get("value") or "").strip())
        mise = _safe_decimal(raw.get("mise") if raw.get("mise") is not None else raw.get("stake"))
        potentiel_gain = _safe_decimal(raw.get("potentiel_gain", 0))
        gratuit = bool(raw.get("gratuit", False))
        option = _safe_int(raw.get("option", 1))

        if not gratuit and mise <= 0:
            continue

        line = TicketLine.objects.create(
            ticket=ticket,
            jeu=jeu,
            valeur=valeur,
            mise=mise,
            potentiel_gain=potentiel_gain,
            gratuit=gratuit,
            option=option,
        )
        created_lines.append({
            "jeu": jeu.upper(),
            "valeur": valeur,
            "mise": float(mise),
            "potentiel_gain": float(potentiel_gain),
            "gratuit": False,
        })
        total_mise += mise

        # Mettre à jour compteurs risques
        RiskManagementService.apply_bet(tirage=draw, game=jeu, value=valeur, stake=mise)

    # Ajouter mariages gratuits
    for fm in free_marriages:
        valeur = str(fm.get("valeur", "")).strip()
        if not valeur:
            continue

        TicketLine.objects.create(
            ticket=ticket,
            jeu="mariage",
            valeur=valeur,
            mise=Decimal("0"),
            potentiel_gain=Decimal("0"),
            gratuit=True,
        )
        created_lines.append({
            "jeu": "MARIAGE",
            "valeur": valeur,
            "mise": 0,
            "potentiel_gain": 0,
            "gratuit": True,
        })

    if not created_lines:
        ticket.delete()
        return _json_error("Aucune ligne de mise valide", 400)

    ticket.total_mise = total_mise
    ticket.save(update_fields=["total_mise"])

    # Créer entrée commission dans le ledger
    _create_commission_entry(ticket)
    
    # Créer entrée caisse terrain (vente)
    from agent_portal.services import create_cashbox_entry_for_sale
    create_cashbox_entry_for_sale(ticket)

    from accounts.audit import log_audit
    from accounts.models import AuditAction
    log_audit(
        action=AuditAction.TICKET_CREATE,
        entity_type="Ticket",
        entity_id=str(ticket.id),
        borlette=borlette,
        actor_user=agent.user,
        actor_agent=agent,
        request=request,
        meta={
            "ticket_no": ticket.numero_ticket,
            "tirage_id": draw.id,
            "tirage_nom": draw.nom,
            "session_key": str(draw.session_key),
            "total_mise": float(ticket.total_mise),
            "lines_count": len(created_lines),
        },
    )

    # Retourner ticket créé
    return _json_success({
        "ticket": {
            "id": str(ticket.id),
            "numero": ticket.numero_ticket,
            "total_mise": float(ticket.total_mise),
            "statut": ticket.statut,
            "created_at": ticket.created_at.isoformat(),
            "tirage_id": draw.id,
            "tirage_nom": draw.nom,
            "lines": created_lines,
        }
    })


@csrf_exempt
@jwt_required
@require_http_methods(["POST"])
def api_ticket_create_multi(request: HttpRequest) -> JsonResponse:
    """
    POST /api/agent/ticket/create-multi/
    Crée N tickets distincts, 1 par tirage sélectionné (multi-tirage)
    
    Phase I-A2: Supporte les échecs partiels - continue avec les autres tirages
    si un tirage échoue. Retourne à la fois les tickets créés et les échecs.
    
    Supports offline ticket sync with HMAC verification:
    Headers: X-DEVICE-ID, X-PAYLOAD-SIGN
    Signature: HMAC_SHA256(device_secret, payload_json + session_key)
    
    Body: {
        "tirage_ids": [6, 7],
        "entries": [{"game": "boule", "number": "44", "stake": 10}, ...],
        "overrides": {"6": {"entries": [...]}, "7": {"entries": [...]}}  // optionnel
        "session_key": "uuid-string"  // required for offline sync
    }
    
    Response: {
        "success": true/false,
        "tickets": [{"tirage_id": 1, "ticket_uuid": "...", "ticket_no": "...", "total_mise": 250}, ...],
        "failed": [{"tirage_id": 3, "error": "tirage fermé"}, ...]
    }
    """
    from accounts.audit import log_audit
    from accounts.models import AuditAction
    
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    logger.info(f"[TICKET_MULTI] Agent: {agent.id}, Borlette: {agent.borlette.id}")

    try:
        body = json.loads(request.body.decode("utf-8"))
        logger.info(f"[TICKET_MULTI] Body decoded: {body}")
    except Exception as e:
        logger.error(f"[TICKET_MULTI] Invalid JSON: {e}, body: {request.body}")
        return _json_error("Invalid JSON", 400)

    tirage_ids = body.get("tirage_ids", [])
    entries = body.get("entries", [])
    session_key = body.get("session_key", "")

    if not tirage_ids:
        return _json_error("Aucun tirage sélectionné", 400)
    if not entries:
        return _json_error("Aucune ligne de mise", 400)

    # Check if this is an offline sync (has HMAC headers)
    device_id = request.headers.get("X-DEVICE-ID", "")
    is_offline_sync = bool(device_id)

    if is_offline_sync:
        payload_json = json.dumps(body, sort_keys=True, separators=(',', ':'))
        is_valid, error_msg = _verify_hmac_signature(request, agent, payload_json, session_key)
        if not is_valid:
            logger.warning(f"[TICKET_MULTI] HMAC invalid: {error_msg}")
            from accounts.audit import log_audit
            from accounts.models import AuditAction
            log_audit(
                borlette=agent.borlette,
                actor_user=request.user,
                actor_agent=agent,
                action=AuditAction.OFFLINE_TAMPER_BLOCKED,
                entity_type="Ticket",
                entity_id="tampered",
                meta={
                    "device_id": device_id,
                    "session_key": session_key,
                    "error": error_msg,
                    "tirage_ids": tirage_ids,
                },
            )
            return _json_error(error_msg, 403)

    # Appel du service isolé (peut aussi être appelé par le Gateway Go)
    result = TicketBatchService.create_tickets(
        agent=agent,
        body=body,
        device_id=device_id,
        actor_user=request.user,
        request=request,
    )

    if not result.success:
        return _json_error(
            {"message": result.error_message, "failed": result.failed_tirages},
            result.status_code,
        )

    return _json_success(result.to_dict())


@jwt_required
@require_http_methods(["GET"])
def api_ticket_detail(request: HttpRequest, ticket_id: str) -> JsonResponse:
    """
    GET /api/agent/ticket/<uuid>/
    Détail d'un ticket
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    ticket = Ticket.objects.filter(
        id=ticket_id,
        agent=agent,
        borlette=agent.borlette,
    ).select_related("tirage").prefetch_related("lignes").first()

    if not ticket:
        return _json_error("Ticket non trouvé", 404)

    lines = []
    for l in ticket.lignes.all():
        lines.append({
            "jeu": l.jeu.upper(),
            "valeur": l.valeur,
            "mise": float(l.mise),
            "potentiel_gain": float(l.potentiel_gain),
            "gratuit": l.gratuit,
        })

    return _json_success({
        "ticket": {
            "id": str(ticket.id),
            "numero": ticket.numero_ticket,
            "total_mise": float(ticket.total_mise),
            "total_gain": float(ticket.total_gain) if ticket.total_gain else None,
            "statut": ticket.statut,
            "created_at": ticket.created_at.isoformat(),
            "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
            "tirage_id": ticket.tirage.id if ticket.tirage else None,
            "tirage_nom": ticket.tirage.nom if ticket.tirage else "",
            "group_id": str(ticket.group_id) if ticket.group_id else None,
            "lines": lines,
        }
    })


@jwt_required
@require_http_methods(["GET"])
def api_ticket_print(request: HttpRequest, ticket_id: str) -> JsonResponse:
    """
    GET /api/agent/ticket/<uuid>/print/
    Retourne données formatées pour impression ESC/POS
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    ticket = Ticket.objects.filter(
        id=ticket_id,
        agent=agent,
        borlette=agent.borlette,
    ).select_related("tirage").prefetch_related("lignes").first()

    if not ticket:
        return _json_error("Ticket non trouvé", 404)

    borlette = agent.borlette
    created = timezone.localtime(ticket.created_at)

    # Format lignes pour impression
    lines_print = []
    for l in ticket.lignes.all():
        jeu = l.jeu.upper()
        valeur = l.valeur
        mise = str(l.mise) if not l.gratuit else "GRATUIT"
        
        # Ajouter option pour LOTO4 et LOTO5 (champ option dans TicketLine)
        if jeu in ["LOTO4", "LOTO5"] and l.option and l.option >= 1:
            lines_print.append(f"{jeu:<7} {valeur:<6} OPT{l.option} {mise:>8}")
        else:
            lines_print.append(f"{jeu:<7} {valeur:<6} {mise:>8}")

    # Récupérer les noms des tirages
    tirages = [ticket.tirage.nom] if ticket.tirage else []

    # Generate QR code URL
    qr_code_url = f"https://www.gaboombos.com/ticket/{ticket.numero_ticket}"

    logo_url = ""
    if borlette.logo_borlette:
        try:
            logo_url = request.build_absolute_uri(borlette.logo_borlette.url)
        except Exception:
            logo_url = ""

    return _json_success({
        "print_data": {
            "borlette_name": borlette.nom_borlette,
            "borlette_slogan": borlette.slogan or "",
            "borlette_tel": borlette.telephone or "",
            "borlette_adresse": borlette.adresse or "",
            "borlette_site_web": borlette.site_web or "",
            "borlette_logo_url": logo_url,
            "agent_name": agent.nom,
            "ticket_number": ticket.numero_ticket,
            "group_id": str(ticket.group_id) if ticket.group_id else None,
            "date": created.strftime("%d/%m/%Y"),
            "time": created.strftime("%H:%M"),
            "tirages": tirages,
            "lines": lines_print,
            "total_mise": float(ticket.total_mise),
            "ticket_footer_text": borlette.ticket_footer_text or "La fiche est payable une seule fois au porteur. Le montant gagné devra être réclamé avant 90 jours",
            "mariage_gratuit_actif": _get_mariage_actif(borlette),
            "mariage_gratuit_montant": str(_get_mariage_montant(borlette)),
            "qr_code_url": qr_code_url,
        }
    })


@jwt_required
@require_http_methods(["GET"])
def api_ticket_pdf(request: HttpRequest, ticket_id: str) -> HttpResponse:
    """
    GET /api/agent/ticket/<uuid>/pdf/
    Génère un PDF du ticket pour impression ou sauvegarde
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    ticket = Ticket.objects.filter(
        id=ticket_id,
        agent=agent,
        borlette=agent.borlette,
    ).select_related("tirage").prefetch_related("lignes").first()

    if not ticket:
        return _json_error("Ticket non trouvé", 404)

    borlette = agent.borlette
    created = timezone.localtime(ticket.created_at)

    # Créer le PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ticket_{ticket.numero_ticket}.pdf"'

    # Configuration du document (80mm de largeur comme un ticket thermique)
    doc = SimpleDocTemplate(
        response,
        pagesize=(80 * mm, 200 * mm),
        rightMargin=5 * mm,
        leftMargin=5 * mm,
        topMargin=5 * mm,
        bottomMargin=5 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    # En-tête
    elements.append(Paragraph(f"<b>{borlette.nom_borlette}</b>", styles['Center']))
    elements.append(Paragraph(borlette.slogan or "", styles['Center']))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(f"Tel: {borlette.telephone or ''}", styles['Normal']))
    elements.append(Paragraph(borlette.ville or "", styles['Normal']))
    elements.append(Spacer(1, 3 * mm))

    # Ligne de séparation
    elements.append(Paragraph("-" * 30, styles['Center']))
    elements.append(Spacer(1, 2 * mm))

    # Info ticket
    elements.append(Paragraph(f"<b>Ticket:</b> {ticket.numero_ticket}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date:</b> {created.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Heure:</b> {created.strftime('%H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(f"<b>Agent:</b> {agent.nom}", styles['Normal']))
    elements.append(Paragraph(f"<b>Tirage:</b> {ticket.tirage.nom if ticket.tirage else '—'}", styles['Normal']))
    elements.append(Spacer(1, 3 * mm))

    # Ligne de séparation
    elements.append(Paragraph("-" * 30, styles['Center']))
    elements.append(Spacer(1, 2 * mm))

    # Lignes du ticket
    table_data = [['JEU', 'VALEUR', 'MISE']]
    for l in ticket.lignes.all():
        jeu = l.jeu.upper()
        valeur = l.valeur
        mise = str(l.mise) if not l.gratuit else "GRATUIT"
        table_data.append([jeu, valeur, mise])

    table = Table(table_data, colWidths=[20 * mm, 20 * mm, 20 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 3 * mm),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 3 * mm))

    # Total
    elements.append(Paragraph(f"<b>TOTAL MISE:</b> {ticket.total_mise} G", styles['Normal']))
    elements.append(Spacer(1, 3 * mm))

    # Ligne de séparation
    elements.append(Paragraph("-" * 30, styles['Center']))
    elements.append(Spacer(1, 2 * mm))

    # Pied de page
    elements.append(Paragraph("Bonne chance", styles['Center']))
    elements.append(Paragraph("Merci pour votre confiance", styles['Center']))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(borlette.ticket_footer_text or "La fiche est payable une seule fois au porteur. Le montant gagné devra être réclamé avant 90 jours", styles['Small']))

    doc.build(elements)
    return response


# ═══════════════════════════════════════════════════════════════════════════
# HISTORIQUE & RESULTATS
# ═══════════════════════════════════════════════════════════════════════════

@jwt_required
@require_http_methods(["GET"])
def api_historique(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/historique/?limit=20&offset=0
    Historique des tickets de l'agent
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    limit = min(int(request.GET.get("limit", 20)), 100)
    offset = int(request.GET.get("offset", 0))

    tickets = (
        Ticket.objects.filter(agent=agent, borlette=agent.borlette)
        .exclude(statut=TicketStatus.PREVIEW)
        .order_by("-created_at")
        .select_related("tirage")[offset:offset + limit]
    )

    data = []
    for t in tickets:
        # Récupérer tous les tirages liés (via group_id pour multi-tirage)
        tirages_list = []
        if t.tirage:
            tirages_list.append(t.tirage.nom)
        
        data.append({
            "id": str(t.id),
            "numero": t.numero_ticket,
            "total_mise": float(t.total_mise),
            "total_gain": float(t.total_gain) if t.total_gain else None,
            "statut": t.statut,
            "created_at": t.created_at.isoformat(),
            "tirages": tirages_list,
            "lines": [],
        })

    return _json_success({"tickets": data})


@jwt_required
@require_http_methods(["GET"])
def api_resultats(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/resultats/?limit=20
    Derniers résultats des tirages de la borlette avec tous les lots
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    limit = min(int(request.GET.get("limit", 20)), 50)

    resultats = (
        Resultat.objects.filter(tirage__borlette=agent.borlette)
        .select_related("tirage")
        .order_by("-date", "-created_at")[:limit]
    )

    data = []
    for r in resultats:
        data.append({
            "id": r.id,
            "tirage_id": r.tirage.id,
            "tirage_nom": r.tirage.nom,
            "tirage_type": r.tirage.type,
            "date": r.date.isoformat(),
            "heure_tirage": r.tirage.heure_tirage.strftime("%H:%M") if r.tirage.heure_tirage else "--:--",
            # Les 3 lots de base
            "lot1": r.lot1,
            "lot2": r.lot2,
            "lot3": r.lot3,
            # Loto3
            "loto3": r.loto3,
            # Loto4 (3 options)
            "loto4_opt1": r.loto4_opt1,
            "loto4_opt2": r.loto4_opt2,
            "loto4_opt3": r.loto4_opt3,
            # Loto5 (3 options)
            "loto5_opt1": r.loto5_opt1,
            "loto5_opt2": r.loto5_opt2,
            "loto5_opt3": r.loto5_opt3,
        })

    return _json_success({"resultats": data})


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD AGENT
# ═══════════════════════════════════════════════════════════════════════════

@jwt_required
@require_http_methods(["GET"])
def api_dashboard(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/dashboard/?period=7|14|30
    Stats personnelles de l'agent
    period: nombre de jours (7=1 semaine, 14=2 semaines, 30=1 mois)
    
    Gains = mises - commission - gains_dus (après paiement tickets gagnants)
    Gains totaux = monte après vente, descend après paiement gain
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    # Période demandée (défaut: 7 jours)
    try:
        period_days = int(request.GET.get("period", 7))
    except ValueError:
        period_days = 7
    
    # Limiter aux valeurs valides
    if period_days not in [1, 7, 14, 30, 365]:
        period_days = 7

    today = timezone.localdate()
    period_start = today - timezone.timedelta(days=period_days - 1)

    # Tous les tickets valides de l'agent
    all_tickets = Ticket.objects.filter(
        agent=agent,
        borlette=agent.borlette,
        statut=TicketStatus.VALIDE,
    )

    # Stats du jour
    today_tickets = all_tickets.filter(created_at__date=today)
    today_agg = today_tickets.aggregate(
        count=models.Count("id"),
        total_mises=models.Sum("total_mise"),
        total_gains_du=models.Sum("total_gain_du"),
        total_gains_paye=models.Sum("total_gain_paye"),
    )

    # Stats de la période sélectionnée
    period_tickets = all_tickets.filter(created_at__date__gte=period_start)
    period_agg = period_tickets.aggregate(
        count=models.Count("id"),
        total_mises=models.Sum("total_mise"),
        total_gains_du=models.Sum("total_gain_du"),
        total_gains_paye=models.Sum("total_gain_paye"),
    )

    # Commission - Solde via Ledger (source of truth)
    commission_pct = agent.commission or Decimal("0")
    ledger_balance = AgentLedgerEntry.get_agent_balance(agent)
    
    # Stats du jour
    today_mises = today_agg.get("total_mises") or Decimal("0")
    today_gains_du = today_agg.get("total_gains_du") or Decimal("0")
    today_gains_paye = today_agg.get("total_gains_paye") or Decimal("0")
    today_commission = (today_mises * commission_pct) / Decimal("100")
    # Gain agent = mises - commission - gains_dus
    today_gain_agent = today_mises - today_commission - today_gains_du

    # Stats période
    period_mises = period_agg.get("total_mises") or Decimal("0")
    period_gains_du = period_agg.get("total_gains_du") or Decimal("0")
    period_gains_paye = period_agg.get("total_gains_paye") or Decimal("0")
    period_commission = (period_mises * commission_pct) / Decimal("100")
    # Gain agent période = mises - commission - gains_dus
    period_gain_agent = period_mises - period_commission - period_gains_du

    # Stats globales (tous les temps) pour gains totaux dynamiques
    all_agg = all_tickets.aggregate(
        total_mises=models.Sum("total_mise"),
        total_gains_du=models.Sum("total_gain_du"),
        total_gains_paye=models.Sum("total_gain_paye"),
    )
    global_mises = all_agg.get("total_mises") or Decimal("0")
    global_gains_du = all_agg.get("total_gains_du") or Decimal("0")
    global_gains_paye = all_agg.get("total_gains_paye") or Decimal("0")
    global_commission = (global_mises * commission_pct) / Decimal("100")
    # Gains totaux = mises - commission - gains_paye (monte après vente, descend après paiement)
    gains_totaux = global_mises - global_commission - global_gains_paye

    # Solde caisse physique (source of truth : mises - gains_dus - retraits + réapprovisionnements)
    from agent_portal.models import AgentCashboxEntry
    cashbox_data = AgentCashboxEntry.get_agent_cashbox_balance(agent)
    solde_caisse = float(global_mises) - float(global_gains_du) \
                   - float(cashbox_data["withdrawals"]) \
                   + float(cashbox_data["replenishments"]) \
                   + float(cashbox_data["adjustments"])

    return _json_success({
        "agent": {
            "nom": agent.nom,
            "zone": agent.zone,
            "commission_pct": float(commission_pct),
        },
        "today": {
            "tickets": today_agg.get("count") or 0,
            "mises": float(today_mises),
            "gains_du": float(today_gains_du),
            "gains_paye": float(today_gains_paye),
            "gain_agent": float(today_gain_agent),
            "commission": float(today_commission),
        },
        "period": {
            "days": period_days,
            "start_date": period_start.isoformat(),
            "tickets": period_agg.get("count") or 0,
            "mises": float(period_mises),
            "gains_du": float(period_gains_du),
            "gains_paye": float(period_gains_paye),
            "gain_agent": float(period_gain_agent),
            "commission": float(period_commission),
        },
        "global": {
            "mises": float(global_mises),
            "gains_du": float(global_gains_du),
            "gains_paye": float(global_gains_paye),
            "gains_totaux": float(gains_totaux),
            "solde_caisse": solde_caisse,
            "commission_balance": float(ledger_balance["balance"]),
            "commission_earned": float(ledger_balance["commission_earned"]),
            "commission_withdrawn": float(ledger_balance["commission_payout"]),
        },
    })


@jwt_required
@require_http_methods(["GET"])
def api_agent_caisse(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/caisse/
    Retourne le solde et historique caisse de l'agent connecté.
    Pour l'app Android.
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    # Solde caisse physique (mises - gains dus - retraits + réapprovisionnements)
    from agent_portal.models import AgentCashboxEntry

    ticket_agg = Ticket.objects.filter(
        agent=agent, statut=TicketStatus.VALIDE
    ).aggregate(
        total_mises=Sum("total_mise"),
        total_gains_du=Sum("total_gain_du"),
    )
    total_mises = ticket_agg["total_mises"] or 0
    total_gains_du = ticket_agg["total_gains_du"] or 0

    cashbox_data = AgentCashboxEntry.get_agent_cashbox_balance(agent)
    balance = float(total_mises) - float(total_gains_du) + float(cashbox_data["adjustments"]) - float(cashbox_data["withdrawals"]) + float(cashbox_data["replenishments"])

    # 10 dernières entrées caisse
    entries = AgentCashboxEntry.objects.filter(agent=agent).select_related("created_by")[:10]

    last_entries = []
    for e in entries:
        last_entries.append({
            "id": str(e.id),
            "type": e.entry_type,
            "type_display": e.get_entry_type_display(),
            "amount": float(e.amount),
            "description": e.description,
            "date": e.created_at.isoformat(),
        })

    return _json_success({
        "balance": balance,
        "total_mises": float(total_mises),
        "total_gains_du": float(total_gains_du),
        "withdrawals": float(cashbox_data["withdrawals"]),
        "replenishments": float(cashbox_data["replenishments"]),
        "adjustments": float(cashbox_data["adjustments"]),
        "last_entries": last_entries,
    })


@csrf_exempt
@jwt_required
@require_http_methods(["POST"])
def api_withdraw_commission(request: HttpRequest) -> JsonResponse:
    """
    POST /api/agent/commission/withdraw/
    L'agent retire sa commission accumulée.
    Crée une notification admin.
    
    La commission redescend à zéro après retrait.
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    # Solde actuel via Ledger
    balance_data = AgentLedgerEntry.get_agent_balance(agent)
    current_balance = balance_data["balance"]

    if current_balance <= 0:
        return _json_error("Aucune commission à retirer", 400)

    with transaction.atomic():
        today = timezone.localdate()
        # Créer entrée COMMISSION_PAYOUT (négatif = sortie)
        entry = AgentLedgerEntry.objects.create(
            agent=agent,
            borlette=agent.borlette,
            entry_type=LedgerEntryType.COMMISSION_PAYOUT,
            amount=-current_balance,
            description=f"Retrait commission par agent",
            created_by=agent.user,
            period_key=today.strftime("%Y-%m-%d"),
        )

        # Créer notification admin
        from admin_portal.models import AdminNotification
        AdminNotification.objects.create(
            borlette=agent.borlette,
            notification_type="COMMISSION_WITHDRAW",
            title=f"💰 Retrait commission - {agent.nom}",
            message=f"L'agent {agent.nom} a retiré sa commission de {current_balance:.2f} G",
            meta={
                "agent_id": agent.id,
                "agent_nom": agent.nom,
                "amount": float(current_balance),
                "entry_id": str(entry.id),
            }
        )

    # Nouveau solde (devrait être 0)
    new_balance = AgentLedgerEntry.get_agent_balance(agent)

    return _json_success({
        "amount_withdrawn": float(current_balance),
        "new_balance": float(new_balance["balance"]),
        "entry_id": str(entry.id),
    })


@jwt_required
@require_http_methods(["GET"])
def api_commission_history(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/commission/history/?period=7|30|365
    Historique des commissions de l'agent sur une période.
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    try:
        period_days = int(request.GET.get("period", 30))
    except ValueError:
        period_days = 30
    
    if period_days not in [7, 30, 90, 365]:
        period_days = 30

    today = timezone.localdate()
    start_date = today - timezone.timedelta(days=period_days)

    # Entrées de commission sur la période
    entries = AgentLedgerEntry.objects.filter(
        agent=agent,
        created_at__date__gte=start_date,
        entry_type__in=[LedgerEntryType.COMMISSION_EARNED, LedgerEntryType.COMMISSION_PAYOUT]
    ).order_by("-created_at")[:50]

    data = []
    for e in entries:
        data.append({
            "id": str(e.id),
            "type": e.entry_type,
            "type_display": e.get_entry_type_display(),
            "amount": float(e.amount),
            "description": e.description,
            "date": e.created_at.isoformat(),
        })

    # Totaux sur la période
    totals = AgentLedgerEntry.objects.filter(
        agent=agent,
        created_at__date__gte=start_date,
    ).values("entry_type").annotate(total=models.Sum("amount"))

    earned = Decimal("0")
    withdrawn = Decimal("0")
    for t in totals:
        if t["entry_type"] == LedgerEntryType.COMMISSION_EARNED:
            earned = t["total"] or Decimal("0")
        elif t["entry_type"] == LedgerEntryType.COMMISSION_PAYOUT:
            withdrawn = abs(t["total"] or Decimal("0"))

    return _json_success({
        "period_days": period_days,
        "start_date": start_date.isoformat(),
        "entries": data,
        "totals": {
            "earned": float(earned),
            "withdrawn": float(withdrawn),
            "net": float(earned - withdrawn),
        }
    })


@jwt_required
@require_http_methods(["GET"])
def api_ticket_list_agent(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/tickets/list/
    Liste les tickets de l'agent avec filtres.
    
    Query params:
    - date: YYYY-MM-DD (filtre par date de création)
    - tirage_id: int (filtre par tirage)
    - status: pending|won|lost|paid|cancelled (filtre par statut calculé)
    - limit: int (défaut 50, max 100)
    - offset: int (défaut 0)
    """
    from datetime import timedelta, datetime
    
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    limited = _rate_limit_or_429(request=request, agent=agent, scope="ticket_list", limit=30, window_seconds=60)
    if limited:
        return limited

    # Parse filters
    date_str = request.GET.get("date", "")
    tirage_id = request.GET.get("tirage_id", "")
    status_filter = request.GET.get("status", "")
    limit = min(int(request.GET.get("limit", 50)), 100)
    offset = int(request.GET.get("offset", 0))

    # Base queryset
    qs = Ticket.objects.filter(
        agent=agent,
        borlette=agent.borlette,
        statut__in=[TicketStatus.VALIDE, TicketStatus.PAYE, TicketStatus.ANNULE],
    ).select_related("tirage").prefetch_related("lignes").order_by("-created_at")

    # Filter by date
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            qs = qs.filter(created_at__date=date_obj)
        except ValueError:
            pass

    # Filter by tirage
    if tirage_id:
        try:
            qs = qs.filter(tirage_id=int(tirage_id))
        except ValueError:
            pass

    # Get total before status filter (for pagination info)
    total_before_status = qs.count()

    # Compute status and filter
    now = timezone.now()
    tickets_data = []
    
    for ticket in qs:
        # Compute effective status
        tirage = ticket.tirage
        tirage_open = tirage.etat_ouverture == "OUVERT" if tirage else False
        
        # IMPORTANT: Vérifier si le résultat existe pour la SESSION du ticket
        # Un ticket ne peut être gagné/perdu que si le résultat de SA session existe
        has_results = False
        if tirage and ticket.tirage_session_key:
            has_results = Resultat.objects.filter(
                tirage=tirage, 
                session_key=ticket.tirage_session_key
            ).exists()
        
        if ticket.statut == TicketStatus.ANNULE:
            computed_status = "cancelled"
        elif ticket.is_paid:
            computed_status = "paid"
        elif has_results:
            computed_status = "won" if ticket.is_winner else "lost"
        else:
            computed_status = "pending"
        
        # Apply status filter
        if status_filter and computed_status != status_filter:
            continue
        
        # Check if can be voided (< 5 minutes)
        age_minutes = (now - ticket.created_at).total_seconds() / 60
        can_void = age_minutes < 5 and ticket.statut != TicketStatus.ANNULE and not ticket.is_paid
        
        # Count bets
        num_bets = ticket.lignes.count()
        
        tickets_data.append({
            "id": str(ticket.id),
            "numero": ticket.numero_ticket,
            "group_id": str(ticket.group_id) if ticket.group_id else None,
            "tirage_id": tirage.id if tirage else None,
            "tirage_nom": tirage.nom if tirage else "N/A",
            "tirage_open": tirage_open,
            "status": computed_status,
            "num_bets": num_bets,
            "total_mise": float(ticket.total_mise),
            "total_gain_du": float(ticket.total_gain_du),
            "total_gain_paye": float(ticket.total_gain_paye),
            "is_winner": ticket.is_winner,
            "is_paid": ticket.is_paid,
            "can_pay": ticket.is_winner and not ticket.is_paid and computed_status == "won",
            "can_void": can_void,
            "can_reprint": ticket.statut != TicketStatus.ANNULE,
            "created_at": ticket.created_at.isoformat(),
            "age_minutes": round(age_minutes, 1),
        })

    # Apply pagination after status filter
    paginated = tickets_data[offset:offset + limit]
    
    return _json_success({
        "tickets": paginated,
        "total": len(tickets_data),
        "limit": limit,
        "offset": offset,
    })


@jwt_required
@require_http_methods(["GET"])
def api_ticket_search_agent(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/tickets/search/?q=...
    Recherche un ticket par numéro (côté agent).
    """
    from datetime import timedelta
    
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    limited = _rate_limit_or_429(request=request, agent=agent, scope="ticket_search", limit=30, window_seconds=60)
    if limited:
        return limited

    query = request.GET.get("q", "").strip()
    if not query:
        return _json_error("Paramètre 'q' requis", 400)

    # Chercher ticket appartenant à cet agent
    ticket = Ticket.objects.filter(
        agent=agent,
        borlette=agent.borlette,
    ).filter(
        models.Q(numero_ticket__icontains=query) | models.Q(id__icontains=query)
    ).select_related("tirage").prefetch_related("lignes").first()

    if not ticket:
        return _json_error("Ticket non trouvé", 404)

    # Vérifier si suppression possible (<7 min et pas payé)
    now = timezone.now()
    can_delete = (
        (now - ticket.created_at) <= timedelta(minutes=7)
        and ticket.total_gain_paye == 0
        and ticket.statut != TicketStatus.ANNULE
    )

    lines = []
    for line in ticket.lignes.all():
        lines.append({
            "jeu": line.jeu,
            "valeur": line.valeur,
            "mise": float(line.mise),
            "gain_du": float(line.gain_du),
            "is_winner": line.is_winner,
            "win_context": line.win_context,
        })

    return _json_success({
        "ticket": {
            "id": str(ticket.id),
            "numero": ticket.numero_ticket,
            "tirage": ticket.tirage.nom if ticket.tirage else "N/A",
            "statut": ticket.statut,
            "total_mise": float(ticket.total_mise),
            "total_gain_du": float(ticket.total_gain_du),
            "total_gain_paye": float(ticket.total_gain_paye),
            "reste_a_payer": float(ticket.total_gain_du - ticket.total_gain_paye),
            "is_winner": ticket.is_winner,
            "is_paid": ticket.is_paid,
            "created_at": ticket.created_at.isoformat(),
            "lines": lines,
        },
        "actions": {
            "can_pay": ticket.is_winner and not ticket.is_paid,
            "can_delete": can_delete,
        },
    })


@jwt_required
@require_http_methods(["GET"])
def api_ticket_group_search(request: HttpRequest, group_id: str) -> JsonResponse:
    """
    GET /api/agent/tickets/group/<group_id>/
    Recherche tous les tickets d'un groupe (multi-tirage) par QR code.
    Le QR code contient le group_id qui relie tous les tickets créés ensemble.
    """
    from datetime import timedelta
    
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    limited = _rate_limit_or_429(request=request, agent=agent, scope="ticket_group_search", limit=30, window_seconds=60)
    if limited:
        return limited

    # Chercher tous les tickets du groupe appartenant à cet agent
    tickets = Ticket.objects.filter(
        agent=agent,
        borlette=agent.borlette,
        group_id=group_id,
    ).select_related("tirage").prefetch_related("lignes").order_by("created_at")

    if not tickets.exists():
        return _json_error("Aucun ticket trouvé pour ce groupe", 404)

    now = timezone.now()
    tickets_data = []
    
    for ticket in tickets:
        # Vérifier si le résultat existe pour la session du ticket
        has_results = False
        if ticket.tirage and ticket.tirage_session_key:
            has_results = Resultat.objects.filter(
                tirage=ticket.tirage, 
                session_key=ticket.tirage_session_key
            ).exists()
        
        # Calculer le statut
        if ticket.statut == TicketStatus.ANNULE:
            computed_status = "cancelled"
        elif ticket.is_paid:
            computed_status = "paid"
        elif has_results:
            computed_status = "won" if ticket.is_winner else "lost"
        else:
            computed_status = "pending"
        
        # Vérifier si annulation possible
        age_minutes = (now - ticket.created_at).total_seconds() / 60
        can_void = age_minutes < 5 and ticket.statut != TicketStatus.ANNULE and not ticket.is_paid
        
        lines = []
        for line in ticket.lignes.all():
            lines.append({
                "jeu": line.jeu,
                "valeur": line.valeur,
                "mise": float(line.mise),
                "gain_du": float(line.gain_du),
                "is_winner": line.is_winner,
                "win_context": line.win_context,
            })
        
        tickets_data.append({
            "id": str(ticket.id),
            "numero": ticket.numero_ticket,
            "tirage_id": ticket.tirage.id if ticket.tirage else None,
            "tirage_nom": ticket.tirage.nom if ticket.tirage else "N/A",
            "status": computed_status,
            "total_mise": float(ticket.total_mise),
            "total_gain_du": float(ticket.total_gain_du),
            "total_gain_paye": float(ticket.total_gain_paye),
            "is_winner": ticket.is_winner,
            "is_paid": ticket.is_paid,
            "can_pay": ticket.is_winner and not ticket.is_paid and computed_status == "won",
            "can_void": can_void,
            "created_at": ticket.created_at.isoformat(),
            "lines": lines,
        })

    return _json_success({
        "group_id": group_id,
        "tickets": tickets_data,
        "total": len(tickets_data),
    })


@csrf_exempt
@jwt_required
@require_http_methods(["POST"])
@transaction.atomic
def api_ticket_pay_agent(request: HttpRequest, ticket_id: str) -> JsonResponse:
    """
    POST /api/agent/ticket/<uuid>/pay/
    Paye un ticket gagnant (côté agent).
    Anti-fraude: empêche double paiement, déduit de la caisse terrain.
    """
    from agent_portal.services import TicketPayoutService
    
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    limited = _rate_limit_or_429(request=request, agent=agent, scope="ticket_pay", limit=10, window_seconds=60)
    if limited:
        return limited

    # Chercher ticket appartenant à cet agent
    try:
        ticket = Ticket.objects.select_for_update().get(
            id=ticket_id,
            agent=agent,
            borlette=agent.borlette,
        )
    except Ticket.DoesNotExist:
        return _json_error("Ticket non trouvé", 404)

    from agent_portal.models import AgentCashboxEntry
    cashbox_before = AgentCashboxEntry.get_agent_cashbox_balance(agent).get("balance")

    # Utiliser le service de paiement (TOTAL uniquement)
    result = TicketPayoutService.pay_ticket(
        ticket=ticket,
        agent=agent,
        note="Paiement via app agent",
    )

    if not result["success"]:
        return _json_error(result["error"], 400)

    cashbox_after = AgentCashboxEntry.get_agent_cashbox_balance(agent).get("balance")

    from accounts.audit import log_audit
    from accounts.models import AuditAction
    log_audit(
        action=AuditAction.TICKET_PAYOUT,
        entity_type="Ticket",
        entity_id=str(ticket.id),
        borlette=agent.borlette,
        actor_user=agent.user,
        actor_agent=agent,
        request=request,
        meta={
            "ticket_no": ticket.numero_ticket,
            "payout_id": result.get("payout_id"),
            "amount_paid": float(result.get("amount_paid") or 0),
            "cashbox_before": float(cashbox_before) if cashbox_before is not None else None,
            "cashbox_after": float(cashbox_after) if cashbox_after is not None else None,
        },
    )

    return _json_success({
        "payout_id": result["payout_id"],
        "amount_paid": float(result["amount_paid"]),
        "remaining": float(result["remaining"]),
        "is_fully_paid": result["is_fully_paid"],
    })


@csrf_exempt
@jwt_required
@require_http_methods(["POST"])
@transaction.atomic
def api_ticket_void_agent(request: HttpRequest, ticket_id: str) -> JsonResponse:
    """
    POST /api/agent/ticket/<uuid>/void/
    Annule un ticket (si < 7 minutes et pas payé).
    Crée écriture inverse caisse si nécessaire.
    """
    from datetime import timedelta
    from agent_portal.services import void_ticket_with_cashbox_reversal
    
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    limited = _rate_limit_or_429(request=request, agent=agent, scope="ticket_void", limit=5, window_seconds=60)
    if limited:
        return limited

    try:
        ticket = Ticket.objects.select_for_update().get(
            id=ticket_id,
            agent=agent,
            borlette=agent.borlette,
        )
    except Ticket.DoesNotExist:
        return _json_error("Ticket non trouvé", 404)

    # Vérification délai 7 minutes
    now = timezone.now()
    age = now - ticket.created_at

    if age > timedelta(minutes=7):
        return _json_error(
            f"Annulation impossible: ticket créé il y a {int(age.total_seconds() // 60)} minutes (max 7 min)",
            400
        )

    # Utiliser le service qui gère l'écriture inverse caisse
    result = void_ticket_with_cashbox_reversal(ticket)

    if not result["success"]:
        return _json_error(result["error"], 400)

    from accounts.audit import log_audit
    from accounts.models import AuditAction
    log_audit(
        action=AuditAction.TICKET_VOID,
        entity_type="Ticket",
        entity_id=str(ticket.id),
        borlette=agent.borlette,
        actor_user=agent.user,
        actor_agent=agent,
        request=request,
        meta={
            "ticket_no": ticket.numero_ticket,
            "total_mise": float(ticket.total_mise),
            "reason": "time_window",
            "cashbox_reversed": bool(result.get("cashbox_reversed")),
        },
    )

    return _json_success({
        "message": result["message"],
        "cashbox_reversed": result["cashbox_reversed"],
    })


@jwt_required
@require_http_methods(["GET"])
def api_ticket_blueprint(request: HttpRequest, ticket_id: str) -> JsonResponse:
    """
    GET /api/agent/ticket/<uuid>/blueprint/
    Retourne le blueprint d'un ticket pour "Refaire fiche".
    Refuse si VOID ou si appartient à un autre agent.
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Non autorisé", 401)

    try:
        ticket = Ticket.objects.select_related("tirage").get(
            id=ticket_id,
            agent=agent,
            borlette=agent.borlette,
        )
    except Ticket.DoesNotExist:
        return _json_error("Ticket non trouvé ou non autorisé", 404)

    # Refuser si VOID
    if ticket.status == TicketStatus.VOID:
        return _json_error("Impossible de refaire une fiche annulée", 400)

    # Construire les lignes normalisées
    lines = []
    
    # Boules
    for i, boule in enumerate(ticket.boules or []):
        if boule:
            lines.append({
                "jeu": "boule",
                "valeur": boule,
                "mise": float(ticket.mises_boules[i]) if ticket.mises_boules and i < len(ticket.mises_boules) else 0,
            })
    
    # Mariages
    for i, mariage in enumerate(ticket.mariages or []):
        if mariage:
            lines.append({
                "jeu": "mariage",
                "valeur": mariage,
                "mise": float(ticket.mises_mariages[i]) if ticket.mises_mariages and i < len(ticket.mises_mariages) else 0,
            })
    
    # Loto3
    for i, loto3 in enumerate(ticket.loto3 or []):
        if loto3:
            lines.append({
                "jeu": "loto3",
                "valeur": loto3,
                "mise": float(ticket.mises_loto3[i]) if ticket.mises_loto3 and i < len(ticket.mises_loto3) else 0,
            })
    
    # Loto4
    for i, loto4 in enumerate(ticket.loto4 or []):
        if loto4:
            mise = float(ticket.mises_loto4[i]) if ticket.mises_loto4 and i < len(ticket.mises_loto4) else 0
            opt = ticket.options_loto4[i] if ticket.options_loto4 and i < len(ticket.options_loto4) else 1
            lines.append({
                "jeu": "loto4",
                "valeur": loto4,
                "mise": mise,
                "option": opt,
            })
    
    # Loto5
    for i, loto5 in enumerate(ticket.loto5 or []):
        if loto5:
            mise = float(ticket.mises_loto5[i]) if ticket.mises_loto5 and i < len(ticket.mises_loto5) else 0
            opt = ticket.options_loto5[i] if ticket.options_loto5 and i < len(ticket.options_loto5) else 1
            lines.append({
                "jeu": "loto5",
                "valeur": loto5,
                "mise": mise,
                "option": opt,
            })

    return _json_success({
        "ticket_id": str(ticket.id),
        "tirage_id": ticket.tirage_id,
        "tirage_nom": ticket.tirage.nom if ticket.tirage else None,
        "session_key": ticket.tirage.session_key if ticket.tirage else None,
        "lines": lines,
        "total_mise": float(ticket.total_mise),
    })


# ═══════════════════════════════════════════════════════════════════════════
# HEARTBEAT (Agent Online Status)
# ═══════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
@jwt_required
def api_agent_heartbeat(request: HttpRequest) -> JsonResponse:
    """
    POST /api/agent/heartbeat/
    Met à jour last_seen_at pour signaler que l'agent est en ligne.
    Appelé toutes les 60s par l'app Android.
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Agent non trouvé", 404)
    
    agent.last_seen_at = timezone.now()
    agent.save(update_fields=["last_seen_at"])
    
    return _json_success({"status": "ok", "timestamp": agent.last_seen_at.isoformat()})


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH CHECK (No Auth - Connection Test)
# ═══════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["GET"])
def api_health(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/health/
    Health check endpoint for testing connection from Android app.
    No authentication required - allows testing before login.
    
    Returns:
        {
            "status": "ok",
            "server_time": "2025-02-01T23:30:00-05:00",
            "version": "gaboom-central-1.0"
        }
    """
    return JsonResponse({
        "status": "ok",
        "server_time": timezone.now().isoformat(),
        "version": "gaboom-central-1.0",
    })


# ═══════════════════════════════════════════════════════════════════════════
# DEVICE REGISTRATION (Offline HMAC Signing)
# ═══════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
@jwt_required
def api_device_register(request: HttpRequest) -> JsonResponse:
    """
    POST /api/agent/device/register/
    Register device for offline ticket HMAC signing.
    Returns device_id and device_secret for signing offline payloads.
    
    Body:
        {
            "device_name": "Agent Phone Xiaomi"  // optional
        }
    
    Returns:
        {
            "success": true,
            "device_id": "dev_abc123xyz",
            "device_secret": "sec_def456uvw"  // Store securely!
        }
    """
    from accounts.models import AgentDevice, AuditAction
    from accounts.audit import log_audit
    import secrets
    
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Agent non trouvé", 404)
    
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        body = {}
    
    device_name = body.get("device_name", "")
    
    # Generate unique device_id and secret
    device_id = f"dev_{secrets.token_urlsafe(16)}"
    device_secret = secrets.token_urlsafe(32)
    
    # Create device record
    device = AgentDevice.objects.create(
        agent=agent,
        device_id=device_id,
        device_secret=device_secret,
        device_name=device_name,
        is_active=True
    )
    
    # Audit log
    log_audit(
        borlette=agent.borlette,
        actor_user=request.user,
        actor_agent=agent,
        action=AuditAction.DEVICE_REGISTER,
        entity_type="AgentDevice",
        entity_id=str(device.id),
        meta={"device_id": device_id, "device_name": device_name}
    )
    
    return _json_success({
        "device_id": device_id,
        "device_secret": device_secret,
        "device_name": device_name
    })


# ═══════════════════════════════════════════════════════════════════════════
# AGENT CONFIG (Offline settings)
# ═══════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["GET"])
@jwt_required
def api_agent_config(request: HttpRequest) -> JsonResponse:
    """
    GET /api/agent/config/
    Get agent/borlette configuration including offline mode settings.
    
    Returns:
        {
            "success": true,
            "allow_offline_print": false,
            "server_time": "2025-02-01T23:30:00-05:00",
            "version": "gaboom-central-1.0"
        }
    """
    agent = _get_agent_from_request(request)
    if not agent:
        return _json_error("Agent non trouvé", 404)
    
    borlette = agent.borlette
    
    return _json_success({
        "allow_offline_print": borlette.allow_offline_print,
        "server_time": timezone.now().isoformat(),
        "version": "gaboom-central-1.1-offline",
        "borlette": {
            "id": borlette.id,
            "nom": borlette.nom_borlette,
            "telephone": borlette.telephone,
            "slogan": borlette.slogan or "",
            "adresse": borlette.adresse or "",
            "logo_url": request.build_absolute_uri(borlette.logo_borlette.url) if borlette.logo_borlette else "",
            "ticket_footer_text": borlette.ticket_footer_text or "La fiche est payable une seule fois au porteur. Le montant gagné devra être réclamé avant 90 jours",
            "mariage_gratuit_actif": _get_mariage_actif(borlette),
            "mariage_gratuit_montant": str(_get_mariage_montant(borlette)),
        }
    })
