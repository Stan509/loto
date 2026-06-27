"""
TicketBatchService — Logique métier isolée pour la création multi-tirages.

Ce service peut être appelé :
- Par la vue Django actuelle (api_ticket_create_multi)
- Par une future route interne (Gateway Go) sans dépendre de HttpRequest.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.audit import log_audit
from accounts.models import AuditAction, Agent, Borlette
from core.services.risk_management_service import RiskManagementService
from core.services.ticket_validation_service import TicketValidationService

from agent_portal.models import Ticket, TicketLine, TicketStatus, AgentLedgerEntry, LedgerEntryType
from accounts.models import Tirage, TirageStatus

logger = logging.getLogger(__name__)


def _generate_ticket_number() -> str:
    now = timezone.localtime(timezone.now())
    return f"CB-{now.year}-{now.strftime('%m%d%H%M%S%f')[-10:]}"


def _create_commission_entry(ticket: Ticket) -> AgentLedgerEntry | None:
    """Crée une entrée COMMISSION_EARNED pour un ticket (idempotent)."""
    if not ticket.agent or not ticket.borlette:
        return None

    existing = AgentLedgerEntry.objects.filter(
        related_ticket=ticket, entry_type=LedgerEntryType.COMMISSION_EARNED
    ).first()
    if existing:
        return existing

    commission_pct = Decimal(str(ticket.agent.commission or 0)) / Decimal("100")
    commission_amount = (ticket.total_mise * commission_pct).quantize(Decimal("0.01"))

    if commission_amount <= 0:
        return None

    entry = AgentLedgerEntry.objects.create(
        agent=ticket.agent,
        borlette=ticket.borlette,
        related_ticket=ticket,
        entry_type=LedgerEntryType.COMMISSION_EARNED,
        amount=commission_amount,
        description=f"Commission sur {ticket.numero_ticket}",
    )

    ticket.agent.solde_actuel += commission_amount
    ticket.agent.total_ventes += ticket.total_mise
    ticket.agent.total_benefice += commission_amount
    ticket.agent.save(update_fields=["solde_actuel", "total_ventes", "total_benefice"])

    return entry


def _safe_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


class TicketBatchResult:
    """Résultat d'un batch de création de tickets."""
    def __init__(
        self,
        success: bool,
        status_code: int,
        group_id: uuid.UUID,
        created_tickets: list[dict],
        failed_tirages: list[dict],
        error_message: str = "",
    ):
        self.success = success
        self.status_code = status_code
        self.group_id = group_id
        self.created_tickets = created_tickets
        self.failed_tirages = failed_tirages
        self.error_message = error_message

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "group_id": str(self.group_id),
            "tickets": self.created_tickets,
        }
        if self.failed_tirages:
            data["failed"] = self.failed_tirages
        return data


