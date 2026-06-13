#!/usr/bin/env python
"""Script to check database for borlettes and subscriptions."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import Borlette, Subscription, User, UserRole

print("=== VÉRIFICATION DES DONNÉES ===\n")

# Check Borlettes
borlettes = Borlette.objects.all()
print(f"📊 Borlettes en base: {borlettes.count()}")
for b in borlettes:
    print(f"   - {b.nom_borlette} (ID: {b.id})")

print()

# Check Subscriptions
subs = Subscription.objects.all().select_related('borlette', 'user')
print(f"📊 Abonnements en base: {subs.count()}")
for s in subs:
    status = "Actif" if s.is_active else "Inactif"
    print(f"   - {s.borlette.nom_borlette} | Admin: {s.user.username} | Expire: {s.end_date} | {status}")

print()

# Check Admin users
admins = User.objects.filter(role=UserRole.ADMIN)
print(f"📊 Admins en base: {admins.count()}")
for a in admins:
    print(f"   - {a.username} (ID: {a.id})")

print()

# Check Affiliate users
affiliates = User.objects.filter(role=UserRole.AFFILIATE)
print(f"📊 Affiliés en base: {affiliates.count()}")
for af in affiliates:
    print(f"   - {af.username}")

print()

# Check Tirages
from accounts.models import Tirage
tirages = Tirage.objects.all()
print(f"📊 Tirages en base: {tirages.count()}")
for t in tirages:
    print(f"   - {t.nom} | Borlette: {t.borlette.nom_borlette if t.borlette else 'N/A'} | {t.heure_tirage}")
