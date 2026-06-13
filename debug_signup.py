#!/usr/bin/env python
"""
Script pour tester l'API d'inscription et voir les erreurs exactes
"""
import os
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
sys.path.insert(0, 'c:\\Users\\Réginald\\Documents\\Gaboom Central')

import django
django.setup()

import json
from django.test import Client
from accounts.models import User, Borlette

# Nettoyer d'abord si l'utilisateur existe déjà
try:
    existing = User.objects.filter(username='test_debug_final').first()
    if existing:
        existing.delete()
        print("✓ Ancien utilisateur de test supprimé")
except:
    pass

# Test avec des données complètes
client = Client()
data = {
    'username': 'test_debug_final',
    'email': 'testfinal@example.com',
    'phone': '+50912345678',
    'borlette_name': 'Final Test Borlette',
    'adresse': 'Delmas, Port-au-Prince',
    'slogan': 'La borlette de confiance',
    'password': 'testpassword123',
    'promo_code': ''
}

print("="*60)
print("TEST INSCRIPTION BORLETTE")
print("="*60)
print(f"\nDonnées envoyées: {json.dumps(data, indent=2)}")

try:
    response = client.post('/api/signup/', json.dumps(data), content_type='application/json')
    print(f"\nStatus: {response.status_code}")
    print(f"Response: {response.content.decode()}")
    
    # Parser la réponse
    result = json.loads(response.content.decode())
    
    if result.get('success'):
        print("\n✅ INSCRIPTION RÉUSSIE!")
        print(f"User créé: {data['username']}")
        print(f"Borlette créée: {data['borlette_name']}")
        
        # Vérifier que l'utilisateur existe
        user = User.objects.filter(username='test_debug_final').first()
        if user:
            print(f"✓ User trouvé en base: {user.username}")
            print(f"✓ Role: {user.role}")
            
            # Vérifier la borlette
            if hasattr(user, 'borlette'):
                print(f"✓ Borlette associée: {user.borlette.nom_borlette}")
            else:
                print("❌ PAS DE BORLETTE ASSOCIÉE!")
        else:
            print("❌ USER NON TROUVÉ EN BASE!")
    else:
        print(f"\n❌ ERREUR: {result.get('message', 'Message inconnu')}")
        print(f"Erreur complète: {result}")
        
except Exception as e:
    print(f"\n❌ EXCEPTION: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("="*60)
