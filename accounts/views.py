import secrets
import string
import uuid

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import (
    AccountRecoveryRequest,
    Borlette,
    LotteryAPIConfig,
    RecoveryStatus,
    User,
    UserRole,
    Agent,
    FinancialTransaction,
    GlobalPaymentSettings,
)
from accounts.mail_service import send_custom_email


@login_required
def superadmin_api_config(request: HttpRequest):
    if not request.user.is_superuser:
        return redirect("/admin/")

    config = LotteryAPIConfig.objects.first()
    has_key = bool(getattr(config, "api_key", "")) if config else False

    if request.method == "POST":
        api_url = (request.POST.get("api_url") or "").strip()
        api_key = (request.POST.get("api_key") or "").strip()
        is_active = (request.POST.get("is_active") or "") == "on"

        if not api_url:
            messages.error(request, "API URL requis")
            return redirect("/superadmin/api-config/")

        if config is None:
            if not api_key:
                messages.error(request, "API KEY requis")
                return redirect("/superadmin/api-config/")
            config = LotteryAPIConfig.objects.create(api_url=api_url, api_key=api_key, is_active=is_active)
        else:
            config.api_url = api_url
            if api_key:
                config.api_key = api_key
            config.is_active = is_active
            config.save(update_fields=["api_url", "api_key", "is_active", "updated_at"])

        messages.success(request, "Configuration API enregistrée")
        return redirect("/superadmin/api-config/")

    return render(
        request,
        "admin_portal/superadmin_api_config.html",
        {
            "config": config,
            "has_key": has_key,
        },
    )


def verify_email(request: HttpRequest, token: str):
    """Vérification de l'adresse email de l'administrateur ou de l'affilié."""
    user = get_object_or_404(User, email_verification_token=token)
    
    user.is_active = True
    user.is_email_verified = True
    user.email_verification_token = None
    user.save(update_fields=["is_active", "is_email_verified", "email_verification_token"])
    
    messages.success(
        request,
        "Votre adresse email a été confirmée avec succès ! Vous pouvez maintenant vous connecter à votre compte."
    )
    return render(request, "accounts/email_verified.html", {"user": user})


def reset_password(request: HttpRequest, token: str):
    """Réinitialisation du mot de passe avec le jeton reçu par email."""
    user = get_object_or_404(
        User, 
        password_reset_token=token,
        password_reset_token_expires__gt=timezone.now()
    )
    
    if request.method == "POST":
        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        
        if not new_password or new_password != confirm_password:
            messages.error(request, "Les mots de passe ne correspondent pas ou sont vides.")
            return render(request, "accounts/reset_password.html", {"token": token})
            
        user.set_password(new_password)
        user.password_reset_token = None
        user.password_reset_token_expires = None
        user.save()
        
        messages.success(request, "Votre mot de passe a été réinitialisé avec succès. Vous pouvez maintenant vous connecter.")
        return redirect("/portal/login/")
        
    return render(request, "accounts/reset_password.html", {"token": token})


