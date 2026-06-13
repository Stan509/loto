"""
One-time management command to create the superuser.
Run via: python manage.py create_superuser_prod
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import User

USERNAME = "GaboomAdmin"
PASSWORD = "H@cker509"

if User.objects.filter(username=USERNAME).exists():
    print(f"User '{USERNAME}' already exists — skipping.")
else:
    user = User.objects.create_superuser(
        username=USERNAME,
        password=PASSWORD,
        email="admin@gaboom.com",
        role="SUPER_ADMIN",
    )
    print(f"Superuser '{USERNAME}' created successfully!")
