import secrets
import string

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import (
    AccountRecoveryRequest,
    Borlette,
    LotteryAPIConfig,
    RecoveryStatus,
    User,
    UserRole,
)


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


def account_recovery(request: HttpRequest):
    """Page de demande de récupération de compte (Admin de Borlette)."""
    if request.method == "POST":
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
            "Demande envoyée avec succès. Notre équipe va traiter votre demande dans les plus brefs délais."
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