def account_recovery(request: HttpRequest):
    """Page de demande de récupération de compte."""
    if request.method == "POST":
        action = request.POST.get("action", "")
        
        if action == "forgot_password":
            email = (request.POST.get("email") or "").strip()
            if not email:
                messages.error(request, "Adresse email requise")
                return redirect("account_recovery")
                
            users = User.objects.filter(email=email)
            if not users.exists():
                # We show success message anyway to prevent email enumeration
                messages.success(request, "Si l'adresse email existe, un lien de réinitialisation a été envoyé.")
                return redirect("account_recovery")
                
            # Pick first matching active/valid user
            user = users.first()
            token = uuid.uuid4().hex
            user.password_reset_token = token
            user.password_reset_token_expires = timezone.now() + timezone.timedelta(hours=2)
            user.save(update_fields=["password_reset_token", "password_reset_token_expires"])
            
            domain = request.get_host()
            protocol = "https" if request.is_secure() else "http"
            reset_url = f"{protocol}://{domain}/accounts/reset-password/{token}/"
            
            subject = "Réinitialisation de votre mot de passe Gaboom"
            message_text = f"Bonjour {user.username},\n\nVous avez demandé la réinitialisation de votre mot de passe. Veuillez cliquer sur le lien suivant dans les 2 prochaines heures :\n{reset_url}\n\nSi vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email."
            html_message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                <h2 style="color: #ea580c; text-align: center;">Réinitialisation de mot de passe</h2>
                <p>Bonjour <strong>{user.username}</strong>,</p>
                <p>Vous avez demandé à réinitialiser le mot de passe de votre compte Gaboom Central. Cliquez sur le bouton ci-dessous pour définir un nouveau mot de passe :</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" style="background-color: #ea580c; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Réinitialiser mon mot de passe</a>
                </div>
                <p style="font-size: 12px; color: #666;">Ce lien expirera dans 2 heures. Si le bouton ne fonctionne pas, copiez-collez le lien suivant dans votre navigateur :<br><a href="{reset_url}">{reset_url}</a></p>
                <hr style="border: 0; border-top: 1px solid #e0e0e0; margin: 20px 0;">
                <p style="font-size: 12px; color: #999; text-align: center;">&copy; Gaboom Central · Tous droits réservés</p>
            </div>
            """
            send_custom_email(subject, message_text, email, html_message=html_message)
            messages.success(request, "Un lien de réinitialisation a été envoyé à votre adresse email.")
            return redirect("account_recovery")
            
        elif action == "forgot_username":
            email = (request.POST.get("email") or "").strip()
            if not email:
                messages.error(request, "Adresse email requise")
                return redirect("account_recovery")
                
            users = User.objects.filter(email=email)
            if not users.exists():
                messages.success(request, "Si l'adresse email existe, les identifiants ont été envoyés.")
                return redirect("account_recovery")
                
            usernames = [u.username for u in users]
            usernames_str = ", ".join(usernames)
            
            subject = "Récupération de vos identifiants Gaboom"
            message_text = f"Bonjour,\n\nVous avez demandé à récupérer vos identifiants Gaboom Central. Les comptes associés à cet email sont :\n\n{usernames_str}\n\nL'équipe Gaboom"
            html_message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                <h2 style="color: #ea580c; text-align: center;">Récupération d'identifiants</h2>
                <p>Bonjour,</p>
                <p>Voici les noms d'utilisateurs associés à votre adresse email sur Gaboom Central :</p>
                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 16px; text-align: center; margin: 20px 0;">
                    <strong>{usernames_str}</strong>
                </div>
                <p>Vous pouvez maintenant vous connecter en utilisant l'un de ces identifiants.</p>
                <hr style="border: 0; border-top: 1px solid #e0e0e0; margin: 20px 0;">
                <p style="font-size: 12px; color: #999; text-align: center;">&copy; Gaboom Central · Tous droits réservés</p>
            </div>
            """
            send_custom_email(subject, message_text, email, html_message=html_message)
            messages.success(request, "Vos identifiants ont été envoyés à votre adresse email.")
            return redirect("account_recovery")
            
        else:
            # Demande de récupération manuelle
            username = (request.POST.get("username") or "").strip()
            phone = (request.POST.get("phone") or "").strip()
            message_text = (request.POST.get("message") or "").strip()

            if not username:
                messages.error(request, "Nom d'utilisateur requis")
                return redirect("account_recovery")

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                messages.error(request, "Ce compte n'existe pas dans notre système")
                return redirect("account_recovery")

            if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
                messages.error(request, "Seuls les administrateurs de Borlette peuvent utiliser cette fonction")
                return redirect("account_recovery")

            borlette = getattr(user, "borlette", None)

            AccountRecoveryRequest.objects.create(
                user=user,
                borlette=borlette,
                phone_number=phone,
                message=message_text,
            )

            messages.success(
                request,
                "Demande manuelle envoyée avec succès. Notre équipe va traiter votre demande dans les plus breves délais."
            )
            return redirect("account_recovery")

    return render(request, "accounts/account_recovery.html")



@login_required
def force_password_change(request: HttpRequest):
    """Page forcée de changement de mot de passe après connexion avec temp password."""
    if not request.user.must_change_password:
        return redirect("/portal/dashboard/")

    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            request.user.must_change_password = False
            request.user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, request.user)
            messages.success(request, "Votre mot de passe a été changé avec succès")
            return redirect("/portal/dashboard/")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, "accounts/force_password_change.html", {"form": form})


@login_required
def superadmin_recovery_requests(request: HttpRequest):
    """Vue Superadmin: liste des demandes de récupération de compte."""
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au superadmin")
        return redirect("/admin/")

    pending = AccountRecoveryRequest.objects.filter(status=RecoveryStatus.PENDING).select_related("user", "borlette")
    resolved = AccountRecoveryRequest.objects.filter(status=RecoveryStatus.RESOLVED).select_related("user", "borlette")[:20]

    return render(
        request,
        "accounts/superadmin_recovery_requests.html",
        {
            "pending": pending,
            "resolved": resolved,
        },
    )


