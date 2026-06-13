from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest

from accounts.models import AuditAction, AuditLog, Agent, Borlette, User

logger = logging.getLogger(__name__)


def log_audit(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    borlette: Borlette | None = None,
    actor_user: User | None = None,
    actor_agent: Agent | None = None,
    meta: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditLog | None:
    """
    Create an AuditLog entry. Safe: never raises, logs errors instead.
    
    Args:
        action: AuditAction value (e.g. TICKET_CREATE)
        entity_type: Model name (e.g. "Ticket", "Tirage")
        entity_id: Primary key of the entity
        borlette: Optional, auto-inferred from actor_agent or actor_user
        actor_user: User performing the action
        actor_agent: Agent performing the action (if applicable)
        meta: Additional metadata dict
        request: HttpRequest to extract ip/user_agent/path
    
    Returns:
        AuditLog instance or None if creation failed
    """
    try:
        payload: dict[str, Any] = dict(meta or {})

        if request is not None:
            payload.setdefault("path", getattr(request, "path", None))
            payload.setdefault("method", getattr(request, "method", None))
            payload.setdefault("ip", request.META.get("REMOTE_ADDR"))
            payload.setdefault("user_agent", request.META.get("HTTP_USER_AGENT"))

            if actor_user is None and getattr(request, "user", None) and request.user.is_authenticated:
                actor_user = request.user

        if borlette is None:
            if actor_agent is not None:
                borlette = actor_agent.borlette
            elif actor_user is not None and hasattr(actor_user, "borlette"):
                borlette = getattr(actor_user, "borlette", None)

        return AuditLog.objects.create(
            borlette=borlette,
            actor_user=actor_user,
            actor_agent=actor_agent,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            meta=payload,
        )
    except Exception as exc:
        logger.exception("Failed to create AuditLog: %s", exc)
        return None
