"""
Dashboard API Endpoints - KPI, Charts, Tables, Recommendations
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse

from accounts.models import UserRole
from .dashboard_service import DashboardService

from admin_portal.security import get_user_borlette, staff_can


def _require_admin_api(request: HttpRequest) -> JsonResponse | None:
    """Vérifie que l'utilisateur est admin avec une borlette."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Non authentifié"}, status=401)

    if request.user.is_superuser or request.user.role == UserRole.SUPER_ADMIN:
        return JsonResponse({"error": "Accès refusé"}, status=403)
    
    if request.user.role != UserRole.ADMIN:
        return JsonResponse({"error": "Accès refusé"}, status=403)
    
    borlette = get_user_borlette(request.user)
    if not borlette:
        return JsonResponse({"error": "Pas de borlette associée"}, status=403)
    
    return None


def _require_dashboard_perm(request: HttpRequest) -> JsonResponse | None:
    if not staff_can(request.user, "can_view_dashboard"):
        return JsonResponse({"error": "Permission refusée"}, status=403)
    return None


@login_required
def api_dashboard_summary(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/dashboard/summary/?period=7d
    Retourne les KPI principaux + agents online + tirages status.
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    p = _require_dashboard_perm(request)
    if p:
        return p
    
    period = request.GET.get("period", "7d")
    service = DashboardService(get_user_borlette(request.user))
    
    kpi = service.get_kpi_summary(period)
    agents = service.get_agents_online()
    tirages = service.get_tirages_status()
    
    return JsonResponse({
        "success": True,
        "kpi": kpi,
        "agents": agents,
        "tirages": tirages,
    })


@login_required
def api_dashboard_charts(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/dashboard/charts/?period=7d
    Retourne les données pour les graphiques.
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    p = _require_dashboard_perm(request)
    if p:
        return p
    
    period = request.GET.get("period", "7d")
    service = DashboardService(get_user_borlette(request.user))
    
    charts = service.get_charts_data(period)
    
    return JsonResponse({
        "success": True,
        "charts": charts,
    })


@login_required
def api_dashboard_tables(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/dashboard/tables/?period=7d
    Retourne les données pour les tables compactes.
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    p = _require_dashboard_perm(request)
    if p:
        return p
    
    period = request.GET.get("period", "7d")
    service = DashboardService(get_user_borlette(request.user))
    
    tables = service.get_tables_data(period)
    
    return JsonResponse({
        "success": True,
        "tables": tables,
    })


@login_required
def api_dashboard_recommendations(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/dashboard/recommendations/?period=7d
    Retourne les recommandations basées sur les signaux.
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    p = _require_dashboard_perm(request)
    if p:
        return p
    
    period = request.GET.get("period", "7d")
    service = DashboardService(get_user_borlette(request.user))
    
    recommendations = service.get_recommendations(period)
    
    return JsonResponse({
        "success": True,
        "recommendations": recommendations,
    })


@login_required
def api_dashboard_full(request: HttpRequest) -> JsonResponse:
    """
    GET /portal/api/dashboard/full/?period=7d
    Retourne toutes les données du dashboard en une seule requête.
    """
    guard = _require_admin_api(request)
    if guard:
        return guard

    p = _require_dashboard_perm(request)
    if p:
        return p
    
    period = request.GET.get("period", "7d")
    service = DashboardService(get_user_borlette(request.user))
    
    # Récupérer les notifications non lues
    from .models import AdminNotification
    notifications_unread = AdminNotification.objects.filter(
        borlette=get_user_borlette(request.user),
        is_read=False
    ).count()
    
    return JsonResponse({
        "success": True,
        "kpi": service.get_kpi_summary(period),
        "agents": service.get_agents_online(),
        "tirages": service.get_tirages_status(),
        "charts": service.get_charts_data(period),
        "tables": service.get_tables_data(period),
        "recommendations": service.get_recommendations(period),
        "notifications_unread": notifications_unread,
    })


@login_required
def api_notifications_list(request):
    """
    GET /portal/api/notifications/?limit=20&unread_only=false
    Retourne les notifications de l'admin.
    """
    error = _require_admin_api(request)
    if error:
        return error
    
    from .models import AdminNotification
    from django.utils import timezone
    
    limit = min(int(request.GET.get("limit", 20)), 50)
    unread_only = request.GET.get("unread_only", "false").lower() == "true"
    
    qs = AdminNotification.objects.filter(borlette=request.user.borlette)
    
    if unread_only:
        qs = qs.filter(is_read=False)
    
    notifications = qs.order_by("-created_at")[:limit]
    
    return JsonResponse({
        "success": True,
        "notifications": [
            {
                "id": str(n.id),
                "type": n.notification_type,
                "title": n.title,
                "message": n.message,
                "meta": n.meta,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
        "unread_count": AdminNotification.objects.filter(
            borlette=request.user.borlette,
            is_read=False
        ).count(),
    })


@login_required
def api_notifications_mark_read(request):
    """
    POST /portal/api/notifications/mark-read/
    Body: {"notification_ids": ["uuid1", "uuid2"]} ou {"all": true}
    Marque les notifications comme lues.
    """
    import json
    from django.views.decorators.http import require_POST
    from django.utils import timezone
    
    error = _require_admin_api(request)
    if error:
        return error
    
    if request.method != "POST":
        return JsonResponse({"error": "POST requis"}, status=405)
    
    from .models import AdminNotification
    
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        body = {}
    
    now = timezone.now()
    
    if body.get("all"):
        # Marquer toutes comme lues
        count = AdminNotification.objects.filter(
            borlette=request.user.borlette,
            is_read=False
        ).update(is_read=True, read_at=now)
    else:
        # Marquer les IDs spécifiés
        notification_ids = body.get("notification_ids", [])
        count = AdminNotification.objects.filter(
            borlette=request.user.borlette,
            id__in=notification_ids,
            is_read=False
        ).update(is_read=True, read_at=now)
    
    return JsonResponse({
        "success": True,
        "marked_count": count,
    })
