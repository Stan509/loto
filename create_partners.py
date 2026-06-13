import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import User, UserRole, PartnerProfile

# Create partner 1: Blancko-G
try:
    blancko = User.objects.create_user(
        username='Blancko-G',
        email='blancko@gaboom.com',
        password='partner123',
        role=UserRole.PARTNER,
        is_active=True
    )
    # Create partner profile
    PartnerProfile.objects.create(
        user=blancko,
        can_submit_results=True,
        can_confirm_affiliate_payments=True,
        can_renew_subscriptions=True
    )
    print(f"✅ Partner 'Blancko-G' created successfully")
except Exception as e:
    print(f"❌ Error creating Blancko-G: {e}")

# Create partner 2: Jhonny-DG
try:
    jhonny = User.objects.create_user(
        username='Jhonny-DG',
        email='jhonny@gaboom.com',
        password='partner123',
        role=UserRole.PARTNER,
        is_active=True
    )
    # Create partner profile
    PartnerProfile.objects.create(
        user=jhonny,
        can_submit_results=True,
        can_confirm_affiliate_payments=True,
        can_renew_subscriptions=True
    )
    print(f"✅ Partner 'Jhonny-DG' created successfully")
except Exception as e:
    print(f"❌ Error creating Jhonny-DG: {e}")

# Verify
print("\n📋 All partners:")
partners = User.objects.filter(role=UserRole.PARTNER)
for p in partners:
    print(f"  - {p.username} ({p.email})")
