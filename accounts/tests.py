from django.test import TestCase, Client
from django.urls import reverse
import json
from accounts.models import User, UserRole

class SignupVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_admin_signup_and_verify_code(self):
        # 1. Sign up
        payload = {
            "username": "directeur_test",
            "email": "dir@example.com",
            "phone": "+50933333333",
            "password": "securepassword123",
            "borlette_name": "Test Borlette",
            "adresse": "Port-au-Prince",
            "slogan": "The Best",
        }
        response = self.client.post(
            reverse("accounts_api:signup"),
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        
        # Verify user is created but inactive
        user = User.objects.get(username="directeur_test")
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.role, UserRole.ADMIN)
        
        # Get verification code
        code = user.email_verification_token
        self.assertTrue(code.isdigit())
        self.assertEqual(len(code), 6)

        # 2. Verify with wrong code
        verify_payload = {
            "username": "directeur_test",
            "code": "000000"
        }
        verify_response = self.client.post(
            reverse("accounts_api:signup_verify_code"),
            data=json.dumps(verify_payload),
            content_type="application/json"
        )
        self.assertEqual(verify_response.status_code, 400)
        self.assertFalse(verify_response.json()["success"])

        # 3. Verify with correct code
        verify_payload["code"] = code
        verify_response = self.client.post(
            reverse("accounts_api:signup_verify_code"),
            data=json.dumps(verify_payload),
            content_type="application/json"
        )
        self.assertEqual(verify_response.status_code, 200)
        verify_data = verify_response.json()
        self.assertTrue(verify_data["success"])
        self.assertEqual(verify_data["data"]["redirect_url"], "/portal/dashboard/")

        # Verify user is now active
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)
        self.assertIsNone(user.email_verification_token)