class TicketBatchService:
    """Service de création de tickets multi-tirages."""

    @classmethod
    def create_tickets(
        cls,
        *,
        agent: Agent,
        body: dict[str, Any],
        device_id: str = "",
        actor_user=None,
        request=None,
    ) -> TicketBatchResult:
        """
        Crée un batch de tickets pour un ou plusieurs tirages.
        Ne dépend pas de HttpRequest (peut être appelé par le Gateway Go).
        """
        tirage_ids = body.get("tirage_ids", [])
        entries = body.get("entries", [])
        overrides = body.get("overrides", {})
        session_key = body.get("session_key", "")
        is_offline_sync = bool(device_id)

        logger.info(f"[BATCH] tirage_ids={tirage_ids}, entries_count={len(entries)}, agent={agent.id}, borlette={agent.borlette.id}")

        if not tirage_ids:
            return TicketBatchResult(
                success=False, status_code=400, group_id=uuid.uuid4(),
                created_tickets=[], failed_tirages=[],
                error_message="Aucun tirage sélectionné",
            )
        if not entries:
            return TicketBatchResult(
                success=False, status_code=400, group_id=uuid.uuid4(),
                created_tickets=[], failed_tirages=[],
                error_message="Aucune ligne de mise",
            )

        borlette = agent.borlette
        admin = borlette.user
        group_id = uuid.uuid4()

        # Récupérer les tirages actifs
        draws = list(
            Tirage.objects.filter(
                id__in=tirage_ids,
                borlette=borlette,
                statut=TirageStatus.ACTIF,
            )
        )

        if len(draws) != len(tirage_ids):
            found_ids = {d.id for d in draws}
            missing = [tid for tid in tirage_ids if tid not in found_ids]
            logger.error(f"[BATCH] Tirages non trouvés: {missing}. Cherchés: {tirage_ids}, Trouvés ACTIF: {[d.id for d in draws]}")
            return TicketBatchResult(
                success=False, status_code=400, group_id=group_id,
                created_tickets=[], failed_tirages=[],
                error_message=f"Tirages invalides ou inactifs: {missing}",
            )

        created_tickets: list[dict] = []
        failed_tirages: list[dict] = []

        for draw in draws:
            logger.info("[BATCH] Processing draw %s - %s", draw.id, draw.nom)
            try:
                with transaction.atomic():
                    draw = Tirage.objects.select_for_update().get(
                        id=draw.id,
                        borlette=borlette,
                        statut=TirageStatus.ACTIF,
                    )

                    if draw.etat_ouverture != "OUVERT":
                        failed_tirages.append({
                            "tirage_id": draw.id,
                            "tirage_nom": draw.nom,
                            "error": f"Le tirage {draw.nom} est fermé",
                        })
                        log_audit(
                            action=AuditAction.OFFLINE_SYNC_FAILED,
                            entity_type="Ticket",
                            entity_id="failed",
                            borlette=borlette,
                            actor_user=actor_user,
                            actor_agent=agent,
                            request=request,
                            meta={
                                "tirage_id": draw.id,
                                "tirage_nom": draw.nom,
                                "error": "tirage fermé",
                                "session_key": session_key,
                                "device_id": device_id if is_offline_sync else None,
                                "batch_id": str(group_id),
                            },
                        )
                        continue

                    if is_offline_sync and str(draw.session_key) != session_key:
                        failed_tirages.append({
                            "tirage_id": draw.id,
                            "tirage_nom": draw.nom,
                            "error": f"Session expirée pour {draw.nom}. Le tirage a été rouvert.",
                        })
                        log_audit(
                            action=AuditAction.OFFLINE_SYNC_FAILED,
                            entity_type="Ticket",
                            entity_id="failed",
                            borlette=borlette,
                            actor_user=actor_user,
                            actor_agent=agent,
                            request=request,
                            meta={
                                "tirage_id": draw.id,
                                "tirage_nom": draw.nom,
                                "error": "session_key mismatch",
                                "expected_session": session_key,
                                "actual_session": str(draw.session_key),
                                "device_id": device_id if is_offline_sync else None,
                                "batch_id": str(group_id),
                            },
                        )
                        continue

                    tirage_entries = overrides.get(str(draw.id), {}).get("entries", entries)

                    lines = []
                    for e in tirage_entries:
                        lines.append({
                            "jeu": e.get("game", "") or e.get("jeu", ""),
                            "valeur": e.get("number", "") or e.get("valeur", ""),
                            "mise": e.get("stake", 0) or e.get("mise", 0),
                            "gratuit": bool(e.get("gratuit", False)) or bool(e.get("free", False)),
                        })

                    validation = TicketValidationService.validate_ticket(
                        admin=admin,
                        agent=agent,
                        ticket_lines=lines,
                        draw_ids=[draw.id],
                    )

                    if not validation.get("is_valid"):
                        errors = validation.get("errors", ["Invalide"])
                        failed_tirages.append({
                            "tirage_id": draw.id,
                            "tirage_nom": draw.nom,
                            "error": f"Tirage {draw.nom}: " + "; ".join(errors),
                        })
                        log_audit(
                            action=AuditAction.OFFLINE_SYNC_FAILED,
                            entity_type="Ticket",
                            entity_id="validation_failed",
                            borlette=borlette,
                            actor_user=actor_user,
                            actor_agent=agent,
                            request=request,
                            meta={
                                "tirage_id": draw.id,
                                "tirage_nom": draw.nom,
                                "errors": errors,
                                "device_id": device_id if is_offline_sync else None,
                                "batch_id": str(group_id),
                            },
                        )
                        continue

                    draw.ensure_current_session()

                    ticket_number = _generate_ticket_number()
                    ticket = Ticket.objects.create(
                        borlette=borlette,
                        agent=agent,
                        tirage=draw,
                        tirage_session_key=draw.session_key,
                        group_id=group_id,
                        numero_ticket=ticket_number,
                        total_mise=Decimal("0"),
                        statut=TicketStatus.VALIDE,
                    )

                    total_mise = Decimal("0")
                    ticket_lines: list[dict] = []
                    free_marriages = validation.get("free_marriages", [])

                    for raw in lines:
                        jeu = (raw.get("jeu") or "").strip().lower()
                        valeur = TicketValidationService.canonicalize_value(
                            jeu, str(raw.get("valeur") or "").strip()
                        )
                        mise = _safe_decimal(raw.get("mise", 0))
                        potentiel_gain = _safe_decimal(raw.get("potentiel_gain", 0))
                        gratuit = bool(raw.get("gratuit", False))

                        if not gratuit and mise <= 0:
                            continue

                        TicketLine.objects.create(
                            ticket=ticket,
                            jeu=jeu,
                            valeur=valeur,
                            mise=mise,
                            potentiel_gain=potentiel_gain,
                            gratuit=gratuit,
                        )
                        ticket_lines.append({
                            "jeu": jeu.upper(),
                            "valeur": valeur,
                            "mise": float(mise),
                            "potentiel_gain": float(potentiel_gain),
                        })
                        total_mise += mise

                        RiskManagementService.apply_bet(tirage=draw, game=jeu, value=valeur, stake=mise)

                    for fm in free_marriages:
                        valeur = str(fm.get("valeur", "")).strip()
                        if valeur:
                            TicketLine.objects.create(
                                ticket=ticket,
                                jeu="mariage",
                                valeur=valeur,
                                mise=Decimal("0"),
                                potentiel_gain=Decimal("0"),
                                gratuit=True,
                            )

                    ticket.total_mise = total_mise
                    ticket.save(update_fields=["total_mise"])

                    _create_commission_entry(ticket)

                    from agent_portal.services import create_cashbox_entry_for_sale
                    create_cashbox_entry_for_sale(ticket)

                    log_audit(
                        action=AuditAction.TICKET_CREATE,
                        entity_type="Ticket",
                        entity_id=str(ticket.id),
                        borlette=borlette,
                        actor_user=actor_user or agent.user,
                        actor_agent=agent,
                        request=request,
                        meta={
                            "ticket_no": ticket.numero_ticket,
                            "group_id": str(group_id),
                            "tirage_id": draw.id,
                            "tirage_nom": draw.nom,
                            "session_key": str(draw.session_key),
                            "total_mise": float(ticket.total_mise),
                            "lines_count": len(ticket_lines),
                            "offline_sync": is_offline_sync,
                            "device_id": device_id if is_offline_sync else None,
                        },
                    )

                    created_tickets.append({
                        "tirage_id": draw.id,
                        "tirage_nom": draw.nom,
                        "ticket_uuid": str(ticket.id),
                        "ticket_no": ticket.numero_ticket,
                        "group_id": str(group_id),
                        "total_mise": float(total_mise),
                        "lines": ticket_lines,
                    })

            except Exception as e:
                logger.exception("[BATCH] EXCEPTION draw=%s type=%s msg=%s", draw.id, type(e).__name__, str(e))
                failed_tirages.append({
                    "tirage_id": draw.id,
                    "tirage_nom": draw.nom,
                    "error": f"Erreur interne: {str(e)}",
                })
                log_audit(
                    action=AuditAction.OFFLINE_SYNC_FAILED,
                    entity_type="Ticket",
                    entity_id="exception",
                    borlette=borlette,
                    actor_user=actor_user,
                    actor_agent=agent,
                    request=request,
                    meta={
                        "tirage_id": draw.id,
                        "tirage_nom": draw.nom,
                        "error": str(e),
                        "device_id": device_id if is_offline_sync else None,
                        "batch_id": str(group_id),
                    },
                )
                continue

        if not created_tickets and failed_tirages:
            return TicketBatchResult(
                success=False, status_code=400, group_id=group_id,
                created_tickets=[], failed_tirages=failed_tirages,
                error_message="Tous les tirages ont échoué",
            )

        if created_tickets and failed_tirages:
            log_audit(
                action=AuditAction.OFFLINE_BATCH_PARTIAL,
                entity_type="Ticket",
                entity_id=str(group_id),
                borlette=borlette,
                actor_user=actor_user,
                actor_agent=agent,
                request=request,
                meta={
                    "batch_id": str(group_id),
                    "created_count": len(created_tickets),
                    "failed_count": len(failed_tirages),
                    "created_tirage_ids": [t["tirage_id"] for t in created_tickets],
                    "failed_tirage_ids": [f["tirage_id"] for f in failed_tirages],
                    "device_id": device_id if is_offline_sync else None,
                    "session_key": session_key,
                },
            )
        elif created_tickets and is_offline_sync:
            log_audit(
                action=AuditAction.OFFLINE_SYNC_SUCCESS,
                entity_type="Ticket",
                entity_id=str(group_id),
                borlette=borlette,
                actor_user=actor_user,
                actor_agent=agent,
                request=request,
                meta={
                    "batch_id": str(group_id),
                    "ticket_count": len(created_tickets),
                    "device_id": device_id,
                    "session_key": session_key,
                },
            )

        return TicketBatchResult(
            success=True, status_code=200, group_id=group_id,
            created_tickets=created_tickets, failed_tirages=failed_tirages,
        )