@login_required
def superadmin_resolve_recovery(request: HttpRequest, recovery_id: str):
    """Vue Superadmin: résoudre une demande de récupération en générant un mot de passe temporaire."""
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au superadmin")
        return redirect("/admin/")

    try:
        recovery = AccountRecoveryRequest.objects.select_related("user").get(id=recovery_id)
    except AccountRecoveryRequest.DoesNotExist:
        messages.error(request, "Demande introuvable")
        return redirect("superadmin_recovery_requests")

    if recovery.status != RecoveryStatus.PENDING:
        messages.warning(request, "Cette demande a déjà été traitée")
        return redirect("superadmin_recovery_requests")

    if request.method == "POST":
        # Générer un mot de passe temporaire sécurisé
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        user = recovery.user
        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])

        recovery.status = RecoveryStatus.RESOLVED
        recovery.temp_password = temp_password
        recovery.temp_password_expires_at = timezone.now() + timezone.timedelta(hours=24)
        recovery.resolved_at = timezone.now()
        recovery.resolved_by = request.user
        recovery.save(update_fields=[
            "status", "temp_password", "temp_password_expires_at",
            "resolved_at", "resolved_by"
        ])

        messages.success(
            request,
            f"Mot de passe temporaire généré pour {user.username}. "
            f"Le client doit se connecter avec ce mot de passe et sera forcé de le changer."
        )
        return redirect("superadmin_recovery_requests")

    return render(
        request,
        "accounts/superadmin_resolve_recovery.html",
        {"recovery": recovery},
    )


@login_required
def superadmin_dashboard(request: HttpRequest):
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au superadmin")
        return redirect("/admin/")

    total_borlettes = Borlette.objects.count()
    total_active_admins = User.objects.filter(role=UserRole.ADMIN, is_active=True).count()
    total_suspended_admins = User.objects.filter(role=UserRole.ADMIN, is_active=False).count()
    total_agents = Agent.objects.count()
    total_tx = FinancialTransaction.objects.count()
    
    from django.db.models import Sum, Count, Q
    total_revenue = FinancialTransaction.objects.aggregate(total=Sum('total_amount'))['total'] or 0

    borlettes = Borlette.objects.select_related('user').annotate(
        num_agents=Count('agents')
    ).order_by('nom_borlette')

    search_query = request.GET.get('q', '').strip()
    if search_query:
        borlettes = borlettes.filter(
            Q(nom_borlette__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )

    return render(
        request,
        "accounts/superadmin_dashboard.html",
        {
            "total_borlettes": total_borlettes,
            "total_active_admins": total_active_admins,
            "total_suspended_admins": total_suspended_admins,
            "total_agents": total_agents,
            "total_tx": total_tx,
            "total_revenue": total_revenue,
            "borlettes": borlettes,
            "search_query": search_query,
        },
    )


@login_required
def superadmin_toggle_borlette_status(request: HttpRequest, borlette_id: int):
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au superadmin")
        return redirect("/admin/")

    borlette = get_object_or_404(Borlette, id=borlette_id)
    user = borlette.user
    
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    
    status_str = "réactivé" if user.is_active else "suspendu"
    messages.success(request, f"L'administrateur de la borlette '{borlette.nom_borlette}' a été {status_str} avec succès.")
    
    return redirect("superadmin_dashboard")


def admin_index_redirect(request: HttpRequest):
    if request.user.is_authenticated and (request.user.is_superuser or request.user.role == UserRole.SUPER_ADMIN):
        return redirect('superadmin_dashboard')
    from django.contrib import admin
    return admin.site.index(request)


@login_required
def superadmin_payment_config(request: HttpRequest):
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au superadmin")
        return redirect("/admin/")

    from decimal import Decimal
    config, _ = GlobalPaymentSettings.objects.get_or_create(id=1)

    if request.method == "POST":
        config.stripe_public_key = (request.POST.get("stripe_public_key") or "").strip()
        config.stripe_secret_key = (request.POST.get("stripe_secret_key") or "").strip()
        config.moncash_client_id = (request.POST.get("moncash_client_id") or "").strip()
        config.moncash_secret_key = (request.POST.get("moncash_secret_key") or "").strip()
        config.moncash_sandbox = (request.POST.get("moncash_sandbox") or "") == "on"
        config.automatic_payments_active = (request.POST.get("automatic_payments_active") or "") == "on"
        
        try:
            config.stripe_fee_percent = Decimal(request.POST.get("stripe_fee_percent", "3.5"))
            config.stripe_fee_fixed = Decimal(request.POST.get("stripe_fee_fixed", "0.30"))
            config.moncash_fee_percent = Decimal(request.POST.get("moncash_fee_percent", "1.0"))
            config.moncash_fee_fixed = Decimal(request.POST.get("moncash_fee_fixed", "0.0"))
        except Exception:
            pass

        config.save()
        messages.success(request, "Configuration de paiement mise à jour avec succès.")
        return redirect("superadmin_payment_config")

    return render(
        request,
        "accounts/superadmin_payment_config.html",
        {
            "config": config,
        },
    )


@login_required
def superadmin_smtp_config(request: HttpRequest):
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au superadmin")
        return redirect("/admin/")

    from accounts.models import SMTPSettings
    config = SMTPSettings.objects.filter(is_active=True).first()
    if not config:
        config = SMTPSettings.objects.create(
            smtp_host="mail.privateemail.com",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_use_tls=True,
            smtp_use_ssl=False,
            from_email="",
            is_active=True
        )

    if request.method == "POST":
        config.smtp_host = (request.POST.get("smtp_host") or "").strip()
        config.smtp_port = int(request.POST.get("smtp_port") or 587)
        config.smtp_username = (request.POST.get("smtp_username") or "").strip()
        
        password = request.POST.get("smtp_password", "").strip()
        if password:
            config.smtp_password = password
            
        config.smtp_use_tls = request.POST.get("smtp_use_tls") == "on"
        config.smtp_use_ssl = request.POST.get("smtp_use_ssl") == "on"
        config.from_email = (request.POST.get("from_email") or "").strip()
        config.save()
        
        messages.success(request, "Configuration SMTP mise à jour avec succès.")
        return redirect("superadmin_smtp_config")

    return render(
        request,
        "accounts/superadmin_smtp_config.html",
        {
            "config": config,
        },
    )


@login_required
def superadmin_email_marketing(request: HttpRequest):
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au superadmin")
        return redirect("/admin/")

    if request.method == "POST":
        subject = (request.POST.get("subject") or "").strip()
        message_body = (request.POST.get("message_body") or "").strip()
        target = request.POST.get("target", "all")
        is_html = request.POST.get("is_html") == "on"
        
        if not subject or not message_body:
            messages.error(request, "Le sujet et le corps du message sont obligatoires.")
            return redirect("superadmin_email_marketing")
            
        # Select users
        if target == "admins":
            users = User.objects.filter(role=UserRole.ADMIN, email__isnull=False)
        elif target == "affiliates":
            users = User.objects.filter(role=UserRole.AFFILIATE, email__isnull=False)
        else:
            users = User.objects.filter(role__in=[UserRole.ADMIN, UserRole.AFFILIATE], email__isnull=False)
            
        # Clean target emails
        recipient_list = [u.email for u in users if u.email and "@" in u.email]
        
        if not recipient_list:
            messages.warning(request, "Aucun destinataire trouvé pour ce segment.")
            return redirect("superadmin_email_marketing")
            
        # Send emails
        sent_count = 0
        from accounts.mail_service import send_custom_email
        for email in recipient_list:
            html = message_body if is_html else None
            text = message_body if not is_html else "Veuillez ouvrir cet email avec un client compatible HTML."
            
            success = send_custom_email(subject, text, email, html_message=html)
            if success:
                sent_count += 1
                
        messages.success(request, f"Campagne email envoyée avec succès à {sent_count} destinataire(s).")
        return redirect("superadmin_email_marketing")

    return render(request, "accounts/superadmin_email_marketing.html")


@login_required
def superadmin_reset_user_password(request: HttpRequest, user_id: int):
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au superadmin")
        return redirect("/admin/")

    user = get_object_or_404(User, id=user_id)
    
    if request.method == "POST":
        new_password = request.POST.get("new_password", "").strip()
        force_change = request.POST.get("force_change") == "on"
        
        if not new_password:
            # Generate a temporary one
            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for _ in range(12))
            
        user.set_password(new_password)
        if force_change:
            user.must_change_password = True
        user.save()
        
        messages.success(
            request, 
            f"Le mot de passe de '{user.username}' a été réinitialisé à : {new_password}"
        )
        
    return redirect("superadmin_dashboard")


