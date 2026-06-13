#!/usr/bin/env python
"""List all admins in the system."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import User, UserRole, Subscription, Borlette

print("=" * 70)
print("LISTE DES ADMINS (DIRECTEURS DE BORLETTES)")
print("=" * 70)

admins = User.objects.filter(role=UserRole.ADMIN).order_by('username')

print(f"\n📊 TOTAL: {admins.count()} admins\n")

for i, admin in enumerate(admins, 1):
    borlette_name = admin.borlette.nom_borlette if admin.borlette else "AUCUNE BORLETTE"
    borlette_id = admin.borlette.id if admin.borlette else "N/A"
    
    # Check if admin has subscription
    subs = Subscription.objects.filter(user=admin)
    if subs.exists():
        sub = subs.first()
        sub_info = f"Abonnement: {sub.subscription_type} (expire: {sub.end_date})"
    else:
        sub_info = "PAS D'ABONNEMENT"
    
    print(f"{i}. {admin.username}")
    print(f"   Email: {admin.email or 'N/A'}")
    print(f"   Borlette: {borlette_name} (ID: {borlette_id})")
    print(f"   Status: {'Actif' if admin.is_active else 'Inactif'}")
    print(f"   {sub_info}")
    print()

# Summary by borlette
print("=" * 70)
print("ADMINS PAR BORLETTE:")
print("=" * 70)
for borlette in Borlette.objects.all():
    admin_count = User.objects.filter(borlette=borlette, role=UserRole.ADMIN).count()
    print(f"   • {borlette.nom_borlette}: {admin_count} admin(s)")

print("\n" + "=" * 70)
