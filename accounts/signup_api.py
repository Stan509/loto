"""
API pour l'inscription des nouvelles borlettes avec gestion du code promo.
"""

import json
import uuid
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
from accounts.mail_service import send_custom_email


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

    import random
    token = f"{random.randint(100000, 999999)}"

    with transaction.atomic():
        # Créer l'utilisateur (commence inactif pour confirmation par mail)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=UserRole.ADMIN,
            is_active=False,
            email_verification_token=token,
            is_email_verified=False,
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

    # Envoyer l'email de confirmation
    domain = request.get_host()
    protocol = "https" if request.is_secure() else "http"
    verify_url = f"{protocol}://{domain}/accounts/verify-email/{token}/"
    
    subject = "Confirmez votre compte Gaboom Central"
    message_text = f"Bonjour {username},\n\nMerci de vous être inscrit sur Gaboom Central. Votre code de validation est : {token}\n\nVous pouvez également confirmer votre adresse email en cliquant sur le lien suivant :\n{verify_url}\n\nL'équipe Gaboom"
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #ea580c; text-align: center;">Bienvenue chez Gaboom Central</h2>
        <p>Bonjour <strong>{username}</strong>,</p>
        <p>Merci de vous être inscrit sur Gaboom Central. Votre code de validation est : <strong style="font-size: 20px; color: #ea580c; font-family: monospace;">{token}</strong></p>
        <p>Pour confirmer votre adresse email et activer votre compte, veuillez saisir ce code de validation sur la page d'inscription, ou cliquer sur le bouton ci-dessous :</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}" style="background-color: #ea580c; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Confirmer mon compte</a>
        </div>
        <p style="font-size: 12px; color: #666;">Si le bouton ne fonctionne pas, copiez-collez le lien suivant dans votre navigateur :<br><a href="{verify_url}">{verify_url}</a></p>
        <hr style="border: 0; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <p style="font-size: 12px; color: #999; text-align: center;">&copy; Gaboom Central · Tous droits réservés</p>
    </div>
    """
    send_custom_email(subject, message_text, email, html_message=html_message)

    return _json_success({
        "user_id": user.id,
        "username": username,
        "borlette_id": borlette.id,
        "activation_amount": str(price_calc['total']),
        "promo_applied": bool(promo_code),
        "message": "Inscription réussie ! Un email de validation a été envoyé à votre adresse. Veuillez entrer le code reçu pour activer votre compte.",
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_verify_code(request) -> JsonResponse:
    """
    POST /api/signup/verify-code/
    Valide le code de confirmation envoyé par e-mail et active le compte.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return _json_error("JSON invalide")

    username = data.get("username", "").strip()
    code = data.get("code", "").strip()

    if not username or not code:
        return _json_error("Nom d'utilisateur et code requis.")

    user = User.objects.filter(username=username, email_verification_token=code).first()
    if not user:
        return _json_error("Code de validation ou nom d'utilisateur incorrect.")

    with transaction.atomic():
        user.is_active = True
        user.is_email_verified = True
        user.email_verification_token = None
        user.save(update_fields=["is_active", "is_email_verified", "email_verification_token"])

    # Se connecter automatiquement
    from django.contrib.auth import login
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    redirect_url = "/portal/dashboard/"
    if user.role == UserRole.AFFILIATE:
        redirect_url = "/affiliate/dashboard/"
    elif user.role == UserRole.PARTNER:
        redirect_url = "/partner/dashboard/"

    return _json_success({
        "message": "Votre compte a été activé avec succès !",
        "redirect_url": redirect_url
    })