def borlette_logo_view(request, borlette_id):
    from django.http import HttpResponse, Http404
    import base64
    import re
    import os
    from django.conf import settings as django_settings
    
    try:
        borlette = Borlette.objects.get(id=borlette_id)
    except Borlette.DoesNotExist:
        raise Http404("Borlette non trouvée")
        
    if borlette.logo_base64:
        base64_str = borlette.logo_base64.strip()
        if "," in base64_str:
            match = re.match(r"^data:([^;]+);base64,(.*)$", base64_str)
            if match:
                mime_type = match.group(1)
                base64_data = match.group(2)
            else:
                mime_type = "image/png"
                base64_data = base64_str.split(",")[-1]
        else:
            mime_type = "image/png"
            base64_data = base64_str
            
        try:
            binary_data = base64.b64decode(base64_data.strip())
            return HttpResponse(binary_data, content_type=mime_type)
        except Exception:
            pass
            
    # Serve fallback logo.png directly as binary response instead of redirecting
    fallback_path = os.path.join(django_settings.BASE_DIR, "static", "logo.png")
    if os.path.exists(fallback_path):
        try:
            with open(fallback_path, "rb") as f:
                return HttpResponse(f.read(), content_type="image/png")
        except Exception:
            pass
            
    raise Http404("Logo non trouvé")



