#!/usr/bin/env python
"""Create test subscription for debugging."""
import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import Subscription, Borlette, User, UserRole, PartnerProfile

print("="*60)
print("CREATION D'UN ABONNEMENT TEST")
print("="*60)

# Get first borlette
borlette = Borlette.objects.first()
if not borlette:
    print("❌ Aucune borlette trouvée!")
    exit(1)
print(f"✅ Borlette: {borlette.nom_borlette}")

# Get first admin
admin = User.objects.filter(role=UserRole.ADMIN).first()
if not admin:
    print("❌ Aucun admin trouvé!")
    exit(1)
print(f"✅ Admin: {admin.username}")

# Create subscription
sub, created = Subscription.objects.get_or_create(
    user=admin,
    borlette=borlette,
    defaults={
        'subscription_type': 'trial',
        'end_date': datetime.now().date() + timedelta(days=15),
        'is_active': True
    }
)
if created:
    print(f"✅ Abonnement créé: {sub}")
else:
    print(f"✅ Abonnement existant: {sub}")

# Enable permission for first partner
partner = PartnerProfile.objects.first()
if partner:
    partner.can_renew_subscriptions = True
    partner.save()
    print(f"✅ Permission activée pour: {partner.user.username}")
    # Assign all borlettes to partner
    partner.allowed_borlettes.set(Borlette.objects.all())
    print(f"✅ Borlettes assignées au partenaire")

print("\n" + "="*60)
print("RAFRAICHISSEZ LE DASHBOARD!")
print("="*60)
