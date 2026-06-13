#!/usr/bin/env python
"""Debug script to check data."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import Subscription, Borlette, PartnerProfile

print("=" * 60)
print("VERIFICATION DES DONNEES")
print("=" * 60)

print(f"\n📊 Borlettes: {Borlette.objects.count()}")
for b in Borlette.objects.all():
    print(f"   - {b.nom_borlette}")

print(f"\n📊 Abonnements: {Subscription.objects.count()}")
for s in Subscription.objects.all():
    print(f"   - {s.borlette.nom_borlette} | {s.user.username} | {s.subscription_type} | Actif:{s.is_active}")

print(f"\n📊 Partenaires: {PartnerProfile.objects.count()}")
for p in PartnerProfile.objects.all():
    print(f"   - {p.user.username}")
    print(f"     Borlettes assignees: {list(p.allowed_borlettes.all())}")

print("\n" + "=" * 60)
if Subscription.objects.count() == 0:
    print("⚠️  AUCUN ABONNEMENT TROUVE!")
    print("   La section 'Borlettes Inscrites' sera vide.")
    print("   Creez des abonnements via l'admin Django.")
else:
    print("✅ Des abonnements existent.")
    print("   Si vous ne les voyez pas, videz le cache (Ctrl+F5)")
print("=" * 60)
