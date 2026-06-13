import json

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core import signing
from decimal import Decimal

from django.core.paginator import Paginator

from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from django.urls import reverse

from accounts.models import (
    AdminPaymentSettings,
    Agent,
    AgentStatus,
    Tirage,
    TirageCombiStats,
    TirageNumeroStats,
    TirageStatus,
    UserRole,
    MariageBlock,
)

from core.services.risk_management_service import RiskManagementService

from admin_portal.security import get_user_borlette, get_staff_user, staff_can
from accounts.audit import log_audit
from accounts.models import StaffUser, StaffUserRole, AuditAction

from .agent_forms import AgentCreateForm, AgentEditForm, AgentResetPasswordForm
from .forms import PortalAuthenticationForm, BorletteInfoForm
from .payment_forms import AdminPaymentSettingsForm
from .tirage_forms import TirageForm, TirageEditForm

User = get_user_model()


def _portal_guard(request):
    if request.user.is_superuser or request.user.role == UserRole.SUPER_ADMIN:
        return redirect("superadmin_dashboard")
    return None


def _require_admin(request):
    if request.user.role != UserRole.ADMIN:
        return redirect("/portal/dashboard/")
    borlette = get_user_borlette(request.user)
    if borlette is None:
        return redirect("/portal/dashboard/")
    return None


def _can_manage_team(user) -> bool:
    staff = get_staff_user(user)
    if not staff:
        return True
    return staff.role == StaffUserRole.MANAGER


@login_required
def team(request):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    if not _can_manage_team(request.user):
        return redirect("/portal/dashboard/")

    borlette = get_user_borlette(request.user)
    staff_qs = StaffUser.objects.filter(borlette=borlette).select_related("user").order_by("-created_at")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "create":
            username = (request.POST.get("username") or "").strip()
            password = (request.POST.get("password") or "").strip()
            role = (request.POST.get("role") or "").strip()

            if not username or not password or role not in {"manager", "finance", "operator"}:
                messages.error(request, "Champs invalides")
                return redirect("/portal/team/")

            if User.objects.filter(username=username).exists():
                messages.error(request, "Utilisateur existe déjà")
                return redirect("/portal/team/")

            perms = _preset_permissions(role)
            with transaction.atomic():
                u = User.objects.create_user(username=username, password=password)
                u.role = UserRole.ADMIN
                u.save(update_fields=["role"])

                staff = StaffUser.objects.create(
                    user=u,
                    borlette=borlette,
                    role=role,
                    is_active=True,
                    **perms,
                )

            log_audit(
                action=AuditAction.STAFF_CREATE,
                entity_type="StaffUser",
                entity_id=str(staff.id),
                borlette=borlette,
                actor_user=request.user,
                request=request,
                meta={"username": username, "role": role, **perms},
            )
            messages.success(request, "Membre ajouté")
            return redirect("/portal/team/")

        if action == "update":
            staff_id = request.POST.get("staff_id")
            staff = StaffUser.objects.filter(id=staff_id, borlette=borlette).select_related("user").first()
            if not staff:
                messages.error(request, "Membre introuvable")
                return redirect("/portal/team/")

            staff.role = (request.POST.get("role") or staff.role).strip()
            staff.can_view_dashboard = (request.POST.get("can_view_dashboard") or "") == "on"
            staff.can_manage_agents = (request.POST.get("can_manage_agents") or "") == "on"
            staff.can_manage_results = (request.POST.get("can_manage_results") or "") == "on"
            staff.can_view_finance = (request.POST.get("can_view_finance") or "") == "on"
            staff.save(
                update_fields=[
                    "role",
                    "can_view_dashboard",
                    "can_manage_agents",
                    "can_manage_results",
                    "can_view_finance",
                    "updated_at",
                ]
            )

            log_audit(
                action=AuditAction.STAFF_UPDATE,
                entity_type="StaffUser",
                entity_id=str(staff.id),
                borlette=borlette,
                actor_user=request.user,
                request=request,
                meta={
                    "username": staff.user.username,
                    "role": staff.role,
                    "can_view_dashboard": staff.can_view_dashboard,
                    "can_manage_agents": staff.can_manage_agents,
                    "can_manage_results": staff.can_manage_results,
                    "can_view_finance": staff.can_view_finance,
                },
            )
            messages.success(request, "Permissions mises à jour")
            return redirect("/portal/team/")

        if action == "toggle":
            staff_id = request.POST.get("staff_id")
            staff = StaffUser.objects.filter(id=staff_id, borlette=borlette).select_related("user").first()
            if not staff:
                messages.error(request, "Membre introuvable")
                return redirect("/portal/team/")

            staff.is_active = not staff.is_active
            staff.save(update_fields=["is_active", "updated_at"])

            log_audit(
                action=AuditAction.STAFF_TOGGLE_ACTIVE,
                entity_type="StaffUser",
                entity_id=str(staff.id),
                borlette=borlette,
                actor_user=request.user,
                request=request,
                meta={"username": staff.user.username, "is_active": staff.is_active},
            )
            messages.success(request, "Statut mis à jour")
            return redirect("/portal/team/")

        messages.error(request, "Action inconnue")
        return redirect("/portal/team/")

    return render(
        request,
        "admin_portal/team.html",
        {
            "staff_list": list(staff_qs),
            "members": list(staff_qs),
        },
    )


