"""
Tests for Admin Portal - Phase J: Mariage Risk Management
"""
import json
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from accounts.models import (
    Borlette,
    Tirage,
    TirageNumeroStats,
    MariageBlock,
    UserRole,
)

User = get_user_model()


class MariageBlockTests(TestCase):
    """Tests for Phase J - Mariage Risk Management"""

    def setUp(self):
        self.client = Client()
        
        # Create admin user with borlette
        self.admin_user = User.objects.create_user(
            username="testadmin",
            password="testpass123",
            role=UserRole.ADMIN,
        )
        self.borlette = Borlette.objects.create(
            user=self.admin_user,
            nom_borlette="Test Borlette",
            adresse="Test Address",
            telephone="12345678",
            slogan="Test Slogan",
        )
        
        # Create tirage
        self.tirage = Tirage.objects.create(
            borlette=self.borlette,
            nom="Midi",
            heure_ouverture="08:00",
            heure_fermeture="14:00",
            heure_tirage="15:00",
        )
        
        # Login
        self.client.login(username="testadmin", password="testpass123")
    
    def test_add_manual_mariage_block(self):
        """Test adding a manual mariage block"""
        response = self.client.post(
            f"/portal/api/tirages/{self.tirage.id}/mariage-blocks/add/",
            data=json.dumps({"combo": "44x30"}),
            content_type="application/json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["combo"], "30x44")  # Normalized
        
        # Verify in database
        self.assertTrue(MariageBlock.is_blocked(self.tirage.id, "44", "30"))
    
    def test_remove_manual_mariage_block(self):
        """Test removing a manual mariage block"""
        # First add a block
        MariageBlock.objects.create(
            tirage=self.tirage,
            boule_a=30,
            boule_b=44,
            created_by=self.admin_user
        )
        
        # Remove it
        response = self.client.delete(
            f"/portal/api/tirages/{self.tirage.id}/mariage-blocks/remove/?combo=44x30"
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        
        # Verify removed
        self.assertFalse(MariageBlock.is_blocked(self.tirage.id, "44", "30"))
    
    def test_list_mariage_blocks(self):
        """Test listing mariage blocks (manual and auto)"""
        # Add manual block
        MariageBlock.objects.create(
            tirage=self.tirage,
            boule_a=12,
            boule_b=33,
            created_by=self.admin_user
        )
        
        # Add blocked boules for auto-derivation
        TirageNumeroStats.objects.create(
            tirage=self.tirage,
            numero="44",
            bloque_admin=True
        )
        TirageNumeroStats.objects.create(
            tirage=self.tirage,
            numero="33",
            bloque_admin=True
        )
        
        response = self.client.get(
            f"/portal/api/tirages/{self.tirage.id}/mariage-blocks/"
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data["success"])
        self.assertIn("manual", data)
        self.assertIn("auto", data)
        self.assertIn("all", data)
        
        # Check manual includes our block
        self.assertIn("12x33", data["manual"])
        
        # Check auto includes derived blocks (44x33, 33x44)
        self.assertIn("33x44", data["auto"])
    
    def test_duplicate_manual_block_rejected(self):
        """Test that duplicate manual blocks are rejected"""
        # Add first block
        MariageBlock.objects.create(
            tirage=self.tirage,
            boule_a=30,
            boule_b=44,
            created_by=self.admin_user
        )
        
        # Try to add again
        response = self.client.post(
            f"/portal/api/tirages/{self.tirage.id}/mariage-blocks/add/",
            data=json.dumps({"combo": "44x30"}),
            content_type="application/json",
        )
        
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertFalse(data["success"])
    
    def test_auto_blocks_calculated_from_boules(self):
        """Test that auto blocks are calculated from blocked boules"""
        # Block boules 44, 33, 30
        for num in ["44", "33", "30"]:
            TirageNumeroStats.objects.create(
                tirage=self.tirage,
                numero=num,
                bloque_admin=True
            )
        
        # Should generate 3 combinations
        from admin_portal.mariage_risk_api import _get_auto_mariage_blocks
        auto_blocks = _get_auto_mariage_blocks(self.tirage.id)
        
        # 3C2 = 3 combinations (normalized a < b)
        self.assertEqual(len(auto_blocks), 3)
        
        # Check specific pairs exist (normalized)
        self.assertIn(("30", "33"), auto_blocks)
        self.assertIn(("30", "44"), auto_blocks)
        self.assertIn(("33", "44"), auto_blocks)
    
    def test_ticket_validation_blocks_mariage(self):
        """Test that ticket validation rejects blocked mariages"""
        from core.services.ticket_validation_service import TicketValidationService
        
        # Add a manual block
        MariageBlock.objects.create(
            tirage=self.tirage,
            boule_a=30,
            boule_b=44,
            created_by=self.admin_user
        )
        
        # Try to validate a ticket with blocked mariage
        result = TicketValidationService.validate_ticket(
            admin=self.admin_user,
            agent=None,  # Will fail due to agent check
            ticket_lines=[{"game": "mariage", "value": "44x30", "stake": 50}],
            draw_ids=[self.tirage.id]
        )
        
        # Should fail (either due to agent or mariage block)
        self.assertFalse(result["is_valid"])
    
    def test_ticket_validation_blocks_auto_mariage(self):
        """Test that ticket validation rejects auto-derived mariages"""
        from core.services.ticket_validation_service import TicketValidationService
        
        # Block boules to trigger auto-derivation
        TirageNumeroStats.objects.create(
            tirage=self.tirage,
            numero="44",
            bloque_admin=True
        )
        TirageNumeroStats.objects.create(
            tirage=self.tirage,
            numero="33",
            bloque_admin=True
        )
        
        # Check that 44x33 is auto-blocked
        is_blocked, source = TicketValidationService._is_mariage_blocked(
            [self.tirage.id], "44x33"
        )
        self.assertTrue(is_blocked)
        self.assertEqual(source, "AUTO")
