"""
Tests for Agent Portal API endpoints
"""
import json
import uuid
import hmac
import hashlib
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from accounts.models import (
    Borlette, Agent, Tirage, Ticket, TicketStatus,
    Device, AuditLog, AuditAction
)

User = get_user_model()


class CreateMultiEndpointTests(TestCase):
    """Tests for POST /api/agent/ticket/create-multi/ - Phase I-A2"""

    def setUp(self):
        self.client = Client()
        
        # Create borlette
        self.borlette = Borlette.objects.create(
            nom="Test Borlette",
            code="TEST",
        )
        
        # Create user and agent
        self.user = User.objects.create_user(
            username="testagent",
            password="testpass123",
        )
        self.agent = Agent.objects.create(
            user=self.user,
            borlette=self.borlette,
            nom="Test Agent",
            code="AGT001",
        )
        
        # Create device for HMAC tests
        self.device = Device.objects.create(
            agent=self.agent,
            device_id="test-device-123",
            device_secret="test-secret-xyz",
            device_name="Test Device",
            is_active=True
        )
        
        # Create open tirages with same session key
        self.session_key = str(uuid.uuid4())
        self.tirage1 = Tirage.objects.create(
            borlette=self.borlette,
            nom="Midi",
            session_key=self.session_key,
            is_open=True,
            etat_ouverture="OUVERT",
        )
        self.tirage2 = Tirage.objects.create(
            borlette=self.borlette,
            nom="Soir",
            session_key=self.session_key,
            is_open=True,
            etat_ouverture="OUVERT",
        )
        
        # Create closed tirage for failure test
        self.tirage_closed = Tirage.objects.create(
            borlette=self.borlette,
            nom="Ferme",
            session_key=self.session_key,
            is_open=False,
            etat_ouverture="FERME",
        )

    def _get_auth_headers(self, agent):
        """Helper to get JWT auth headers for an agent"""
        return {"HTTP_AUTHORIZATION": f"Bearer mock-token-{agent.id}"}
    
    def _calculate_hmac(self, payload_dict, session_key, device_secret):
        """Calculate HMAC signature for offline sync"""
        payload_json = json.dumps(payload_dict, sort_keys=True, separators=(',', ':'))
        message = f"{payload_json}:{session_key}"
        signature = hmac.new(
            device_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature, payload_json

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_create_multi_online_success(self, mock_get_agent):
        """create-multi should create tickets for multiple tirages when online"""
        mock_get_agent.return_value = self.agent
        
        payload = {
            "tirage_ids": [self.tirage1.id, self.tirage2.id],
            "entries": [
                {"game": "boule", "number": "34", "stake": 50.0},
                {"game": "mariage", "number": "34x55", "stake": 25.0}
            ],
            "session_key": self.session_key
        }
        
        response = self.client.post(
            "/api/agent/ticket/create-multi/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(self.agent)
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data["success"])
        self.assertIsNotNone(data["group_id"])
        self.assertEqual(len(data["tickets"]), 2)
        self.assertIsNone(data.get("failed"))
        
        # Verify tickets were created in database
        tickets = Ticket.objects.filter(agent=self.agent)
        self.assertEqual(tickets.count(), 2)

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_create_multi_offline_with_hmac(self, mock_get_agent):
        """create-multi should verify HMAC for offline sync"""
        mock_get_agent.return_value = self.agent
        
        payload = {
            "tirage_ids": [self.tirage1.id],
            "entries": [
                {"game": "boule", "number": "34", "stake": 50.0}
            ],
            "session_key": self.session_key
        }
        
        # Calculate HMAC
        signature, _ = self._calculate_hmac(
            payload, self.session_key, self.device.device_secret
        )
        
        response = self.client.post(
            "/api/agent/ticket/create-multi/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(self.agent),
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_PAYLOAD_SIGN=signature
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data["success"])
        self.assertEqual(len(data["tickets"]), 1)

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_create_multi_offline_hmac_invalid(self, mock_get_agent):
        """create-multi should reject requests with invalid HMAC"""
        mock_get_agent.return_value = self.agent
        
        payload = {
            "tirage_ids": [self.tirage1.id],
            "entries": [
                {"game": "boule", "number": "34", "stake": 50.0}
            ],
            "session_key": self.session_key
        }
        
        # Use wrong signature
        response = self.client.post(
            "/api/agent/ticket/create-multi/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(self.agent),
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_PAYLOAD_SIGN="invalid-signature"
        )
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        
        self.assertFalse(data["success"])
        self.assertIn("hmac", data["error"].lower())

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_create_multi_offline_device_inactive(self, mock_get_agent):
        """create-multi should reject requests from inactive devices"""
        mock_get_agent.return_value = self.agent
        
        # Deactivate device
        self.device.is_active = False
        self.device.save()
        
        payload = {
            "tirage_ids": [self.tirage1.id],
            "entries": [
                {"game": "boule", "number": "34", "stake": 50.0}
            ],
            "session_key": self.session_key
        }
        
        response = self.client.post(
            "/api/agent/ticket/create-multi/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(self.agent),
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_PAYLOAD_SIGN="some-signature"
        )
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        
        self.assertFalse(data["success"])
        self.assertIn("device", data["error"].lower())

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_create_multi_partial_failure_closed_tirage(self, mock_get_agent):
        """create-multi should handle partial failures and continue processing"""
        mock_get_agent.return_value = self.agent
        
        # Request with one open and one closed tirage
        payload = {
            "tirage_ids": [self.tirage1.id, self.tirage_closed.id],
            "entries": [
                {"game": "boule", "number": "34", "stake": 50.0}
            ],
            "session_key": self.session_key
        }
        
        response = self.client.post(
            "/api/agent/ticket/create-multi/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(self.agent)
        )
        
        # Should return 200 with partial success
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data["success"])
        self.assertEqual(len(data["tickets"]), 1)  # Only tirage1 succeeds
        self.assertEqual(len(data["failed"]), 1)   # tirage_closed fails
        
        # Verify the failed tirage has error info
        failed = data["failed"][0]
        self.assertEqual(failed["tirage_id"], self.tirage_closed.id)
        self.assertIn("ferm", failed["error"].lower())

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_create_multi_session_key_mismatch(self, mock_get_agent):
        """create-multi should reject offline sync with wrong session_key"""
        mock_get_agent.return_value = self.agent
        
        payload = {
            "tirage_ids": [self.tirage1.id],
            "entries": [
                {"game": "boule", "number": "34", "stake": 50.0}
            ],
            "session_key": "wrong-session-key"
        }
        
        signature, _ = self._calculate_hmac(
            payload, "wrong-session-key", self.device.device_secret
        )
        
        response = self.client.post(
            "/api/agent/ticket/create-multi/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(self.agent),
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_PAYLOAD_SIGN=signature
        )
        
        # Should fail because tirage session_key doesn't match payload session_key
        self.assertEqual(response.status_code, 200)  # Partial success with failure
        data = response.json()
        
        # Should have failed entry
        self.assertEqual(len(data["failed"]), 1)
        self.assertIn("session", data["failed"][0]["error"].lower())

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_create_multi_all_failures_returns_error(self, mock_get_agent):
        """create-multi should return error if all tirages fail"""
        mock_get_agent.return_value = self.agent
        
        # Request only closed tirages
        payload = {
            "tirage_ids": [self.tirage_closed.id],
            "entries": [
                {"game": "boule", "number": "34", "stake": 50.0}
            ],
            "session_key": self.session_key
        }
        
        response = self.client.post(
            "/api/agent/ticket/create-multi/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(self.agent)
        )
        
        # Should return 400 when all fail
        self.assertEqual(response.status_code, 400)
        data = response.json()
        
        self.assertFalse(data["success"])

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_create_multi_creates_audit_logs(self, mock_get_agent):
        """create-multi should create audit logs for each ticket"""
        mock_get_agent.return_value = self.agent
        
        initial_audit_count = AuditLog.objects.count()
        
        payload = {
            "tirage_ids": [self.tirage1.id],
            "entries": [
                {"game": "boule", "number": "34", "stake": 50.0}
            ],
            "session_key": self.session_key
        }
        
        self.client.post(
            "/api/agent/ticket/create-multi/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(self.agent)
        )
        
        # Should have created audit log
        self.assertGreater(AuditLog.objects.count(), initial_audit_count)
        
        # Verify the audit log entry
        audit = AuditLog.objects.filter(action=AuditAction.TICKET_CREATE).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor_agent, self.agent)


