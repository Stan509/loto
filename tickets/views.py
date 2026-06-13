import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.shortcuts import redirect, render

from accounts.models import UserRole
from .services.ticket_preview_service import build_ticket_preview


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
def ticket_preview(request: HttpRequest):
    guard = _require_agent(request)
    if guard:
        return guard

    agent = request.user.agent
    admin = agent.borlette.user

    errors = []
    preview = None

    if request.method == "POST":
        if request.content_type and "application/json" in request.content_type:
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except Exception:
                payload = {}
            ticket_lines = payload.get("ticket_lines") or []
            draw_ids = payload.get("draw_ids") or []
        else:
            raw_lines = request.POST.get("ticket_lines_json") or "[]"
            try:
                ticket_lines = json.loads(raw_lines)
            except Exception:
                ticket_lines = []
                errors.append("Payload ticket invalide")

            raw_draw_ids = request.POST.get("draw_ids") or ""
            draw_ids = [int(x) for x in raw_draw_ids.replace(" ", "").split(",") if x.isdigit()]

        preview = build_ticket_preview(admin=admin, agent=agent, ticket_lines=ticket_lines, draw_ids=draw_ids)
    else:
        preview = build_ticket_preview(admin=admin, agent=agent, ticket_lines=[], draw_ids=[])

    return render(
        request,
        "tickets/ticket_thermal_preview.html",
        {
            "preview": preview,
            "errors": errors,
            "mode": "preview",
        },
    )


@login_required
def ticket_confirm(request: HttpRequest):
    guard = _require_agent(request)
    if guard:
        return guard

    # No DB write allowed at this step.
    return redirect("admin_portal:tickets:preview")
