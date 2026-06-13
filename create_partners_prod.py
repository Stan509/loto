"""
One-time script to create the required partners.
Run via: python create_partners_prod.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import UserRole, PartnerProfile

User = get_user_model()

PARTNERS = [
    {"username": "BlancoPartner", "password": "Blanco@gaboom", "email": "blanco@gaboom.com"},
    {"username": "JhonnyPartner", "password": "Jhonny@gaboom", "email": "jhonny@gaboom.com"},
]

for pdata in PARTNERS:
    username = pdata["username"]
    password = pdata["password"]
    email = pdata["email"]

    if User.objects.filter(username=username).exists():
        print(f"User '{username}' already exists — skipping.")
    else:
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            role=UserRole.PARTNER,
        )
        # Create partner profile with all permissions enabled
        PartnerProfile.objects.create(
            user=user,
            can_submit_results=True,
            can_confirm_affiliate_payments=True,
            can_renew_subscriptions=True,
        )
        print(f"Partner '{username}' created successfully!")