@login_required
def team_edit(request, staff_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    if request.method != "POST":
        return redirect("/portal/team/")

    if not _can_manage_team(request.user):
        return redirect("/portal/dashboard/")

    borlette = get_user_borlette(request.user)
    staff = StaffUser.objects.filter(id=staff_id, borlette=borlette).select_related("user").first()
    if not staff:
        messages.error(request, "Membre introuvable")
        return redirect("/portal/team/")

    role = (request.POST.get("role") or staff.role).strip()
    if role not in {"manager", "finance", "operator"}:
        messages.error(request, "Rôle invalide")
        return redirect("/portal/team/")

    staff.role = role
    staff.can_view_dashboard = (request.POST.get("can_view_dashboard") or "") == "on"
    staff.can_manage_agents = (request.POST.get("can_manage_agents") or "") == "on"
    staff.can_manage_results = (request.POST.get("can_manage_results") or "") == "on"
    staff.can_view_finance = (request.POST.get("can_view_finance") or "") == "on"
    staff.save(
        update_fields=[
            "role",
            "can_view_dashboard",
            "can_manage_agents",
            "can_manage_results",
            "can_view_finance",
            "updated_at",
        ]
    )

    log_audit(
        action=AuditAction.STAFF_UPDATE,
        entity_type="StaffUser",
        entity_id=str(staff.id),
        borlette=borlette,
        actor_user=request.user,
        request=request,
        meta={
            "username": staff.user.username,
            "role": staff.role,
            "can_view_dashboard": staff.can_view_dashboard,
            "can_manage_agents": staff.can_manage_agents,
            "can_manage_results": staff.can_manage_results,
            "can_view_finance": staff.can_view_finance,
        },
    )
    messages.success(request, "Membre mis à jour")
    return redirect("/portal/team/")


@login_required
def team_suspend(request, staff_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    if request.method != "POST":
        return redirect("/portal/team/")

    if not _can_manage_team(request.user):
        return redirect("/portal/dashboard/")

    borlette = get_user_borlette(request.user)
    staff = StaffUser.objects.filter(id=staff_id, borlette=borlette).select_related("user").first()
    if not staff:
        messages.error(request, "Membre introuvable")
        return redirect("/portal/team/")

    staff.is_active = not staff.is_active
    staff.save(update_fields=["is_active", "updated_at"])

    log_audit(
        action=AuditAction.STAFF_TOGGLE_ACTIVE,
        entity_type="StaffUser",
        entity_id=str(staff.id),
        borlette=borlette,
        actor_user=request.user,
        request=request,
        meta={"username": staff.user.username, "is_active": staff.is_active},
    )
    messages.success(request, "Statut mis à jour")
    return redirect("/portal/team/")


@login_required
def team_delete(request, staff_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    if request.method != "POST":
        return redirect("/portal/team/")

    if not _can_manage_team(request.user):
        return redirect("/portal/dashboard/")

    borlette = get_user_borlette(request.user)
    staff = StaffUser.objects.filter(id=staff_id, borlette=borlette).select_related("user").first()
    if not staff:
        messages.error(request, "Membre introuvable")
        return redirect("/portal/team/")

    username = staff.user.username
    with transaction.atomic():
        user_to_delete = staff.user
        staff.delete()
        user_to_delete.delete()

    log_audit(
        action=AuditAction.STAFF_UPDATE,
        entity_type="StaffUser",
        entity_id=str(staff_id),
        borlette=borlette,
        actor_user=request.user,
        request=request,
        meta={"username": username, "deleted": True},
    )
    messages.success(request, "Membre supprimé")
    return redirect("/portal/team/")


def _preset_permissions(role: str) -> dict:
    if role == StaffUserRole.MANAGER:
        return {
            "can_view_dashboard": True,
            "can_manage_agents": True,
            "can_manage_results": True,
            "can_view_finance": True,
        }
    if role == StaffUserRole.FINANCE:
        return {
            "can_view_dashboard": True,
            "can_manage_agents": False,
            "can_manage_results": False,
            "can_view_finance": True,
        }
    # operator
    return {
        "can_view_dashboard": True,
        "can_manage_agents": True,
        "can_manage_results": True,
        "can_view_finance": False,
    }


def _generate_agent_username(telephone: str) -> str:
    digits = "".join([c for c in (telephone or "") if c.isdigit()])
    base = f"agent_{digits}" if digits else "agent"

    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base}_{i}"
    return username


def portal_login(request):
    next_url = request.GET.get("next") or request.POST.get("next") or "/portal/dashboard/"

    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.role == UserRole.SUPER_ADMIN:
            return redirect("/admin/")
        if request.user.role == UserRole.PARTNER:
            return redirect("/partner/dashboard/")
        if request.user.role == UserRole.AFFILIATE:
            return redirect("/affiliate/dashboard/")
        return redirect(next_url)

    form = PortalAuthenticationForm(request=request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)

        if user.is_superuser or user.role == UserRole.SUPER_ADMIN:
            return redirect("superadmin_dashboard")

        # Redirect based on role
        if user.role == UserRole.PARTNER:
            return redirect("/partner/dashboard/")
        if user.role == UserRole.AFFILIATE:
            return redirect("/affiliate/dashboard/")

        # Sécurité redirect
        if not url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = "/portal/dashboard/"

        return redirect(next_url)

    return render(request, "admin_portal/login.html", {"form": form, "next": next_url})


def portal_auto_login(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.role == UserRole.SUPER_ADMIN:
            return redirect("/admin/")
        return redirect("/portal/dashboard/")

    token = request.GET.get("token")
    if not token:
        return redirect("/portal/login/")

    try:
        user_id = signing.TimestampSigner(salt="gaboom_signup").unsign(token, max_age=300)
    except Exception:
        return redirect("/portal/login/")

    user = User.objects.filter(id=user_id).first()
    if user is None:
        return redirect("/portal/login/")
    if user.is_superuser or user.role == UserRole.SUPER_ADMIN:
        return redirect("/portal/login/")

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("/portal/dashboard/")


@login_required
def index(request):
    guard = _portal_guard(request)
    if guard:
        return guard
    return redirect("/portal/dashboard/")


@login_required
def dashboard(request):
    guard = _portal_guard(request)
    if guard:
        return guard
    if not staff_can(request.user, "can_view_dashboard"):
        return redirect("/portal/rapports/")
    return render(request, "admin_portal/dashboard.html")


@login_required
def dashboard_data(request):
    """Endpoint JSON pour les données du dashboard - filtré par borlette"""
    guard = _portal_guard(request)
    if guard:
        return JsonResponse({"error": "unauthorized"}, status=403)

    guard2 = _require_admin(request)
    if guard2:
        return JsonResponse({"error": "unauthorized"}, status=403)

    if not staff_can(request.user, "can_view_dashboard"):
        return JsonResponse({"error": "unauthorized"}, status=403)

    borlette = get_user_borlette(request.user)
    range_param = request.GET.get("range", "today")

    now = timezone.now()
    today = now.date()

    if range_param == "7d":
        start_date = today - timezone.timedelta(days=7)
    elif range_param == "30d":
        start_date = today - timezone.timedelta(days=30)
    else:
        start_date = today

    # Tirages actifs de cette borlette
    tirages_actifs = Tirage.objects.filter(
        borlette=borlette,
        statut=TirageStatus.ACTIF
    ).order_by("heure_fermeture")

    # Agents de cette borlette
    agents = Agent.objects.filter(borlette=borlette).select_related("user")
    agents_total = agents.count()
    agents_online = sum(1 for a in agents if a.etat_connexion == "CONNECTE")

    # Stats risques (exposition) - agrégé depuis TirageNumeroStats
    total_exposition_boule = Decimal("0")
    boules_high_risk = []

    for tirage in tirages_actifs:
        stats = TirageNumeroStats.objects.filter(tirage=tirage)
        for s in stats:
            total_exposition_boule += s.mises_total
            if s.plafond_admin > 0:
                ratio = (s.mises_total / s.plafond_admin * 100) if s.plafond_admin else 0
                if ratio >= 70:
                    boules_high_risk.append({
                        "tirage": tirage.nom,
                        "numero": s.numero,
                        "ratio": float(ratio),
                        "mises": float(s.mises_total),
                        "plafond": float(s.plafond_admin),
                    })

    # KPIs basés sur les vrais tickets
    from agent_portal.models import Ticket, TicketStatus
    
    tickets_qs = Ticket.objects.filter(
        borlette=borlette,
        statut=TicketStatus.VALIDE,
        created_at__date__gte=start_date,
    )
    tickets_count = tickets_qs.count()
    tickets_agg = tickets_qs.aggregate(
        total_mises=models.Sum("total_mise"),
        total_gains=models.Sum("total_gain"),
    )
    chiffre_affaires = float(tickets_agg.get("total_mises") or 0)
    total_gains = float(tickets_agg.get("total_gains") or 0)
    profit_estime = chiffre_affaires - total_gains
    exposition = float(total_exposition_boule)

    # Alertes intelligentes
    alerts = []

    # Alerte: agents hors ligne
    agents_offline = agents_total - agents_online
    if agents_offline >= 2:
        alerts.append({
            "type": "warning",
            "message": f"{agents_offline} agents hors ligne",
            "detail": "Vérifiez leur connexion"
        })

    # Alerte: exposition élevée
    for risk in boules_high_risk[:3]:
        alerts.append({
            "type": "danger",
            "message": f"Boule {risk['numero']} exposition {risk['ratio']:.0f}%",
            "detail": f"Tirage {risk['tirage']}"
        })

    # Alerte: tirage ferme bientôt
    for tirage in tirages_actifs:
        if tirage.etat_ouverture == "OUVERT" and tirage.heure_fermeture:
            fermeture = timezone.datetime.combine(today, tirage.heure_fermeture)
            fermeture = timezone.make_aware(fermeture)
            diff = (fermeture - now).total_seconds() / 60
            if 0 < diff <= 10:
                alerts.append({
                    "type": "info",
                    "message": f"{tirage.nom} ferme dans {int(diff)} min",
                    "detail": f"Fermeture à {tirage.heure_fermeture.strftime('%H:%M') if tirage.heure_fermeture else '--:--'}"
                })

    # Tirages actifs pour la table
    active_draws = []
    for t in tirages_actifs:
        expo_tirage = TirageNumeroStats.objects.filter(tirage=t).aggregate(
            total=models.Sum("mises_total")
        )["total"] or Decimal("0")

        active_draws.append({
            "id": t.id,
            "nom": t.nom,
            "ouverture": t.heure_ouverture.strftime("%H:%M") if t.heure_ouverture else "--:--",
            "fermeture": t.heure_fermeture.strftime("%H:%M") if t.heure_fermeture else "--:--",
            "tirage": t.heure_tirage.strftime("%H:%M") if t.heure_tirage else "--:--",
            "statut": t.etat_ouverture,
            "exposition": float(expo_tirage),
        })

    # TODOs stratégiques
    todos = []
    if boules_high_risk:
        for r in boules_high_risk[:2]:
            todos.append(f"Vérifier plafond Boule {r['numero']} tirage {r['tirage']}")
    if agents_offline >= 2:
        todos.append(f"{agents_offline} agents hors ligne - vérifier connexion")
    for tirage in tirages_actifs:
        if tirage.etat_ouverture == "OUVERT" and tirage.heure_fermeture:
            fermeture = timezone.datetime.combine(today, tirage.heure_fermeture)
            fermeture = timezone.make_aware(fermeture)
            diff = (fermeture - now).total_seconds() / 60
            if 0 < diff <= 10:
                todos.append(f"{tirage.nom} ferme dans {int(diff)} min")

    # Chart data (simulé pour Phase 1)
    chart_labels = []
    chart_tickets = []
    chart_profit = []
    chart_loss = []

    for i in range(7):
        d = today - timezone.timedelta(days=6-i)
        chart_labels.append(d.strftime("%d/%m"))
        # Simuler données cohérentes
        base = 50 + (i * 10)
        chart_tickets.append(base + (i % 3) * 15)
        chart_profit.append(base * 0.15 * 1000)
        chart_loss.append(base * 0.05 * 1000)

    return JsonResponse({
        "kpis": {
            "tickets": tickets_count,
            "chiffre_affaires": chiffre_affaires,
            "profit": profit_estime,
            "exposition": exposition,
            "agents_online": agents_online,
            "agents_total": agents_total,
            "tirages_ouverts": sum(1 for t in tirages_actifs if t.etat_ouverture == "OUVERT"),
        },
        "charts": {
            "labels": chart_labels,
            "tickets": chart_tickets,
            "profit": chart_profit,
            "loss": chart_loss,
        },
        "alerts": alerts,
        "active_draws": active_draws,
        "todos": todos,
        "updated_at": now.strftime("%H:%M:%S"),
    })


@login_required
def information(request):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    borlette = request.user.borlette
    edit_mode = (request.GET.get("edit") or "").strip() == "1"
    form = BorletteInfoForm(request.POST or None, request.FILES or None, instance=borlette)

    # Get subscription data
    from accounts.models import Subscription
    from django.utils import timezone
    subscription = Subscription.objects.filter(
        user=request.user,
        borlette=borlette,
        is_active=True
    ).first()
    
    # Get agent count
    from accounts.models import Agent
    agent_count = Agent.objects.filter(borlette=borlette, statut="ACTIF").count()
    
    # Check if borlette has a promo code discount
    from accounts.models import FinancialTransaction, PromoCode
    first_transaction = FinancialTransaction.objects.filter(
        borlette=borlette,
        type="activation"
    ).first()
    
    has_promo_discount = False
    promo_code_used = None
    discount_amount = 0
    base_price = 12500
    discounted_price = 12500
    
    if first_transaction and first_transaction.promo_code:
        has_promo_discount = True
        promo_code_used = first_transaction.promo_code.code
        discount_amount = 2500  # Rabais activation
        discounted_price = base_price - discount_amount
    
    # Calculate amount due per agent (with or without promo discount)
    amount_due_per_agent = 1200 if has_promo_discount else 1250
    total_amount_due = agent_count * amount_due_per_agent
    
    # Calculate savings
    total_agent_savings = (1250 - amount_due_per_agent) * agent_count if has_promo_discount else 0
    total_savings = discount_amount + total_agent_savings

    if request.method == "POST":
        if "upload_payment_proof" in request.POST and request.FILES.get("payment_proof"):
            # Handle payment proof upload
            if subscription:
                subscription.payment_proof = request.FILES["payment_proof"]
                subscription.save()
                messages.success(request, "Preuve de paiement envoyée avec succès.")
            else:
                messages.error(request, "Aucun abonnement actif trouvé.")
            return redirect("admin_portal:information")
        elif form.is_valid():
            form.save()
            # Sync mariage gratuit → AdminPaymentSettings (source unique de vérité)
            _borlette = request.user.borlette
            _pay, _ = AdminPaymentSettings.objects.get_or_create(borlette=_borlette)
            _pay.mariage_gratuit_actif = _borlette.mariage_gratuit_actif
            _pay.mariage_gratuit_montant_fixe = _borlette.mariage_gratuit_montant
            _pay.save(update_fields=["mariage_gratuit_actif", "mariage_gratuit_montant_fixe", "updated_at"])
            messages.success(request, "Informations mises à jour.")
            return redirect("admin_portal:information")

    return render(request, "admin_portal/information.html", {
        "form": form,
        "edit_mode": edit_mode,
        "subscription": subscription,
        "agent_count": agent_count,
        "amount_due_per_agent": amount_due_per_agent,
        "total_amount_due": total_amount_due,
        "today": timezone.now().date(),
        "has_promo_discount": has_promo_discount,
        "promo_code_used": promo_code_used,
        "discount_amount": discount_amount,
        "base_price": base_price,
        "discounted_price": discounted_price,
        "total_agent_savings": total_agent_savings,
        "total_savings": total_savings,
    })


@login_required
def audit_logs_list(request):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    from accounts.models import AuditAction, AuditLog

    borlette = request.user.borlette

    qs = (
        AuditLog.objects.filter(borlette=borlette)
        .select_related("actor_user", "actor_agent")
        .order_by("-created_at")
    )

    action = (request.GET.get("action") or "").strip()
    entity_type = (request.GET.get("entity_type") or "").strip()
    entity_id = (request.GET.get("entity_id") or "").strip()
    actor = (request.GET.get("actor") or "").strip()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()

    if action:
        qs = qs.filter(action=action)
    if entity_type:
        qs = qs.filter(entity_type__iexact=entity_type)
    if entity_id:
        qs = qs.filter(entity_id__icontains=entity_id)
    if actor:
        qs = qs.filter(
            models.Q(actor_user__username__icontains=actor)
            | models.Q(actor_agent__nom__icontains=actor)
        )
    if date_from:
        try:
            df = timezone.datetime.strptime(date_from, "%Y-%m-%d").date()
            qs = qs.filter(created_at__date__gte=df)
        except Exception:
            pass
    if date_to:
        try:
            dt = timezone.datetime.strptime(date_to, "%Y-%m-%d").date()
            qs = qs.filter(created_at__date__lte=dt)
        except Exception:
            pass

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()
    querystring_prefix = f"{querystring}&" if querystring else ""

    return render(
        request,
        "admin_portal/audit_logs_list.html",
        {
            "page_obj": page_obj,
            "actions": AuditAction.choices,
            "filters": {
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "actor": actor,
                "date_from": date_from,
                "date_to": date_to,
            },
            "querystring_prefix": querystring_prefix,
        },
    )


@login_required
def agents_list(request):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    agents = (
        Agent.objects.filter(borlette=request.user.borlette)
        .select_related("user")
        .order_by("nom")
    )
    return render(request, "admin_portal/agents_list.html", {"agents": agents})


@login_required
@transaction.atomic
def agent_create(request):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    if request.method == "POST":
        form = AgentCreateForm(request.POST)
        if form.is_valid():
            username = _generate_agent_username(form.cleaned_data["telephone"])

            user = User(
                username=username,
                role=UserRole.AGENT,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )
            user.set_password(form.cleaned_data["mot_de_passe"])
            user.save()

            agent = Agent.objects.create(
                user=user,
                borlette=request.user.borlette,
                nom=form.cleaned_data["nom"],
                telephone=form.cleaned_data["telephone"],
                zone=form.cleaned_data["zone"],
                commission=form.cleaned_data["commission"],
                statut=AgentStatus.ACTIF,
            )

            return redirect("admin_portal:agent_detail", agent_id=agent.id)
    else:
        form = AgentCreateForm()

    return render(
        request,
        "admin_portal/agent_form.html",
        {
            "form": form,
            "page_title": "Nouvel agent",
            "page_meta": "Création",
        },
    )


@login_required
def agent_detail(request, agent_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    agent = Agent.objects.select_related("user", "borlette").get(id=agent_id, borlette=request.user.borlette)
    return render(request, "admin_portal/agent_detail.html", {"agent": agent})


@login_required
@transaction.atomic
def agent_edit(request, agent_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    agent = Agent.objects.select_related("user").get(id=agent_id, borlette=request.user.borlette)

    if request.method == "POST":
        form = AgentEditForm(request.POST, instance=agent)
        if form.is_valid():
            form.save()
            return redirect("admin_portal:agent_detail", agent_id=agent.id)
    else:
        form = AgentEditForm(instance=agent)

    return render(
        request,
        "admin_portal/agent_form.html",
        {
            "form": form,
            "page_title": "Modifier agent",
            "page_meta": agent.nom,
        },
    )


@login_required
@transaction.atomic
def agent_suspend(request, agent_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    if request.method != "POST":
        return redirect("admin_portal:agent_detail", agent_id=agent_id)

    agent = Agent.objects.select_related("user").get(id=agent_id, borlette=request.user.borlette)
    if agent.statut == AgentStatus.ACTIF:
        agent.statut = AgentStatus.SUSPENDU
        agent.user.is_active = False
    else:
        agent.statut = AgentStatus.ACTIF
        agent.user.is_active = True

    agent.user.save()
    agent.save()

    return redirect("admin_portal:agents")


@login_required
@transaction.atomic
def agent_delete(request, agent_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    agent = Agent.objects.select_related("user").get(id=agent_id, borlette=request.user.borlette)

    if request.method == "POST":
        user = agent.user
        agent.delete()
        user.delete()
        return redirect("admin_portal:agents")

    return render(request, "admin_portal/agent_confirm_delete.html", {"agent": agent})


@login_required
@transaction.atomic
def agent_reset_password(request, agent_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    agent = Agent.objects.select_related("user").get(id=agent_id, borlette=request.user.borlette)

    if request.method == "POST":
        form = AgentResetPasswordForm(request.POST)
        if form.is_valid():
            agent.user.set_password(form.cleaned_data["mot_de_passe"])
            agent.user.save()
            return redirect("admin_portal:agent_detail", agent_id=agent.id)
    else:
        form = AgentResetPasswordForm()

    return render(request, "admin_portal/agent_reset_password.html", {"form": form, "agent": agent})


@login_required
def tirages_list(request):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    from .tirage_results_service import TirageResultsStatusService
    from accounts.models import AdminTiragePreference
    
    tirages = (
        Tirage.objects.filter(borlette=request.user.borlette)
        .order_by("ordre_affichage", "heure_tirage", "nom")
    )
    
    # Get results status for each tirage
    service = TirageResultsStatusService(request.user.borlette)
    statuses = {s.tirage_id: s for s in service.get_all_statuses()}
    
    # Get admin activation preferences
    prefs = {
        pref.tirage_id: pref.actif
        for pref in AdminTiragePreference.objects.filter(user=request.user)
    }
    
    # Attach status and preference to each tirage
    tirages_with_status = []
    for t in tirages:
        status = statuses.get(t.id)
        t.results_status = status
        t.actif_pour_admin = prefs.get(t.id, True)  # Default to True if no preference
        tirages_with_status.append(t)

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

    tirages_with_status.sort(key=sort_key)
    
    return render(request, "admin_portal/tirages_list.html", {"tirages": tirages_with_status})


@login_required
@transaction.atomic
def tirage_create(request):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    if request.method == "POST":
        form = TirageForm(request.POST)
        if form.is_valid():
            tirage = form.save(commit=False)
            tirage.borlette = request.user.borlette
            tirage.full_clean()
            tirage.save()
            return redirect("admin_portal:tirages")
    else:
        form = TirageForm()

    return render(
        request,
        "admin_portal/tirage_form.html",
        {
            "form": form,
            "page_title": "Nouveau tirage",
            "page_meta": "Création",
        },
    )


@login_required
@transaction.atomic
def tirage_edit(request, tirage_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    tirage = Tirage.objects.get(id=tirage_id, borlette=request.user.borlette)

    if request.method == "POST":
        form = TirageEditForm(request.POST, instance=tirage, user=request.user)
        if form.is_valid():
            t = form.save(commit=False)
            t.borlette = request.user.borlette
            t.full_clean()
            t.save()
            return redirect("admin_portal:tirages")
        else:
            # Log errors for debugging
            print("Form errors:", form.errors)
    else:
        form = TirageEditForm(instance=tirage, user=request.user)

    return render(
        request,
        "admin_portal/tirage_form.html",
        {
            "form": form,
            "page_title": "Modifier tirage",
            "page_meta": tirage.nom,
            "is_edit": True,
            "actif_pour_admin": form.fields['actif_pour_admin'].initial if 'actif_pour_admin' in form.fields else True,
        },
    )


@login_required
@transaction.atomic
def tirage_suspend(request, tirage_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    if request.method != "POST":
        return redirect("admin_portal:tirages")

    tirage = Tirage.objects.get(id=tirage_id, borlette=request.user.borlette)
    if tirage.statut == TirageStatus.ACTIF:
        tirage.statut = TirageStatus.SUSPENDU
    else:
        tirage.statut = TirageStatus.ACTIF
    try:
        tirage.full_clean()
        tirage.save()
    except ValidationError as e:
        msg = e.messages[0] if getattr(e, "messages", None) else str(e)
        messages.error(request, msg)

    return redirect("admin_portal:tirages")


@login_required
@transaction.atomic
def tirage_delete(request, tirage_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    tirage = Tirage.objects.get(id=tirage_id, borlette=request.user.borlette)

    if getattr(tirage, "is_default", False):
        messages.error(request, "Impossible de supprimer un tirage par défaut.")
        return redirect("admin_portal:tirages")

    if request.method == "POST":
        tirage.delete()
        return redirect("admin_portal:tirages")

    return render(request, "admin_portal/tirage_confirm_delete.html", {"tirage": tirage})


@login_required
def rapports(request):
    guard = _portal_guard(request)
    if guard:
        return guard
    return render(request, "admin_portal/rapports.html")


@login_required
def parametres(request):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    settings_obj, _ = AdminPaymentSettings.objects.get_or_create(borlette=request.user.borlette)

    saved = request.GET.get("saved") == "1"
    edit = request.GET.get("edit") == "1"

    if request.method == "POST":
        form = AdminPaymentSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.borlette = request.user.borlette
            obj.save()
            # Sync mariage gratuit → Borlette (cohérence avec /information/)
            _borlette = request.user.borlette
            _borlette.mariage_gratuit_actif = obj.mariage_gratuit_actif
            _borlette.mariage_gratuit_montant = obj.mariage_gratuit_montant_fixe
            _borlette.save(update_fields=["mariage_gratuit_actif", "mariage_gratuit_montant"])

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"success": True})
            
            return redirect(f"{reverse('admin_portal:parametres')}?saved=1")
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
    else:
        form = AdminPaymentSettingsForm(instance=settings_obj)

    return render(
        request,
        "admin_portal/parametres.html",
        {"payment_form": form, "payment_settings": settings_obj, "saved": saved, "edit": True},  # Always edit=True for JS toggle
    )


@login_required
@transaction.atomic
def tirage_risques(request, tirage_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    tirage = Tirage.objects.get(id=tirage_id, borlette=request.user.borlette)
    jeu = (request.GET.get("jeu") or "boule").strip().lower()
    if jeu not in ("boule", "mariage", "loto3", "loto4", "loto5"):
        jeu = "boule"

    message = ""

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        key = (request.POST.get("key") or "").strip()

        try:
            if action == "toggle_bloque_admin":
                if jeu == "boule":
                    numero = key
                    obj = TirageNumeroStats.objects.select_for_update().filter(tirage=tirage, numero=numero).first()
                    current = bool(obj.bloque_admin) if obj else False
                    RiskManagementService.set_numero_admin_controls(
                        tirage=tirage, numero=numero, plafond_admin=None, bloque_admin=(not current)
                    )
                    # Synchroniser les mariages dérivés après modification d'une boule
                    RiskManagementService.sync_mariage_derived(tirage=tirage)
                else:
                    valeur = key
                    obj = (
                        TirageCombiStats.objects.select_for_update()
                        .filter(tirage=tirage, jeu_type=jeu, valeur=valeur)
                        .first()
                    )
                    current = bool(obj.bloque_admin) if obj else False
                    RiskManagementService.set_combi_admin_controls(
                        tirage=tirage, jeu_type=jeu, valeur=valeur, plafond_admin=None, bloque_admin=(not current)
                    )
                message = "Mise à jour effectuée."

            elif action == "set_plafond":
                plafond_raw = request.POST.get("plafond_admin")
                if jeu == "boule":
                    numero = key
                    RiskManagementService.set_numero_admin_controls(
                        tirage=tirage, numero=numero, plafond_admin=Decimal(str(plafond_raw or 0)), bloque_admin=None
                    )
                else:
                    valeur = key
                    RiskManagementService.set_combi_admin_controls(
                        tirage=tirage, jeu_type=jeu, valeur=valeur, plafond_admin=Decimal(str(plafond_raw or 0)), bloque_admin=None
                    )
                message = "Plafond mis à jour."

            elif action == "add_combi" and jeu in ("mariage", "loto3", "loto4", "loto5"):
                if jeu == "mariage":
                    # Mariage: format AxB (2 numéros 00-99)
                    num_a = (request.POST.get("num_a") or "").strip().zfill(2)
                    num_b = (request.POST.get("num_b") or "").strip().zfill(2)
                    if not (num_a.isdigit() and num_b.isdigit() and len(num_a) == 2 and len(num_b) == 2):
                        raise ValidationError("Numéros invalides (00-99)")
                    if num_a == num_b:
                        raise ValidationError("Les deux numéros doivent être différents")
                    valeur = f"{num_a}x{num_b}"
                else:
                    # Loto3/4/5: format direct (ex: 456, 2543, 45674)
                    valeur = (request.POST.get("valeur") or "").strip()
                    expected_len = {"loto3": 3, "loto4": 4, "loto5": 5}[jeu]
                    if not (valeur.isdigit() and len(valeur) == expected_len):
                        raise ValidationError(f"{expected_len} chiffres requis (0-9)")
                RiskManagementService.set_combi_admin_controls(
                    tirage=tirage, jeu_type=jeu, valeur=valeur, plafond_admin=None, bloque_admin=True
                )
                message = f"Blocage {jeu} {valeur} ajouté."

        except ValidationError:
            message = "Action invalide."
        except Exception:
            message = "Erreur lors de la mise à jour."

        return redirect(f"{reverse('admin_portal:tirage_risques', args=[tirage.id])}?jeu={jeu}")

    rows: list[dict] = []
    empty_hint = ""

    if jeu == "boule":
        RiskManagementService.ensure_numero_stats_rows(tirage=tirage)
        stats = TirageNumeroStats.objects.filter(tirage=tirage).order_by("numero")
        for s in stats:
            rows.append(
                {
                    "type": "Boule",
                    "valeur": s.numero,
                    "key": s.numero,
                    "mises_total": s.mises_total,
                    "plafond_admin": s.plafond_admin,
                    "bloque_auto": s.bloque_auto,
                    "bloque_admin": s.bloque_admin,
                }
            )
    else:
        # Pour mariage, synchroniser d'abord les dérivés
        if jeu == "mariage":
            RiskManagementService.sync_mariage_derived(tirage=tirage)

        stats = TirageCombiStats.objects.filter(tirage=tirage, jeu_type=jeu).order_by("valeur")
        for s in stats:
            # Déterminer la source du blocage pour l'affichage
            source = None
            if jeu == "mariage":
                if s.bloque_admin and s.bloque_derived:
                    source = "admin+dérivé"
                elif s.bloque_admin:
                    source = "admin"
                elif s.bloque_derived:
                    source = "dérivé"

            # Pour mariage: afficher seulement si bloqué (admin ou dérivé) ou a des mises
            if jeu == "mariage" and not (s.bloque_admin or s.bloque_derived or s.bloque_auto or s.mises_total > 0):
                continue

            rows.append(
                {
                    "type": jeu,
                    "valeur": s.valeur,
                    "key": s.valeur,
                    "mises_total": s.mises_total,
                    "plafond_admin": s.plafond_admin,
                    "bloque_auto": s.bloque_auto,
                    "bloque_admin": s.bloque_admin,
                    "bloque_derived": getattr(s, "bloque_derived", False),
                    "source": source,
                }
            )
        if not rows:
            empty_hint = "Aucune combinaison enregistrée pour ce tirage/jeu pour l’instant."

    return render(
        request,
        "admin_portal/tirage_risques.html",
        {
            "tirage": tirage,
            "jeu": jeu,
            "rows": rows,
            "message": message,
            "empty_hint": empty_hint,
        },
    )


@login_required
@transaction.atomic
def tirage_boules(request, tirage_id: int):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    # Strict isolation
    tirage = Tirage.objects.get(id=tirage_id, borlette=request.user.borlette)

    if request.method == "POST":
        if request.content_type and "application/json" in request.content_type:
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except Exception:
                return JsonResponse({"success": False, "error": "payload_invalide"}, status=400)
        else:
            payload = request.POST

        action = (payload.get("action") or "").strip()
        numero = (payload.get("numero") or "").strip()
        plafond_raw = payload.get("plafond_admin")

        try:
            RiskManagementService.ensure_numero_stats_rows(tirage=tirage)

            if action == "toggle_bloque":
                obj = TirageNumeroStats.objects.filter(tirage=tirage, numero=numero).first()
                current = bool(obj.bloque_admin) if obj else False
                updated = RiskManagementService.set_numero_admin_controls(
                    tirage=tirage, numero=numero, plafond_admin=None, bloque_admin=(not current)
                )
                return JsonResponse(
                    {
                        "success": True,
                        "numero": numero,
                        "bloque_admin": updated.bloque_admin,
                        "bloque_auto": updated.bloque_auto,
                        "plafond_admin": str(updated.plafond_admin),
                        "mises_total": str(updated.mises_total),
                    }
                )

            if action == "update_plafond":
                updated = RiskManagementService.set_numero_admin_controls(
                    tirage=tirage,
                    numero=numero,
                    plafond_admin=Decimal(str(plafond_raw or 0)),
                    bloque_admin=None,
                )
                return JsonResponse(
                    {
                        "success": True,
                        "numero": numero,
                        "bloque_admin": updated.bloque_admin,
                        "bloque_auto": updated.bloque_auto,
                        "plafond_admin": str(updated.plafond_admin),
                        "mises_total": str(updated.mises_total),
                    }
                )

            return JsonResponse({"success": False, "error": "action_invalide"}, status=400)
        except Exception:
            return JsonResponse({"success": False, "error": "server_error"}, status=400)

    stats = RiskManagementService.get_stats(tirage_id=tirage.id, jeu="boule", borlette_id=request.user.borlette.id)

    return render(
        request,
        "admin_portal/tirage_boules.html",
        {
            "tirage": stats["tirage"],
            "rows": stats["rows"],
        },
    )


def _tirage_combis_page(request, tirage_id: int, jeu: str, title: str):
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    tirage = Tirage.objects.get(id=tirage_id, borlette=request.user.borlette)
    jeu = (jeu or "").strip().lower()

    if request.method == "POST":
        if request.content_type and "application/json" in request.content_type:
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except Exception:
                payload = {}
        else:
            payload = request.POST

        action = (payload.get("action") or "").strip()
        valeur = (payload.get("valeur") or "").strip()
        plafond_raw = payload.get("plafond_admin")

        try:
            if action == "toggle_bloque":
                obj = TirageCombiStats.objects.filter(tirage=tirage, jeu_type=jeu, valeur=valeur).first()
                current = bool(obj.bloque_admin) if obj else False
                updated = RiskManagementService.set_combi_admin_controls(
                    tirage=tirage, jeu_type=jeu, valeur=valeur, plafond_admin=None, bloque_admin=(not current)
                )
                return JsonResponse(
                    {
                        "success": True,
                        "valeur": valeur,
                        "bloque_admin": updated.bloque_admin,
                        "bloque_auto": updated.bloque_auto,
                        "plafond_admin": str(updated.plafond_admin),
                        "mises_total": str(updated.mises_total),
                    }
                )

            if action == "update_plafond":
                updated = RiskManagementService.set_combi_admin_controls(
                    tirage=tirage,
                    jeu_type=jeu,
                    valeur=valeur,
                    plafond_admin=Decimal(str(plafond_raw or 0)),
                    bloque_admin=None,
                )
                return JsonResponse(
                    {
                        "success": True,
                        "valeur": valeur,
                        "bloque_admin": updated.bloque_admin,
                        "bloque_auto": updated.bloque_auto,
                        "plafond_admin": str(updated.plafond_admin),
                        "mises_total": str(updated.mises_total),
                    }
                )

            return JsonResponse({"success": False, "error": "action_invalide"}, status=400)
        except Exception:
            return JsonResponse({"success": False, "error": "server_error"}, status=400)

    stats = RiskManagementService.get_stats(
        tirage_id=tirage.id,
        jeu=jeu,
        borlette_id=request.user.borlette.id,
    )

    empty_hint = ""
    if not stats.get("rows"):
        empty_hint = "Aucune combinaison enregistrée pour ce tirage/jeu pour l’instant."

    return render(
        request,
        "admin_portal/tirage_combis.html",
        {
            "tirage": stats["tirage"],
            "rows": stats["rows"],
            "title": title,
            "empty_hint": empty_hint,
        },
    )


@login_required
@transaction.atomic
def tirage_mariages(request, tirage_id: int):
    return _tirage_combis_page(request, tirage_id, "mariage", "Mariages")


@login_required
@transaction.atomic
def tirage_loto3(request, tirage_id: int):
    return _tirage_combis_page(request, tirage_id, "loto3", "Loto3")


@login_required
@transaction.atomic
def tirage_loto4(request, tirage_id: int):
    return _tirage_combis_page(request, tirage_id, "loto4", "Loto4")


@login_required
@transaction.atomic
def tirage_loto5(request, tirage_id: int):
    return _tirage_combis_page(request, tirage_id, "loto5", "Loto5")


@login_required
@transaction.atomic
def tirage_resultats(request, tirage_id: int):
    """Page de saisie des résultats d'un tirage."""
    from accounts.models import Resultat
    from core.services.result_calculation_service import ResultCalculationService
    from .resultat_forms import ResultatForm
    from .tirage_results_service import TirageResultsStatusService

    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    tirage = Tirage.objects.filter(id=tirage_id, borlette=request.user.borlette).first()
    if not tirage:
        return redirect("admin_portal:tirages")
    
    # Get results status for this tirage
    service = TirageResultsStatusService(request.user.borlette)
    results_status = service._get_status(tirage)

    # Vérifier si résultat existe déjà pour cette session
    existing_result = Resultat.objects.filter(
        tirage=tirage,
        session_key=tirage.session_key,
    ).first()

    is_open = tirage.etat_ouverture == "OUVERT"
    calculation_stats = None
    errors = []

    if request.method == "POST" and not is_open:
        form = ResultatForm(request.POST)
        if form.is_valid():
            try:
                # Créer ou mettre à jour le résultat
                if existing_result:
                    existing_result.lot1 = form.cleaned_data["lot1"]
                    existing_result.lot2 = form.cleaned_data["lot2"]
                    existing_result.lot3 = form.cleaned_data["lot3"]
                    existing_result.chiffre_loto3 = form.cleaned_data["chiffre_loto3"]
                    existing_result.date = timezone.localdate()
                    existing_result.locked = False
                    existing_result.computed_at = None
                    existing_result.save()
                    resultat = existing_result
                else:
                    resultat = Resultat.objects.create(
                        tirage=tirage,
                        session_key=tirage.session_key,
                        date=timezone.localdate(),
                        lot1=form.cleaned_data["lot1"],
                        lot2=form.cleaned_data["lot2"],
                        lot3=form.cleaned_data["lot3"],
                        chiffre_loto3=form.cleaned_data["chiffre_loto3"],
                    )

                # Lancer le calcul des gains
                calculation_stats = ResultCalculationService.calculate_gains(
                    tirage=tirage,
                    resultat=resultat,
                )

                # Recharger le résultat
                existing_result = resultat

            except Exception as e:
                errors.append(str(e))
    else:
        initial = {}
        if existing_result:
            initial = {
                "lot1": existing_result.lot1,
                "lot2": existing_result.lot2,
                "lot3": existing_result.lot3,
                "chiffre_loto3": existing_result.chiffre_loto3,
            }
        form = ResultatForm(initial=initial)

    return render(
        request,
        "admin_portal/tirage_resultats.html",
        {
            "tirage": tirage,
            "form": form,
            "is_open": is_open,
            "existing_result": existing_result,
            "calculation_stats": calculation_stats,
            "errors": errors,
            "results_status": results_status,
        },
    )


@login_required
def agent_payout(request, agent_id: int):
    """Paiement d'un agent."""
    from core.services.agent_commission_service import AgentCommissionService
    from .resultat_forms import AgentPayoutForm

    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    agent = Agent.objects.filter(id=agent_id, borlette=request.user.borlette).first()
    if not agent:
        return redirect("admin_portal:agents")

    balance = AgentCommissionService.get_agent_balance(agent=agent)
    payout_created = None
    errors = []

    if request.method == "POST":
        form = AgentPayoutForm(request.POST)
        if form.is_valid():
            try:
                payout_created = AgentCommissionService.create_payout(
                    agent=agent,
                    amount=form.cleaned_data["amount"],
                    created_by=request.user,
                    note=form.cleaned_data.get("note", ""),
                )

                from accounts.audit import log_audit
                from accounts.models import AuditAction
                log_audit(
                    action=AuditAction.AGENT_COMMISSION_PAYOUT,
                    entity_type="Agent",
                    entity_id=str(agent.id),
                    borlette=request.user.borlette,
                    actor_user=request.user,
                    request=request,
                    meta={
                        "paid_agent_id": agent.id,
                        "paid_agent_nom": agent.nom,
                        "payout_id": str(payout_created.id),
                        "amount": float(payout_created.amount),
                        "note": payout_created.note,
                    },
                )
                # Recalculer le solde après paiement
                balance = AgentCommissionService.get_agent_balance(agent=agent)
            except ValueError as e:
                errors.append(str(e))
    else:
        form = AgentPayoutForm(initial={"amount": balance["solde"]})

    payouts = AgentCommissionService.get_payout_history(agent=agent, limit=20)

    return render(
        request,
        "admin_portal/agent_payout.html",
        {
            "agent": agent,
            "form": form,
            "balance": balance,
            "payouts": payouts,
            "payout_created": payout_created,
            "errors": errors,
        },
    )


def agent_cashbox_withdraw(request, agent_id: int):
    """Retrait de la caisse d'un agent."""
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    agent = Agent.objects.filter(id=agent_id, borlette=request.user.borlette).first()
    if not agent:
        return redirect("admin_portal:agents")

    from agent_portal.models import AgentCashboxEntry, CashboxEntryType
    from django.utils import timezone

    current_balance = agent.solde_caisse_calculé
    half_balance = current_balance / 2
    withdrawal_amount = None
    errors = []

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        custom_amount = request.POST.get("custom_amount", "").strip()
        keep_amount_raw = request.POST.get("keep_amount", "").strip()
        note = request.POST.get("note", "")

        try:
            if action == "half":
                withdrawal_amount = current_balance / 2
            elif action == "custom":
                if not custom_amount:
                    errors.append("Veuillez entrer un montant à retirer")
                else:
                    withdrawal_amount = Decimal(str(custom_amount))
            elif action == "keep":
                keep_amount = Decimal(str(keep_amount_raw)) if keep_amount_raw else Decimal("0")
                withdrawal_amount = current_balance - keep_amount
                if withdrawal_amount < 0:
                    errors.append("Le montant à garder ne peut pas dépasser le solde actuel")
                    withdrawal_amount = None
            else:
                errors.append("Action invalide")

            if withdrawal_amount and withdrawal_amount > 0 and withdrawal_amount <= current_balance:
                # Stocker le retrait en négatif (convention WITHDRAWAL = débit)
                AgentCashboxEntry.objects.create(
                    agent=agent,
                    borlette=agent.borlette,
                    entry_type=CashboxEntryType.WITHDRAWAL,
                    amount=-withdrawal_amount,
                    description=f"Retrait caisse - {note}" if note else "Retrait caisse",
                )

                new_balance = agent.solde_caisse_calculé

                from accounts.audit import log_audit
                from accounts.models import AuditAction
                log_audit(
                    action=AuditAction.AGENT_CASHBOX_WITHDRAWAL,
                    entity_type="Agent",
                    entity_id=str(agent.id),
                    borlette=request.user.borlette,
                    actor_user=request.user,
                    request=request,
                    meta={
                        "agent_id": agent.id,
                        "agent_nom": agent.nom,
                        "withdrawal_amount": float(withdrawal_amount),
                        "previous_balance": float(current_balance),
                        "new_balance": float(new_balance),
                        "note": note,
                    },
                )

                messages.success(request, f"Retrait de {withdrawal_amount} G effectué avec succès")
                return redirect("admin_portal:agents")
            elif withdrawal_amount and withdrawal_amount > current_balance:
                errors.append("Le montant du retrait ne peut pas dépasser le solde actuel")
        except Exception as e:
            errors.append(f"Erreur lors du retrait: {str(e)}")

    return render(
        request,
        "admin_portal/agent_cashbox_withdraw.html",
        {
            "agent": agent,
            "current_balance": current_balance,
            "half_balance": half_balance,
            "errors": errors,
        },
    )


def agent_cashbox_replenish(request, agent_id: int):
    """Réapprovisionnement de la caisse d'un agent."""
    guard = _portal_guard(request)
    if guard:
        return guard

    guard2 = _require_admin(request)
    if guard2:
        return guard2

    agent = Agent.objects.filter(id=agent_id, borlette=request.user.borlette).first()
    if not agent:
        return redirect("admin_portal:agents")

    from agent_portal.models import AgentCashboxEntry, CashboxEntryType
    from django.utils import timezone

    current_balance = agent.solde_caisse_calculé
    replenish_amount = None
    errors = []

    if request.method == "POST":
        amount = request.POST.get("amount")
        note = request.POST.get("note", "")

        try:
            if amount:
                replenish_amount = Decimal(str(amount))
                if replenish_amount <= 0:
                    errors.append("Le montant doit être supérieur à 0")
                else:
                    # REPLENISH positif (convention : crédit caisse)
                    AgentCashboxEntry.objects.create(
                        agent=agent,
                        borlette=agent.borlette,
                        entry_type=CashboxEntryType.REPLENISH,
                        amount=replenish_amount,
                        description=f"Réapprovisionnement caisse - {note}" if note else "Réapprovisionnement caisse",
                    )

                    new_balance = agent.solde_caisse_calculé

                    from accounts.audit import log_audit
                    from accounts.models import AuditAction
                    log_audit(
                        action=AuditAction.AGENT_CASHBOX_REPLENISH,
                        entity_type="Agent",
                        entity_id=str(agent.id),
                        borlette=request.user.borlette,
                        actor_user=request.user,
                        request=request,
                        meta={
                            "agent_id": agent.id,
                            "agent_nom": agent.nom,
                            "replenish_amount": float(replenish_amount),
                            "previous_balance": float(current_balance),
                            "new_balance": float(new_balance),
                            "note": note,
                        },
                    )

                    messages.success(request, f"Réapprovisionnement de {replenish_amount} G effectué avec succès")
                    return redirect("admin_portal:agents")
            else:
                errors.append("Veuillez entrer un montant")
        except Exception as e:
            errors.append(f"Erreur lors du réapprovisionnement: {str(e)}")

    return render(
        request,
        "admin_portal/agent_cashbox_replenish.html",
        {
            "agent": agent,
            "current_balance": current_balance,
            "errors": errors,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DÉPENSES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def depenses_list(request):
    """Liste des dépenses."""
    from accounts.models import Expense
    
    user = request.user
    if user.role != UserRole.ADMIN:
        return redirect("admin_portal:index")
    
    try:
        borlette = user.borlette
    except Exception:
        return redirect("admin_portal:index")

    expenses = Expense.objects.filter(borlette=borlette).select_related(
        "category", "tirage", "created_by"
    ).order_by("-date", "-created_at")[:100]

    return render(
        request,
        "admin_portal/depenses_list.html",
        {"expenses": expenses},
    )


@login_required
def depense_create(request):
    """Créer une dépense."""
    from accounts.models import Expense
    from .expense_forms import ExpenseForm
    
    user = request.user
    if user.role != UserRole.ADMIN:
        return redirect("admin_portal:index")
    
    try:
        borlette = user.borlette
    except Exception:
        return redirect("admin_portal:index")

    if request.method == "POST":
        form = ExpenseForm(request.POST, borlette=borlette)
        if form.is_valid():
            expense = form.save(created_by=user)

            from accounts.audit import log_audit
            from accounts.models import AuditAction
            log_audit(
                action=AuditAction.EXPENSE_CREATE,
                entity_type="Expense",
                entity_id=str(expense.id),
                borlette=borlette,
                actor_user=user,
                request=request,
                meta={
                    "amount": float(expense.amount),
                    "date": expense.date.isoformat(),
                    "category": expense.category.name if expense.category else None,
                    "description": expense.description,
                    "tirage_id": expense.tirage_id,
                    "session_key": str(expense.session_key) if expense.session_key else None,
                },
            )
            return redirect("admin_portal:depenses_list")
    else:
        form = ExpenseForm(borlette=borlette)

    return render(
        request,
        "admin_portal/depense_form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def depense_edit(request, depense_id: int):
    """Modifier une dépense."""
    from accounts.models import Expense
    from .expense_forms import ExpenseForm
    
    user = request.user
    if user.role != UserRole.ADMIN:
        return redirect("admin_portal:index")
    
    try:
        borlette = user.borlette
    except Exception:
        return redirect("admin_portal:index")

    expense = Expense.objects.filter(id=depense_id, borlette=borlette).first()
    if not expense:
        return redirect("admin_portal:depenses_list")

    if request.method == "POST":
        form = ExpenseForm(request.POST, borlette=borlette)
        if form.is_valid():
            expense = form.save(instance=expense)

            from accounts.audit import log_audit
            from accounts.models import AuditAction
            log_audit(
                action=AuditAction.EXPENSE_UPDATE,
                entity_type="Expense",
                entity_id=str(expense.id),
                borlette=borlette,
                actor_user=user,
                request=request,
                meta={
                    "amount": float(expense.amount),
                    "date": expense.date.isoformat(),
                    "category": expense.category.name if expense.category else None,
                    "description": expense.description,
                    "tirage_id": expense.tirage_id,
                    "session_key": str(expense.session_key) if expense.session_key else None,
                },
            )
            return redirect("admin_portal:depenses_list")
    else:
        initial = {
            "amount": expense.amount,
            "date": expense.date,
            "category": expense.category_id if expense.category else "",
            "description": expense.description,
        }
        form = ExpenseForm(initial=initial, borlette=borlette)

    return render(
        request,
        "admin_portal/depense_form.html",
        {"form": form, "is_edit": True, "expense": expense},
    )


@login_required
def depense_delete(request, depense_id: int):
    """Supprimer une dépense."""
    from accounts.models import Expense
    
    user = request.user
    if user.role != UserRole.ADMIN:
        return redirect("admin_portal:index")
    
    try:
        borlette = user.borlette
    except Exception:
        return redirect("admin_portal:index")

    expense = Expense.objects.filter(id=depense_id, borlette=borlette).first()
    if not expense:
        return redirect("admin_portal:depenses_list")

    if request.method == "POST":
        payload = {
            "amount": float(expense.amount),
            "date": expense.date.isoformat(),
            "category": expense.category.name if expense.category else None,
            "description": expense.description,
            "tirage_id": expense.tirage_id,
            "session_key": str(expense.session_key) if expense.session_key else None,
        }
        expense.delete()

        from accounts.audit import log_audit
        from accounts.models import AuditAction
        log_audit(
            action=AuditAction.EXPENSE_DELETE,
            entity_type="Expense",
            entity_id=str(depense_id),
            borlette=borlette,
            actor_user=user,
            request=request,
            meta=payload,
        )
        return redirect("admin_portal:depenses_list")

    return render(
        request,
        "admin_portal/depense_confirm_delete.html",
        {"expense": expense},
    )
