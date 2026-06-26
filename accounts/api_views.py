from __future__ import annotations

import json
import random
import re
import string
import uuid
from decimal import Decimal
from accounts.mail_service import send_custom_email

from functools import wraps

from django.contrib.auth import get_user_model, login
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.db.models import Sum

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from accounts.audit import log_audit
from accounts.models import (
    AuditAction,
    FinancialSplit,
    FinancialSplitRole,
    PromoCode,
    Referral,
    WithdrawalRequest,
    WithdrawalStatus,
    UserRole,
)
from accounts.withdrawals import get_affiliate_balance


User = get_user_model()


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"success": False, "error": message}, status=status)


def _json_success(data: dict | None = None) -> JsonResponse:
    payload = {"success": True}
    if data:
        payload.update(data)
    return JsonResponse(payload)


def _cors_json(request: HttpRequest, data, *, status: int = 200):
    resp = JsonResponse(data, status=status)
    origin = request.headers.get("Origin")
    if origin:
        resp["Access-Control-Allow-Origin"] = origin
        resp["Vary"] = "Origin"
        resp["Access-Control-Allow-Credentials"] = "true"
    else:
        resp["Access-Control-Allow-Origin"] = "*"
    resp["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


def clean_username(username: str) -> str:
    username = (username or "").upper()
    username = re.sub(r"[^A-Z0-9]", "", username)
    return username


def generate_promo_code(username: str) -> str:
    base = clean_username(username)
    suffix = "".join(random.choices(string.digits, k=3))
    return f"{base}{suffix}"


@csrf_exempt
def api_affiliate_update_code(request: HttpRequest) -> JsonResponse:
    """POST /api/affiliate/update-code/

    Body: {"code": "NEWCODE"}
    """

    if request.method == "OPTIONS":
        return _cors_json(request, {}, status=200)

    if request.method != "POST":
        return _cors_json(request, {"success": False, "error": "method_not_allowed"}, status=405)

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        return _cors_json(request, {"success": False, "error": "invalid_json"}, status=400)

    requested_code_raw = (payload.get("code") or "").strip().upper()

    if not requested_code_raw:
        return _cors_json(request, {"success": False, "error": "missing_fields"}, status=400)

    if not request.user.is_authenticated:
        return _cors_json(request, {"success": False, "error": "not_authenticated"}, status=401)

    if getattr(request.user, "role", None) != UserRole.AFFILIATE:
        return _cors_json(request, {"success": False, "error": "forbidden"}, status=403)

    # Validation: min 4, no special chars
    if not re.fullmatch(r"[A-Z0-9]{4,50}", requested_code_raw):
        return _cors_json(request, {"success": False, "error": "invalid_code"}, status=400)

    user = request.user

    with transaction.atomic():
        # Unique check (exclude user's current promocode if any)
        if PromoCode.objects.filter(code=requested_code_raw).exclude(owner=user).exists():
            return _cors_json(request, {"success": False, "error": "code_already_used"}, status=409)

        promo = PromoCode.objects.select_for_update().filter(owner=user).first()
        if promo is None:
            promo = PromoCode.objects.create(code=requested_code_raw, owner=user)
        else:
            promo.code = requested_code_raw
            promo.save(update_fields=["code"])

        log_audit(
            action=AuditAction.STAFF_UPDATE,
            entity_type="PromoCode",
            entity_id=str(promo.pk),
            actor_user=user,
            meta={"promo_code": requested_code_raw, "username": user.username},
            request=request,
        )

    return _cors_json(request, {"success": True, "promo_code": requested_code_raw}, status=200)


@csrf_exempt
def api_affiliate_register(request: HttpRequest) -> JsonResponse:
    """POST /api/affiliate/register/"""

    if request.method == "OPTIONS":
        return _cors_json(request, {}, status=200)

    if request.method != "POST":
        return _cors_json(request, {"success": False, "error": "method_not_allowed"}, status=405)

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        return _cors_json(request, {"success": False, "error": "invalid_json"}, status=400)

    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not username or not password or not email:
        return _cors_json(request, {"success": False, "error": "missing_fields"}, status=400)

    if User.objects.filter(username=username).exists():
        return _cors_json(request, {"success": False, "error": "username_already_used"}, status=409)

    if User.objects.filter(email=email).exists():
        return _cors_json(request, {"success": False, "error": "email_already_used"}, status=409)

    token = uuid.uuid4().hex

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=UserRole.AFFILIATE,
                is_active=False,
                email_verification_token=token,
                is_email_verified=False,
            )

            code = generate_promo_code(username)
            tries = 0
            while PromoCode.objects.filter(code=code).exists():
                tries += 1
                if tries > 50:
                    raise RuntimeError("promo_code_generation_failed")
                code = generate_promo_code(username)

            promo = PromoCode.objects.create(code=code, owner=user)

            log_audit(
                action=AuditAction.STAFF_CREATE,
                entity_type="PromoCode",
                entity_id=str(promo.pk),
                actor_user=user,
                meta={"promo_code": code, "username": username},
                request=request,
            )

    except RuntimeError as exc:
        if str(exc) == "promo_code_generation_failed":
            return _cors_json(request, {"success": False, "error": "promo_code_generation_failed"}, status=500)
        raise

    # Envoyer l'email de confirmation
    domain = request.get_host()
    protocol = "https" if request.is_secure() else "http"
    verify_url = f"{protocol}://{domain}/accounts/verify-email/{token}/"
    
    subject = "Confirmez votre compte Partenaire Gaboom"
    message_text = f"Bonjour {username},\n\nMerci de rejoindre le programme d'affiliation Gaboom. Veuillez confirmer votre adresse email en cliquant sur le lien suivant :\n{verify_url}\n\nL'équipe Gaboom"
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #ea580c; text-align: center;">Bienvenue chez Gaboom Affiliation</h2>
        <p>Bonjour <strong>{username}</strong>,</p>
        <p>Merci de rejoindre le programme d'affiliation Gaboom. Pour confirmer votre adresse email et activer votre compte, veuillez cliquer sur le bouton ci-dessous :</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}" style="background-color: #ea580c; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Confirmer mon compte</a>
        </div>
        <p style="font-size: 12px; color: #666;">Si le bouton ne fonctionne pas, copiez-collez le lien suivant dans votre navigateur :<br><a href="{verify_url}">{verify_url}</a></p>
        <hr style="border: 0; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <p style="font-size: 12px; color: #999; text-align: center;">&copy; Gaboom Central · Tous droits réservés</p>
    </div>
    """
    send_custom_email(subject, message_text, email, html_message=html_message)

    return _cors_json(
        request,
        {
            "success": True,
            "promo_code": code,
            "message": "Inscription réussie ! Un email de confirmation a été envoyé. Veuillez confirmer votre compte avant de vous connecter."
        },
        status=201
    )


def jwt_user_required(view_func):
    """Authenticate any user via JWT Bearer token."""

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _json_error("Token manquant", 401)

        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(auth_header.split(" ")[1])
            user = jwt_auth.get_user(validated_token)
            request.user = user
        except (InvalidToken, TokenError) as exc:
            return _json_error(f"Token invalide: {str(exc)}", 401)
        except Exception:
            return _json_error("Erreur authentification", 401)

        return view_func(request, *args, **kwargs)

    return wrapper


def session_or_jwt_user_required(view_func):
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _json_error("Non autorisé", 401)

        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(auth_header.split(" ")[1])
            user = jwt_auth.get_user(validated_token)
            request.user = user
        except (InvalidToken, TokenError) as exc:
            return _json_error(f"Token invalide: {str(exc)}", 401)
        except Exception:
            return _json_error("Erreur authentification", 401)

        return view_func(request, *args, **kwargs)

    return wrapper


def _safe_decimal(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


@csrf_exempt
@session_or_jwt_user_required
@require_http_methods(["POST"])
def api_affiliate_withdraw(request: HttpRequest) -> JsonResponse:
    """POST /api/affiliate/withdraw/

    Body: {"amount": 123.45, "payment_method": "MonCash"}
    Creates a pending WithdrawalRequest after balance check.
    """

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return _json_error("Non autorisé", 401)

    if request.user.role != UserRole.AFFILIATE:
        return _json_error("Accès refusé", 403)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        body = {}

    amount = _safe_decimal(body.get("amount"))
    payment_method = (body.get("payment_method") or "").strip()

    if amount <= 0:
        return _json_error("Montant invalide", 400)

    with transaction.atomic():
        # Lock existing paid withdrawals rows for this user to prevent double-spend races
        WithdrawalRequest.objects.select_for_update().filter(
            user=request.user, status=WithdrawalStatus.PAID
        ).exists()

        bal = get_affiliate_balance(request.user)
        if bal < amount:
            return _json_error("Solde insuffisant", 400)

        wr = WithdrawalRequest.objects.create(
            user=request.user,
            amount=amount,
            status=WithdrawalStatus.PENDING,
            payment_method=payment_method,
        )

        log_audit(
            action=AuditAction.WITHDRAWAL_CREATE,
            entity_type="WithdrawalRequest",
            entity_id=str(wr.pk),
            actor_user=request.user,
            meta={"amount": str(amount), "payment_method": payment_method, "balance_before": str(bal)},
            request=request,
        )

    return _json_success({"withdrawal_id": wr.pk, "status": wr.status})


@session_or_jwt_user_required
@require_http_methods(["GET"])
def api_affiliate_balance(request: HttpRequest) -> JsonResponse:
    """GET /api/affiliate/balance/"""

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return _json_error("Non autorisé", 401)

    if request.user.role != UserRole.AFFILIATE:
        return _json_error("Accès refusé", 403)

    promo = PromoCode.objects.filter(owner=request.user).only("code").first()
    promo_code = promo.code if promo else None

    total_earned = (
        FinancialSplit.objects.filter(user=request.user, role=FinancialSplitRole.AFFILIATE)
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0")
    )

    total_withdrawn = (
        WithdrawalRequest.objects.filter(user=request.user, status=WithdrawalStatus.PAID)
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0")
    )

    bal = get_affiliate_balance(request.user)

    clients_count = Referral.objects.filter(promo__owner=request.user).count()

    share_link = f"http://site.com/?ref={promo_code}" if promo_code else None

    return _json_success(
        {
            "balance": float(bal),
            "total_earned": float(total_earned),
            "total_withdrawn": float(total_withdrawn),
            "clients_count": int(clients_count),
            "promo_code": promo_code,
            "username": request.user.username,
            "share_link": share_link,
        }
    )


@session_or_jwt_user_required
@require_http_methods(["GET"])
def api_affiliate_withdrawals(request: HttpRequest) -> JsonResponse:
    """GET /api/affiliate/withdrawals/ - list last withdrawals"""

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return _json_error("Non autorisé", 401)

    if request.user.role != UserRole.AFFILIATE:
        return _json_error("Accès refusé", 403)

    qs = WithdrawalRequest.objects.filter(user=request.user).order_by("-created_at")[:50]
    return _json_success({
        "withdrawals": [
            {
                "id": w.id,
                "amount": float(w.amount),
                "status": w.status,
                "payment_method": w.payment_method,
                "created_at": w.created_at.isoformat(),
                "processed_at": w.processed_at.isoformat() if w.processed_at else None,
            }
            for w in qs
        ]
    })


def _require_superadmin(request: HttpRequest) -> JsonResponse | None:
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    if not (request.user.is_superuser or request.user.role == UserRole.SUPER_ADMIN):
        return JsonResponse({"error": "SuperAdmin required"}, status=403)
    return None


@csrf_exempt
@jwt_user_required
@require_http_methods(["POST"])
def api_superadmin_withdraw_approve(request: HttpRequest, withdrawal_id: int) -> JsonResponse:
    guard = _require_superadmin(request)
    if guard:
        return guard

    with transaction.atomic():
        wr = WithdrawalRequest.objects.select_for_update().filter(pk=withdrawal_id).first()
        if wr is None:
            return JsonResponse({"error": "Not found"}, status=404)
        if wr.status != WithdrawalStatus.PENDING:
            return JsonResponse({"error": "Invalid status"}, status=400)

        wr.status = WithdrawalStatus.APPROVED
        wr.processed_at = timezone.now()
        wr.save(update_fields=["status", "processed_at"])

        log_audit(
            action=AuditAction.WITHDRAWAL_APPROVE,
            entity_type="WithdrawalRequest",
            entity_id=str(wr.pk),
            actor_user=request.user,
            meta={"amount": str(wr.amount), "user_id": wr.user_id},
            request=request,
        )

    return JsonResponse({"success": True, "status": wr.status})


@csrf_exempt
@jwt_user_required
@require_http_methods(["POST"])
def api_superadmin_withdraw_reject(request: HttpRequest, withdrawal_id: int) -> JsonResponse:
    guard = _require_superadmin(request)
    if guard:
        return guard

    with transaction.atomic():
        wr = WithdrawalRequest.objects.select_for_update().filter(pk=withdrawal_id).first()
        if wr is None:
            return JsonResponse({"error": "Not found"}, status=404)
        if wr.status != WithdrawalStatus.PENDING:
            return JsonResponse({"error": "Invalid status"}, status=400)

        wr.status = WithdrawalStatus.REJECTED
        wr.processed_at = timezone.now()
        wr.save(update_fields=["status", "processed_at"])

        log_audit(
            action=AuditAction.WITHDRAWAL_REJECT,
            entity_type="WithdrawalRequest",
            entity_id=str(wr.pk),
            actor_user=request.user,
            meta={"amount": str(wr.amount), "user_id": wr.user_id},
            request=request,
        )

    return JsonResponse({"success": True, "status": wr.status})


@csrf_exempt
@jwt_user_required
@require_http_methods(["POST"])
def api_superadmin_withdraw_mark_paid(request: HttpRequest, withdrawal_id: int) -> JsonResponse:
    guard = _require_superadmin(request)
    if guard:
        return guard

    with transaction.atomic():
        wr = WithdrawalRequest.objects.select_for_update().filter(pk=withdrawal_id).first()
        if wr is None:
            return JsonResponse({"error": "Not found"}, status=404)
        if wr.status == WithdrawalStatus.PAID:
            return JsonResponse({"error": "Already paid"}, status=400)
        if wr.status != WithdrawalStatus.APPROVED:
            return JsonResponse({"error": "Must be approved first"}, status=400)

        wr.status = WithdrawalStatus.PAID
        wr.processed_at = timezone.now()
        wr.save(update_fields=["status", "processed_at"])

        log_audit(
            action=AuditAction.WITHDRAWAL_MARK_PAID,
            entity_type="WithdrawalRequest",
            entity_id=str(wr.pk),
            actor_user=request.user,
            meta={"amount": str(wr.amount), "user_id": wr.user_id},
            request=request,
        )

    return JsonResponse({"success": True, "status": wr.status})
