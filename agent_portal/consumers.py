"""
WebSocket Consumers pour Agent Portal
Gère les connexions temps réel des agents
"""
from __future__ import annotations

import json
from typing import Any

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from accounts.models import Agent, UserRole


class AgentConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket Consumer pour les agents.
    Canaux:
    - agent_status: statut online/offline
    - tirage_updates: notifications tirage
    - ticket_notifications: confirmation tickets
    """

    async def connect(self):
        """Connexion WebSocket - vérifie authentification agent"""
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        if user.role != UserRole.AGENT:
            await self.close(code=4003)
            return

        try:
            self.agent = await self._get_agent(user)
        except Exception:
            await self.close(code=4003)
            return

        self.borlette_id = self.agent.borlette_id
        self.agent_id = self.agent.id

        # Groupes de canaux
        self.agent_group = f"agent_{self.agent_id}"
        self.borlette_group = f"borlette_{self.borlette_id}"

        # Rejoindre les groupes
        await self.channel_layer.group_add(self.agent_group, self.channel_name)
        await self.channel_layer.group_add(self.borlette_group, self.channel_name)

        await self.accept()

        # Marquer agent comme connecté
        await self._set_agent_online(True)

        # Envoyer confirmation
        await self.send_json({
            "type": "connection_established",
            "agent_id": self.agent_id,
            "borlette_id": self.borlette_id,
            "timestamp": timezone.now().isoformat(),
        })

    async def disconnect(self, close_code):
        """Déconnexion - marquer agent offline"""
        if hasattr(self, "agent_id"):
            await self._set_agent_online(False)

            await self.channel_layer.group_discard(self.agent_group, self.channel_name)
            await self.channel_layer.group_discard(self.borlette_group, self.channel_name)

    async def receive_json(self, content: dict[str, Any]):
        """Réception de messages du client"""
        msg_type = content.get("type", "")

        if msg_type == "ping":
            await self.send_json({"type": "pong", "timestamp": timezone.now().isoformat()})

        elif msg_type == "subscribe_tirage":
            tirage_id = content.get("tirage_id")
            if tirage_id:
                tirage_group = f"tirage_{tirage_id}"
                await self.channel_layer.group_add(tirage_group, self.channel_name)
                await self.send_json({
                    "type": "subscribed",
                    "channel": f"tirage_{tirage_id}",
                })

        elif msg_type == "unsubscribe_tirage":
            tirage_id = content.get("tirage_id")
            if tirage_id:
                tirage_group = f"tirage_{tirage_id}"
                await self.channel_layer.group_discard(tirage_group, self.channel_name)

    # ─── Handlers pour messages du groupe ───────────────────────────────────

    async def ticket_confirmed(self, event: dict):
        """Notification: ticket confirmé"""
        await self.send_json({
            "type": "ticket_confirmed",
            "ticket_id": event.get("ticket_id"),
            "ticket_number": event.get("ticket_number"),
            "total_mise": event.get("total_mise"),
            "timestamp": event.get("timestamp"),
        })

    async def tirage_closed(self, event: dict):
        """Notification: tirage fermé"""
        await self.send_json({
            "type": "tirage_closed",
            "tirage_id": event.get("tirage_id"),
            "tirage_nom": event.get("tirage_nom"),
            "timestamp": event.get("timestamp"),
        })

    async def tirage_result(self, event: dict):
        """Notification: résultat tirage disponible"""
        await self.send_json({
            "type": "tirage_result",
            "tirage_id": event.get("tirage_id"),
            "tirage_nom": event.get("tirage_nom"),
            "resultat": event.get("resultat"),
            "timestamp": event.get("timestamp"),
        })

    async def risk_alert(self, event: dict):
        """Notification: alerte risque (blocage)"""
        await self.send_json({
            "type": "risk_alert",
            "tirage_id": event.get("tirage_id"),
            "jeu": event.get("jeu"),
            "valeur": event.get("valeur"),
            "message": event.get("message"),
            "timestamp": event.get("timestamp"),
        })

    async def broadcast_message(self, event: dict):
        """Message broadcast à tous les agents de la borlette"""
        await self.send_json({
            "type": "broadcast",
            "message": event.get("message"),
            "priority": event.get("priority", "info"),
            "timestamp": event.get("timestamp"),
        })

    # ─── Database helpers ───────────────────────────────────────────────────

    @database_sync_to_async
    def _get_agent(self, user) -> Agent:
        return Agent.objects.select_related("borlette").get(user=user)

    @database_sync_to_async
    def _set_agent_online(self, is_online: bool):
        """Met à jour le statut de connexion de l'agent"""
        Agent.objects.filter(id=self.agent_id).update(
            derniere_connexion=timezone.now() if is_online else None
        )


# ═══════════════════════════════════════════════════════════════════════════
# HELPER: Envoyer notification depuis les vues
# ═══════════════════════════════════════════════════════════════════════════

async def send_ticket_notification(agent_id: int, ticket_data: dict):
    """Envoyer notification de ticket confirmé à un agent"""
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f"agent_{agent_id}",
        {
            "type": "ticket_confirmed",
            **ticket_data,
            "timestamp": timezone.now().isoformat(),
        }
    )


async def send_tirage_update(borlette_id: int, tirage_data: dict):
    """Envoyer update tirage à tous les agents d'une borlette"""
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f"borlette_{borlette_id}",
        {
            **tirage_data,
            "timestamp": timezone.now().isoformat(),
        }
    )


def send_ticket_notification_sync(agent_id: int, ticket_data: dict):
    """Version synchrone pour appeler depuis les vues Django"""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"agent_{agent_id}",
        {
            "type": "ticket_confirmed",
            **ticket_data,
            "timestamp": timezone.now().isoformat(),
        }
    )


def send_tirage_update_sync(borlette_id: int, event_type: str, tirage_data: dict):
    """Version synchrone pour appeler depuis les vues Django"""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"borlette_{borlette_id}",
        {
            "type": event_type,
            **tirage_data,
            "timestamp": timezone.now().isoformat(),
        }
    )
