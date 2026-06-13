#!/usr/bin/env python
"""Renew subscriptions for all admins to 30 days from today."""
import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import Subscription, User, UserRole, Borlette

print("=" * 70)
print("RENOUVELLEMENT DES ABONNEMENTS - TOUS LES ADMINS")
print("=" * 70)

# Get all admins
admins = User.objects.filter(role=UserRole.ADMIN)
print(f"\n📊 {admins.count()} admins trouvés\n")

# New end date (30 days from today)
new_end_date = datetime.now().date() + timedelta(days=30)
print(f"Nouvelle date d'expiration: {new_end_date}\n")

created_count = 0
updated_count = 0

for admin in admins:
    # Get or create subscription
    sub, created = Subscription.objects.get_or_create(
        user=admin,
        defaults={
            'borlette': admin.borlette or Borlette.objects.first(),
            'subscription_type': 'standard',
            'end_date': new_end_date,
            'is_active': True
        }
    )
    
    if created:
        print(f"✅ Créé: {admin.username} - expire le {new_end_date}")
        created_count += 1
    else:
        # Update existing subscription
        sub.end_date = new_end_date
        sub.is_active = True
        if sub.subscription_type == 'trial':
            sub.subscription_type = 'standard'  # Convert trial to standard
        sub.save()
        print(f"🔄 Renouvelé: {admin.username} - expire le {new_end_date}")
        updated_count += 1

print(f"\n" + "=" * 70)
print(f"RÉSULTAT:")
print(f"  • Abonnements créés: {created_count}")
print(f"  • Abonnements renouvelés: {updated_count}")
print(f"  • Total: {created_count + updated_count}")
print("=" * 70)
