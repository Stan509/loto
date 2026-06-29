"""
API endpoints for password reset / account recovery.
Generates a 6-digit code, sends via email, verifies with expiration.
"""
from __future__ import annotations

import json
import random

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.models import UserRole
from accounts.mail_service import send_custom_email

User = get_user_model()

TOKEN_EXPIRY_MINUTES = 15


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"success": False, "error": message}, status=status)


def _json_success(data: dict | None = None) -> JsonResponse:
    payload = {"success": True}
    if data:
        payload.update(data)
    return JsonResponse(payload)


def _render_html_template(template_name: str, context: dict) -> str:
    """Render a Django template to string for email HTML."""
    from django.template.loader import render_to_string
    try:
        return render_to_string(template_name, context)
    except Exception:
        return None


@csrf_exempt
@require_http_methods(["POST"])
def api_request_password_reset(request: HttpRequest) -> JsonResponse:
    """
    POST /api/request-password-reset/

    Body:
    {
        "email": "user@example.com"
    }

    Generates a 6-digit recovery code, stores it on the user with expiry,
    and sends an HTML email with the code and reset link.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return _json_error("JSON invalide", 400)

    email = data.get("email", "").strip().lower()

    if not email:
        return _json_error("L'adresse email est requise", 400)

    # Find user by email
    user = User.objects.filter(email=email).first()
    if not user:
        # Don't reveal if email exists for security
        return _json_success({
            "message": "Si cette adresse email existe, vous recevrez un code de récupération par email."
        })

    # Don't allow password reset for superusers via this API
    if user.is_superuser:
        return _json_success({
            "message": "Si cette adresse email existe, vous recevrez un code de récupération par email."
        })

    # Generate 6-digit code
    token = f"{random.randint(100000, 999999)}"
    expires_at = timezone.now() + timezone.timedelta(minutes=TOKEN_EXPIRY_MINUTES)

    with transaction.atomic():
        user.password_reset_token = token
        user.password_reset_token_expires = expires_at
        user.save(update_fields=["password_reset_token", "password_reset_token_expires"])

    # Build reset link
    domain = request.get_host()
    protocol = "https" if request.is_secure() else "http"
    reset_url = f"{protocol}://{domain}/reset-password/?email={email}&token={token}"

    # Send HTML email
    subject = "Récupération de mot de passe - Gaboom Central"
    message_text = (
        f"Bonjour {user.username},\n\n"
        f"Vous avez demandé la récupération de votre mot de passe Gaboom Central.\n"
        f"Votre code de récupération est : {token}\n\n"
        f"Ce code expirera dans {TOKEN_EXPIRY_MINUTES} minutes.\n\n"
        f"Pour réinitialiser votre mot de passe, cliquez sur le lien suivant :\n"
        f"{reset_url}\n\n"
        f"Si vous n'avez pas demandé cette récupération, ignorez simplement cet email.\n"
        f"L'équipe Gaboom"
    )

    html_message = _render_html_template("accounts/password_reset_email.html", {
        "username": user.username,
        "token": token,
        "reset_url": reset_url,
        "expiry_minutes": TOKEN_EXPIRY_MINUTES,
    })

    send_custom_email(subject, message_text, email, html_message=html_message)

    status_code = 200
    role = getattr(user, "role", None)
    message = "Un code de récupération vous a été envoyé par email."
    # Return redirect info for known roles
    redirect_url = None
    if role == UserRole.ADMIN:
        redirect_url = "/portal/reset-password/"
    elif role == UserRole.AGENT:
        redirect_url = "/agent/reset-password/"
    elif role == UserRole.AFFILIATE:
        redirect_url = "/affiliate/reset-password/"

    return _json_success({
        "message": message,
        "redirect_url": redirect_url,
        "email": email,
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_reset_password(request: HttpRequest) -> JsonResponse:
    """
    POST /api/reset-password/

    Body:
    {
        "email": "user@example.com",
        "token": "123456",
        "new_password": "newSecurePass123"
    }

    Verifies the 6-digit code, checks expiration, resets the password.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return _json_error("JSON invalide", 400)

    email = data.get("email", "").strip().lower()
    token = data.get("token", "").strip()
    new_password = data.get("new_password", "")

    if not all([email, token, new_password]):
        return _json_error("Email, code et nouveau mot de passe requis", 400)

    if len(new_password) < 6:
        return _json_error("Le mot de passe doit contenir au moins 6 caractères", 400)

    user = User.objects.filter(email=email).first()
    if not user:
        return _json_error("Aucun compte trouvé avec cette adresse email", 404)

    # Verify token
    if not user.password_reset_token:
        return _json_error("Aucun code de récupération demandé. Veuillez faire une nouvelle demande.", 400)

    if user.password_reset_token != token:
        return _json_error("Code de récupération invalide", 400)

    # Check expiration
    if user.password_reset_token_expires and timezone.now() > user.password_reset_token_expires:
        return _json_error("Le code de récupération a expiré. Veuillez faire une nouvelle demande.", 400)

    # Reset password and clear token
    with transaction.atomic():
        user.set_password(new_password)
        user.password_reset_token = None
        user.password_reset_token_expires = None
        user.save(update_fields=["password", "password_reset_token", "password_reset_token_expires"])

    # Send confirmation email
    subject = "Mot de passe réinitialisé - Gaboom Central"
    message_text = (
        f"Bonjour {user.username},\n\n"
        f"Votre mot de passe Gaboom Central a été réinitialisé avec succès.\n\n"
        f"Si vous n'avez pas effectué cette modification, veuillez contacter immédiatement notre équipe de support.\n\n"
        f"L'équipe Gaboom"
    )
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #10b981; text-align: center;">✅ Mot de passe réinitialisé</h2>
        <p>Bonjour <strong>{user.username}</strong>,</p>
        <p>Votre mot de passe Gaboom Central a été réinitialisé avec succès.</p>
        <p style="font-size: 12px; color: #666;">Si vous n'avez pas effectué cette modification, veuillez contacter immédiatement notre équipe de support à <a href="mailto:gaboom@programmer.net">gaboom@programmer.net</a>.</p>
        <hr style="border: 0; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <p style="font-size: 12px; color: #999; text-align: center;">&copy; Gaboom Central · Tous droits réservés</p>
    </div>
    """
    send_custom_email(subject, message_text, email, html_message=html_message)

    return _json_success({
        "message": "Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter avec votre nouveau mot de passe."
    })