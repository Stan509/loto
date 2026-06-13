"""
API pour l'inscription des nouvelles borlettes avec gestion du code promo.
"""

import json
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.models import (
    User, UserRole, Borlette, PromoCode, Referral,
    AuditAction
)
from accounts.audit import log_audit
from accounts.pricing_config import calculate_director_price
from accounts.pricing_utils import create_activation_transaction


def _json_error(message: str, status: int = 400):
    return JsonResponse({"success": False, "message": message}, status=status)


def _json_success(data: dict):
    return JsonResponse({"success": True, "data": data})


@csrf_exempt
@require_http_methods(["POST"])
def api_signup(request) -> JsonResponse:
    """
    POST /api/signup/
    
    Inscription d'une nouvelle borlette avec option code promo.
    Crée l'utilisateur, la borlette, et la transaction d'activation.
    
    Body:
    {
        "username": "directeur1",
        "email": "test@example.com",
        "phone": "+50900000000",
        "password": "motdepasse",
        "borlette_name": "Ma Borlette",
        "adresse": "Port-au-Prince",
        "slogan": "Le meilleur loto",
        "promo_code": "CODE123"  // optionnel
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return _json_error("JSON invalide")

    # Champs requis
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")
    borlette_name = data.get("borlette_name", "").strip()
    adresse = data.get("adresse", "").strip()
    slogan = data.get("slogan", "").strip()
    promo_code_str = data.get("promo_code", "").strip()

    # Validation - username est obligatoire
    if not username:
        return _json_error("Le nom d'utilisateur est obligatoire")
    if not all([email, phone, password, borlette_name, adresse]):
        return _json_error("Tous les champs obligatoires doivent être remplis")

    # Vérifier si l'utilisateur existe déjà
    if User.objects.filter(username=username).exists():
        return _json_error("Ce nom d'utilisateur existe déjà", 409)
    if User.objects.filter(email=email).exists():
        return _json_error("Cet email existe déjà", 409)

    # Vérifier le code promo si fourni
    promo_code = None
    if promo_code_str:
        try:
            promo_code = PromoCode.objects.get(code=promo_code_str, is_active=True)
        except PromoCode.DoesNotExist:
            return _json_error("Code promo invalide", 400)

    with transaction.atomic():
        # Créer l'utilisateur
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=UserRole.ADMIN,
        )

        # Créer la borlette (ou mettre à jour si créée par le signal)
        try:
            borlette = Borlette.objects.get(user=user)
            # Mettre à jour les infos si déjà créée par le signal
            borlette.nom_borlette = borlette_name
            borlette.adresse = adresse
            borlette.telephone = phone
            borlette.slogan = slogan or "Votre borlette de confiance"
            borlette.save()
        except Borlette.DoesNotExist:
            borlette = Borlette.objects.create(
                user=user,
                nom_borlette=borlette_name,
                adresse=adresse,
                telephone=phone,
                slogan=slogan or "Votre borlette de confiance",
            )

        # Créer la référence si code promo utilisé
        if promo_code:
            Referral.objects.create(
                promo=promo_code,
                new_user=user,
            )

        # Calculer le prix (0 agents pour l'inscription initiale)
        price_calc = calculate_director_price(agents_count=0, has_promo_code=bool(promo_code))
        
        # Créer la transaction financière
        financial_tx = create_activation_transaction(
            borlette=borlette,
            months=1,
            promo_code=promo_code,
            agents_count=0,
        )

        # Logger l'audit
        log_audit(
            action=AuditAction.BORLETTE_UPDATE,
            entity_type="Borlette",
            entity_id=str(borlette.pk),
            actor_user=user,
            meta={
                "nom_borlette": borlette_name,
                "promo_code": promo_code_str if promo_code else None,
                "activation_amount": str(price_calc['total']),
            },
            request=request,
        )

    return _json_success({
        "user_id": user.id,
        "borlette_id": borlette.id,
        "activation_amount": str(price_calc['total']),
        "promo_applied": bool(promo_code),
        "message": "Inscription réussie ! Connectez-vous pour accéder à votre dashboard.",
    })
