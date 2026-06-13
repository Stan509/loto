#!/usr/bin/env python
"""Script pour mettre à jour les noms d'utilisateur des admins."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import User, UserRole

print("\n" + "="*50)
print("MISE À JOUR DES NOMS D'UTILISATEUR")
print("="*50)

admins = User.objects.filter(role=UserRole.ADMIN)
print(f"\n📊 ADMINS TROUVÉS: {admins.count()}")

for admin in admins:
    print(f"\n   • Utilisateur actuel: {admin.username}")
    print(f"     Email: {admin.email}")
    
    # Générer un nom d'utilisateur à partir de l'email (avant le @)
    new_username = admin.email.split('@')[0] if admin.email else admin.username
    
    # Vérifier si le nom d'utilisateur est déjà pris
    if User.objects.filter(username=new_username).exclude(id=admin.id).exists():
        print(f"     ⚠️  Nom d'utilisateur '{new_username}' déjà pris, pas de modification")
        continue
    
    # Mettre à jour le nom d'utilisateur
    old_username = admin.username
    admin.username = new_username
    admin.save()
    print(f"     ✅ Mis à jour: {old_username} → {new_username}")

print("\n" + "="*50)
print("TERMINÉ")
print("="*50)
