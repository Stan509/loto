#!/usr/bin/env python
"""
Script pour lister toutes les borlettes avec leur username associé
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
sys.path.insert(0, 'c:\\Users\\Réginald\\Documents\\Gaboom Central')

django.setup()

from accounts.models import Borlette

print("=" * 80)
print("LISTE DES BORLETTES")
print("=" * 80)
print(f"{'ID':<5} {'Nom Borlette':<30} {'Username':<25} {'Téléphone':<20}")
print("-" * 80)

borlettes = Borlette.objects.select_related('user').all().order_by('nom_borlette')

if not borlettes:
    print("Aucune borlette trouvée.")
else:
    for b in borlettes:
        username = b.user.username if b.user else "N/A"
        print(f"{b.id:<5} {b.nom_borlette:<30} {username:<25} {b.telephone or 'N/A':<20}")

print("=" * 80)
print(f"Total: {borlettes.count()} borlette(s)")
print("=" * 80)
print("\nUtilisez le 'Username' pour vous connecter au portail.")