class BlueprintEndpointTests(TestCase):
    """Tests for GET /api/agent/ticket/<uuid>/blueprint/"""

    def setUp(self):
        self.client = Client()
        
        # Create borlette
        self.borlette = Borlette.objects.create(
            nom="Test Borlette",
            code="TEST",
        )
        
        # Create user and agent
        self.user = User.objects.create_user(
            username="testagent",
            password="testpass123",
        )
        self.agent = Agent.objects.create(
            user=self.user,
            borlette=self.borlette,
            nom="Test Agent",
            code="AGT001",
        )
        
        # Create another agent for permission tests
        self.other_user = User.objects.create_user(
            username="otheragent",
            password="testpass123",
        )
        self.other_agent = Agent.objects.create(
            user=self.other_user,
            borlette=self.borlette,
            nom="Other Agent",
            code="AGT002",
        )
        
        # Create tirage
        self.tirage = Tirage.objects.create(
            borlette=self.borlette,
            nom="Midi",
            session_key="test-session-123",
            is_open=True,
        )
        
        # Create ticket
        self.ticket = Ticket.objects.create(
            borlette=self.borlette,
            agent=self.agent,
            tirage=self.tirage,
            boules=["34", "67"],
            mises_boules=[Decimal("50"), Decimal("50")],
            mariages=["34x67"],
            mises_mariages=[Decimal("25")],
            loto3=["789"],
            mises_loto3=[Decimal("10")],
            loto4=["1234"],
            mises_loto4=[Decimal("20")],
            options_loto4=[2],
            loto5=["12345"],
            mises_loto5=[Decimal("15")],
            options_loto5=[3],
            status=TicketStatus.PENDING,
        )
        
        # Create VOID ticket for rejection test
        self.void_ticket = Ticket.objects.create(
            borlette=self.borlette,
            agent=self.agent,
            tirage=self.tirage,
            boules=["11"],
            mises_boules=[Decimal("50")],
            status=TicketStatus.VOID,
        )
        
        # Create ticket belonging to other agent
        self.other_ticket = Ticket.objects.create(
            borlette=self.borlette,
            agent=self.other_agent,
            tirage=self.tirage,
            boules=["22"],
            mises_boules=[Decimal("50")],
            status=TicketStatus.PENDING,
        )

    def _get_auth_headers(self, agent):
        """Helper to get JWT auth headers for an agent"""
        # Mock JWT token validation
        return {"HTTP_AUTHORIZATION": f"Bearer mock-token-{agent.id}"}

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_blueprint_returns_correct_lines(self, mock_get_agent):
        """Blueprint should return all ticket lines with correct structure"""
        mock_get_agent.return_value = self.agent
        
        response = self.client.get(
            f"/api/agent/ticket/{self.ticket.id}/blueprint/",
            **self._get_auth_headers(self.agent)
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data["success"])
        self.assertEqual(data["ticket_id"], str(self.ticket.id))
        self.assertEqual(data["tirage_id"], self.tirage.id)
        self.assertEqual(data["session_key"], "test-session-123")
        
        lines = data["lines"]
        
        # Check boules
        boule_lines = [l for l in lines if l["jeu"] == "boule"]
        self.assertEqual(len(boule_lines), 2)
        self.assertEqual(boule_lines[0]["valeur"], "34")
        self.assertEqual(boule_lines[0]["mise"], 50.0)
        
        # Check mariages
        mariage_lines = [l for l in lines if l["jeu"] == "mariage"]
        self.assertEqual(len(mariage_lines), 1)
        self.assertEqual(mariage_lines[0]["valeur"], "34x67")
        self.assertEqual(mariage_lines[0]["mise"], 25.0)
        
        # Check loto3
        loto3_lines = [l for l in lines if l["jeu"] == "loto3"]
        self.assertEqual(len(loto3_lines), 1)
        self.assertEqual(loto3_lines[0]["valeur"], "789")
        
        # Check loto4 with option
        loto4_lines = [l for l in lines if l["jeu"] == "loto4"]
        self.assertEqual(len(loto4_lines), 1)
        self.assertEqual(loto4_lines[0]["valeur"], "1234")
        self.assertEqual(loto4_lines[0]["option"], 2)
        
        # Check loto5 with option
        loto5_lines = [l for l in lines if l["jeu"] == "loto5"]
        self.assertEqual(len(loto5_lines), 1)
        self.assertEqual(loto5_lines[0]["valeur"], "12345")
        self.assertEqual(loto5_lines[0]["option"], 3)

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_blueprint_refuses_void_ticket(self, mock_get_agent):
        """Blueprint should refuse VOID tickets"""
        mock_get_agent.return_value = self.agent
        
        response = self.client.get(
            f"/api/agent/ticket/{self.void_ticket.id}/blueprint/",
            **self._get_auth_headers(self.agent)
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("annulée", data["error"].lower())

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_blueprint_refuses_other_agent_ticket(self, mock_get_agent):
        """Blueprint should refuse tickets belonging to another agent"""
        mock_get_agent.return_value = self.agent
        
        response = self.client.get(
            f"/api/agent/ticket/{self.other_ticket.id}/blueprint/",
            **self._get_auth_headers(self.agent)
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data["success"])

    @patch('agent_portal.api_views._get_agent_from_request')
    def test_blueprint_nonexistent_ticket(self, mock_get_agent):
        """Blueprint should return 404 for non-existent ticket"""
        mock_get_agent.return_value = self.agent
        
        fake_uuid = str(uuid.uuid4())
        response = self.client.get(
            f"/api/agent/ticket/{fake_uuid}/blueprint/",
            **self._get_auth_headers(self.agent)
        )
        
        self.assertEqual(response.status_code, 404)

    def test_blueprint_requires_auth(self):
        """Blueprint should require authentication"""
        response = self.client.get(
            f"/api/agent/ticket/{self.ticket.id}/blueprint/"
        )
        
        self.assertEqual(response.status_code, 401)
