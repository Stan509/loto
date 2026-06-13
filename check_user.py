import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import User

# Check if user Gaboom exists
try:
    gaboom_user = User.objects.get(username='Gaboom')
    print(f"✅ User 'Gaboom' found:")
    print(f"  - ID: {gaboom_user.id}")
    print(f"  - Username: {gaboom_user.username}")
    print(f"  - Email: {gaboom_user.email}")
    print(f"  - Role: {gaboom_user.role}")
    print(f"  - Is active: {gaboom_user.is_active}")
    print(f"  - Is staff: {gaboom_user.is_staff}")
    print(f"  - Is superuser: {gaboom_user.is_superuser}")
    print(f"  - Has usable password: {gaboom_user.has_usable_password()}")
except User.DoesNotExist:
    print("❌ User 'Gaboom' NOT found in database")

# List all users
print("\n📋 All users in database:")
for user in User.objects.all():
    print(f"  - {user.username} (role: {user.role}, active: {user.is_active})")
