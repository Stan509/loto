"""
Security helpers for admin_portal.
Centralized permission checks and borlette isolation.
"""
from __future__ import annotations

from functools import wraps
from typing import Callable

from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect

from accounts.models import UserRole


def get_user_borlette(user):
    """Return borlette for owner-admin or staff user.

    - Owner admin: user.borlette exists (OneToOne)
    - Staff: user.staffuser exists and is_active
    """
    try:
        return user.borlette
    except Exception:
        pass

    staff = getattr(user, "staffuser", None)
    if staff and getattr(staff, "is_active", False):
        return staff.borlette
    return None


def get_staff_user(user):
    staff = getattr(user, "staffuser", None)
    if staff and getattr(staff, "is_active", False):
        return staff
    return None


def staff_can(user, perm_field: str) -> bool:
    staff = get_staff_user(user)
    if not staff:
        return True
    return bool(getattr(staff, perm_field, False))


def require_admin(request: HttpRequest) -> JsonResponse | None:
    """
    Check that request.user is an ADMIN with a borlette.
    Returns None if OK, or a redirect/JsonResponse if not.
    
    Usage in views:
        guard = require_admin(request)
        if guard:
            return guard
    """
    if not request.user.is_authenticated:
        return redirect("/portal/login/")
    
    if request.user.role != UserRole.ADMIN:
        return redirect("/portal/dashboard/")

    borlette = get_user_borlette(request.user)
    if borlette is None:
        return redirect("/portal/dashboard/")
    
    return None


def require_admin_api(request: HttpRequest) -> JsonResponse | None:
    """
    Same as require_admin but returns JSON 401/403 for API endpoints.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    
    if request.user.role != UserRole.ADMIN:
        return JsonResponse({"error": "Admin access required"}, status=403)

    borlette = get_user_borlette(request.user)
    if borlette is None:
        return JsonResponse({"error": "No borlette associated"}, status=403)
    
    return None


def ensure_borlette_match(obj_borlette, user_borlette) -> JsonResponse | None:
    """
    Verify that obj_borlette matches user_borlette.
    Returns None if OK, or 403 JsonResponse if mismatch.
    
    Usage:
        mismatch = ensure_borlette_match(ticket.borlette, request.user.borlette)
        if mismatch:
            return mismatch
    """
    if obj_borlette is None or user_borlette is None:
        return JsonResponse({"error": "Borlette mismatch"}, status=403)
    
    if obj_borlette.id != user_borlette.id:
        return JsonResponse({"error": "Access denied: wrong borlette"}, status=403)
    
    return None


def admin_api_view(view_func: Callable) -> Callable:
    """
    Decorator combining login_required + require_admin_api for JSON endpoints.
    
    Usage:
        @admin_api_view
        def my_api(request):
            borlette = request.user.borlette
            ...
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        guard = require_admin_api(request)
        if guard:
            return guard
        return view_func(request, *args, **kwargs)
    return wrapper


def require_staff_permission_api(permission_field: str):
    """Decorator for API endpoints requiring a staff permission.

    Owner-admin always passes.
    Staff must have the permission_field=True.
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            guard = require_admin_api(request)
            if guard:
                return guard
            if not staff_can(request.user, permission_field):
                return JsonResponse({"error": "Permission refusée"}, status=403)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def admin_page_view(view_func: Callable) -> Callable:
    """
    Decorator combining login_required + require_admin for HTML page views.
    Also handles super_admin redirect to /admin/.
    
    Usage:
        @admin_page_view
        def my_page(request):
            borlette = request.user.borlette
            ...
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/portal/login/")
        
        if request.user.is_superuser or request.user.role == UserRole.SUPER_ADMIN:
            return redirect("/admin/")
        
        guard = require_admin(request)
        if guard:
            return guard
        return view_func(request, *args, **kwargs)
    return wrapper
