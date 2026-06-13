#!/usr/bin/env python
"""Diagnostic complet des borlettes et abonnements."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import Borlette, Subscription, User, UserRole, PartnerProfile

print("=" * 70)
print("DIAGNOSTIC COMPLET - BORLETTES ET DASHBOARD")
print("=" * 70)

# 1. Borlettes en base
borlettes = Borlette.objects.all()
print(f"\n📊 BORLETTES EN BASE: {borlettes.count()}")
for b in borlettes:
    admin = User.objects.filter(borlette=b, role=UserRole.ADMIN).first()
    print(f"   • ID:{b.id} | {b.nom_borlette} | Admin: {admin.username if admin else 'AUCUN'}")

# 2. Admins
admins = User.objects.filter(role=UserRole.ADMIN)
print(f"\n📊 ADMINS (DIRECTEURS): {admins.count()}")
for a in admins:
    b_name = a.borlette.nom_borlette if a.borlette else "SANS BORLETTE"
    print(f"   • {a.username} | Borlette: {b_name}")

# 3. Abonnements
subs = Subscription.objects.all()
print(f"\n📊 ABONNEMENTS: {subs.count()}")
for s in subs:
    status = "✅ Actif" if s.is_active else "❌ Inactif"
    print(f"   • {s.borlette.nom_borlette} | {s.user.username} | {s.subscription_type} | {status}")

# 4. Partenaires et leurs borlettes assignées
print(f"\n📊 PARTENAIRES:")
for p in PartnerProfile.objects.all():
    assigned = list(p.allowed_borlettes.all())
    print(f"   • {p.user.username}")
    print(f"     can_renew_subscriptions: {p.can_renew_subscriptions}")
    print(f"     borlettes assignees: {len(assigned)}")
    for b in assigned:
        print(f"       - {b.nom_borlette}")
    if not assigned:
        print(f"       ⚠️ AUCUNE BORLETTE ASSIGNEE - Devrait voir TOUTES les borlettes")

# 5. Résumé
print(f"\n" + "=" * 70)
print("RESUME POUR LE DASHBOARD:")
print(f"  • Borlettes totales: {borlettes.count()}")
print(f"  • Admins totaux: {admins.count()}")
print(f"  • Abonnements: {subs.count()}")
print(f"\nSi le partenaire n'a PAS de borlettes assignees:")
print(f"  → Il devrait voir {subs.count()} abonnement(s) sur le dashboard")
print(f"\nSi le partenaire A des borlettes assignees:")
assigned_count = PartnerProfile.objects.first().allowed_borlettes.count() if PartnerProfile.objects.exists() else 0
print(f"  → Il ne voit que les abonnements de ses {assigned_count} borlette(s) assignee(s)")
print("=" * 70)
