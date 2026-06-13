from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect

from accounts.models import Borlette, PromoCode, Referral, Tirage, UserRole
from core.services.risk_management_service import RiskManagementService


User = get_user_model()


def _cors_json(data, *, status: int = 200):
    resp = JsonResponse(data, status=status)
    resp["Access-Control-Allow-Origin"] = "*"
    resp["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


def _generate_username(email: str) -> str:
    base = (email or "").split("@")[0].strip() or "admin"
    base = "".join([c for c in base if c.isalnum() or c in ("_", ".", "-")])
    if not base:
        base = "admin"

    username = base
    i = 0
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base}{i}"
    return username


@csrf_exempt
def signup_admin_borlette(request: HttpRequest):
    if request.method == "OPTIONS":
        return _cors_json({}, status=200)

    if request.method != "POST":
        return _cors_json({"error": "method_not_allowed"}, status=405)

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        return _cors_json({"error": "invalid_json"}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    borlette_name = (payload.get("borlette_name") or "").strip()
    adresse = (payload.get("adresse") or "").strip()
    slogan = (payload.get("slogan") or "").strip()
    promo_code = (payload.get("promo_code") or "").strip()

    if not email or not password or not borlette_name or not phone or not adresse or not slogan:
        return _cors_json({"error": "missing_fields"}, status=400)

    if User.objects.filter(email=email).exists():
        return _cors_json({"error": "email_already_used"}, status=409)

    if Borlette.objects.filter(nom_borlette=borlette_name).exists():
        return _cors_json({"error": "borlette_name_already_used"}, status=409)

    promo = None
    if promo_code:
        promo = PromoCode.objects.filter(code=promo_code, is_active=True).select_related("owner").first()
        if promo is None:
            return _cors_json({"error": "invalid_promo_code"}, status=400)

    with transaction.atomic():
        user = User(
            username=_generate_username(email),
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.ADMIN,
            is_active=True,
        )
        user.set_password(password)
        user.save()

        # Créer ou mettre à jour la borlette (le signal peut en avoir créé une)
        try:
            borlette = Borlette.objects.get(user=user)
            # Mettre à jour les infos si déjà créée par le signal
            borlette.nom_borlette = borlette_name
            borlette.adresse = adresse
            borlette.telephone = phone
            borlette.slogan = slogan
            borlette.save()
        except Borlette.DoesNotExist:
            Borlette.objects.create(
                user=user,
                nom_borlette=borlette_name,
                adresse=adresse,
                telephone=phone,
                slogan=slogan,
            )

        if promo is not None:
            Referral.objects.create(promo=promo, new_user=user)

    token = signing.TimestampSigner(salt="gaboom_signup").sign(str(user.id))
    redirect_url = f"http://127.0.0.1:8000/portal/auto-login/?token={token}"
    return _cors_json({"redirect_url": redirect_url}, status=201)


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


@login_required
def tirage_numeros_disponibles(request: HttpRequest, tirage_id: int):
    guard = _require_agent(request)
    if guard:
        return JsonResponse({"detail": "forbidden"}, status=403)

    agent = request.user.agent
    tirage = Tirage.objects.filter(id=tirage_id, borlette=agent.borlette).first()
    if tirage is None:
        return JsonResponse({"detail": "not_found"}, status=404)

    numeros = RiskManagementService.list_available_numbers(tirage=tirage)

    # combis: we only return those already known in DB; the app can cache and refresh.
    combis = {
        "mariage": RiskManagementService.list_available_combis(tirage=tirage, jeu_type="mariage"),
        "loto3": RiskManagementService.list_available_combis(tirage=tirage, jeu_type="loto3"),
        "loto4": RiskManagementService.list_available_combis(tirage=tirage, jeu_type="loto4"),
        "loto5": RiskManagementService.list_available_combis(tirage=tirage, jeu_type="loto5"),
    }

    return JsonResponse(
        {
            "tirage_id": tirage.id,
            "tirage_nom": tirage.nom,
            "etat": tirage.etat_ouverture,
            "numeros": numeros,
            "combis": combis,
        }
    )
