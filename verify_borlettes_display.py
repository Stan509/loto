#!/usr/bin/env python
"""Verify if all borlettes are displayed on partner dashboard."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import Borlette, Subscription, User, UserRole, PartnerProfile

print("=" * 70)
print("VERIFICATION DES BORLETTES SUR LE DASHBOARD PARTENAIRE")
print("=" * 70)

# 1. Count all borlettes
borlettes = Borlette.objects.all()
print(f"\n📊 TOTAL BORLETTES EN BASE: {borlettes.count()}")
for b in borlettes:
    admin = User.objects.filter(borlette=b, role=UserRole.ADMIN).first()
    admin_name = admin.username if admin else "AUCUN ADMIN"
    print(f"   • {b.nom_borlette} (ID: {b.id}) - Admin: {admin_name}")

# 2. Count all admins (directors)
admins = User.objects.filter(role=UserRole.ADMIN)
print(f"\n📊 TOTAL ADMINS (DIRECTEURS): {admins.count()}")
for a in admins:
    borlette_name = a.borlette.nom_borlette if a.borlette else "AUCUNE BORLETTE"
    print(f"   • {a.username} - Borlette: {borlette_name}")

# 3. Count subscriptions
subscriptions = Subscription.objects.all()
print(f"\n📊 TOTAL ABONNEMENTS: {subscriptions.count()}")
for s in subscriptions:
    print(f"   • {s.borlette.nom_borlette} | {s.user.username} | Type: {s.subscription_type} | Actif: {s.is_active}")

# 4. Check partner assignments
partners = PartnerProfile.objects.all()
print(f"\n📊 PARTENAIRES ET LEURS BORLETTES ASSIGNEES:")
for p in partners:
    assigned = p.allowed_borlettes.all()
    print(f"   • {p.user.username}: {assigned.count()} borlette(s) assignée(s)")
    for b in assigned:
        print(f"     - {b.nom_borlette}")

# 5. Missing subscriptions (admins without subscriptions)
print(f"\n📊 ADMINS SANS ABONNEMENT:")
for admin in admins:
    has_subscription = Subscription.objects.filter(user=admin).exists()
    if not has_subscription:
        print(f"   ⚠️  {admin.username} ({admin.borlette.nom_borlette if admin.borlette else 'sans borlette'}) - PAS D'ABONNEMENT")

# 6. Summary
print(f"\n" + "=" * 70)
print("RESUME:")
print(f"  - Borlettes en base: {borlettes.count()}")
print(f"  - Admins en base: {admins.count()}")
print(f"  - Abonnements actifs: {subscriptions.filter(is_active=True).count()}")
print(f"  - Abonnements inactifs: {subscriptions.filter(is_active=False).count()}")
print(f"\nSi le dashboard ne montre pas {subscriptions.count()} abonnements,")
print("c'est qu'il y a un probleme de filtrage dans la vue partner_dashboard.")
print("=" * 70)
