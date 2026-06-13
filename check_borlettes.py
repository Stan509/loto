#!/usr/bin/env python
"""Simple check for borlettes and subscriptions."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import Borlette, Subscription, User, UserRole, PartnerProfile

print("\n" + "="*50)
print("VERIFICATION DES DONNEES")
print("="*50)

# Borlettes
borlettes = Borlette.objects.all()
print(f"\n📊 BORLETTES: {borlettes.count()}")
if borlettes:
    for b in borlettes[:5]:
        print(f"   • {b.nom_borlette} (ID: {b.id})")
else:
    print("   ❌ AUCUNE BORLETTE TROUVEE!")

# Subscriptions
subs = Subscription.objects.all()
print(f"\n📊 ABONNEMENTS: {subs.count()}")
if subs:
    for s in subs.select_related('borlette', 'user')[:5]:
        status = "✅" if s.is_active else "❌"
        print(f"   {status} {s.borlette.nom_borlette} | {s.user.username} | Expire: {s.end_date}")
else:
    print("   ❌ AUCUN ABONNEMENT!")

# Admins
admins = User.objects.filter(role=UserRole.ADMIN)
print(f"\n📊 ADMINS: {admins.count()}")
for a in admins[:5]:
    print(f"   • {a.username}")

# Partners
partners = PartnerProfile.objects.all()
print(f"\n📊 PARTENAIRES: {partners.count()}")
for p in partners:
    print(f"   • {p.user.username}")
    borlettes_list = list(p.allowed_borlettes.all())
    if borlettes_list:
        print(f"     Borlettes assignees: {len(borlettes_list)}")
        for b in borlettes_list[:3]:
            print(f"       - {b.nom_borlette}")
    else:
        print(f"     ⚠️  AUCUNE BORLETTE ASSIGNÉE!")

print("\n" + "="*50)
