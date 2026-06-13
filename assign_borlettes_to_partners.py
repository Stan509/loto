#!/usr/bin/env python
"""Assigner toutes les borlettes à tous les partenaires."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import Borlette, PartnerProfile

print("="*60)
print("ASSIGNATION DES BORLETTES AUX PARTENAIRES")
print("="*60)

# Récupérer toutes les borlettes
all_borlettes = Borlette.objects.all()
print(f"\n📊 Borlettes trouvées: {all_borlettes.count()}")
for b in all_borlettes:
    print(f"   • {b.nom_borlette}")

# Récupérer tous les partenaires
partners = PartnerProfile.objects.all()
print(f"\n📊 Partenaires trouvés: {partners.count()}")

if not all_borlettes:
    print("\n❌ ERREUR: Aucune borlette en base!")
    print("   Créez d'abord des borlettes via l'admin Django.")
    exit(1)

if not partners:
    print("\n❌ ERREUR: Aucun partenaire en base!")
    print("   Créez d'abord un partenaire.")
    exit(1)

# Assigner toutes les borlettes à chaque partenaire
print("\n" + "-"*60)
for partner in partners:
    print(f"\n👤 Partenaire: {partner.user.username}")
    
    # Assigner toutes les borlettes
    partner.allowed_borlettes.set(all_borlettes)
    
    count = partner.allowed_borlettes.count()
    print(f"   ✅ {count} borlette(s) assignée(s)")

print("\n" + "="*60)
print("✅ TERMINÉ!")
print("="*60)
print(f"\nToutes les {all_borlettes.count()} borlettes ont été assignées")
print(f"à {partners.count()} partenaire(s).")
print("\nRedémarrez le serveur et rafraîchissez le dashboard partenaire.")
