#!/usr/bin/env python
"""
Script pour créer un agent de test pour l'admin Gaboom
"""
import os
import sys

# Add the project directory to Python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Agent, Borlette, AgentStatus, UserRole

User = get_user_model()

def create_test_agent():
    # 1. Créer l'utilisateur admin Gaboom s'il n'existe pas
    admin_user, created = User.objects.get_or_create(
        username='gaboom_admin',
        defaults={
            'first_name': 'Gaboom',
            'last_name': 'Admin',
            'email': 'admin@gaboom.com',
            'role': UserRole.ADMIN,
            'is_active': True
        }
    )
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        print(f"✅ Admin créé: {admin_user.username} / mot de passe: admin123")
    else:
        print(f"ℹ️ Admin existe déjà: {admin_user.username}")
    
    # 2. Créer la Borlette (entreprise)
    borlette, created = Borlette.objects.get_or_create(
        nom_borlette='Gaboom Central',
        defaults={
            'user': admin_user,
            'adresse': 'Port-au-Prince, Haïti',
            'telephone': '50912345678',
            'slogan': 'Le futur est à vous!',
            'allow_offline_print': True
        }
    )
    if created:
        print(f"✅ Borlette créée: {borlette.nom_borlette}")
    else:
        print(f"ℹ️ Borlette existe déjà: {borlette.nom_borlette}")
    
    # 3. Créer l'utilisateur agent
    agent_user, created = User.objects.get_or_create(
        username='agent_test',
        defaults={
            'first_name': 'Agent',
            'last_name': 'Test',
            'email': 'agent@test.com',
            'role': UserRole.AGENT,
            'is_active': True
        }
    )
    if created:
        agent_user.set_password('agent123')
        agent_user.save()
        print(f"✅ Utilisateur agent créé: {agent_user.username} / mot de passe: agent123")
    else:
        print(f"ℹ️ Utilisateur agent existe déjà: {agent_user.username}")
    
    # 4. Créer le profil Agent
    agent, created = Agent.objects.get_or_create(
        user=agent_user,
        defaults={
            'borlette': borlette,
            'nom': 'Agent Test Gaboom',
            'telephone': '50987654321',
            'zone': 'Port-au-Prince Centre',
            'statut': AgentStatus.ACTIF,
            'commission': 10.00
        }
    )
    if created:
        print(f"✅ Profil agent créé: {agent.nom}")
    else:
        print(f"ℹ️ Profil agent existe déjà: {agent.nom}")
    
    print("\n" + "="*60)
    print("🔑 IDENTIFIANTS DE CONNEXION POUR L'APP:")
    print("="*60)
    print(f"Username: {agent_user.username}")
    print(f"Password: agent123")
    print(f"Nom: {agent.nom}")
    print(f"Borlette: {borlette.nom_borlette}")
    print("="*60)

if __name__ == "__main__":
    create_test_agent()
