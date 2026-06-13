import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import User, Borlette

# Check user gaboom.hti
try:
    gaboom_user = User.objects.get(username='gaboom.hti')
    print(f"✅ User 'gaboom.hti' found:")
    print(f"  - ID: {gaboom_user.id}")
    print(f"  - Username: {gaboom_user.username}")
    print(f"  - Email: {gaboom_user.email}")
    print(f"  - Role: {gaboom_user.role}")
    
    # Check if user has a borlette
    borlette = Borlette.objects.filter(user=gaboom_user).first()
    if borlette:
        print(f"\n✅ Borlette associated:")
        print(f"  - Name: {borlette.nom_borlette}")
        print(f"  - Telephone: {borlette.telephone}")
        print(f"  - Address: {borlette.adresse}")
    else:
        print(f"\n❌ No borlette associated with this user")
except User.DoesNotExist:
    print("❌ User 'gaboom.hti' NOT found")

# Check all borlettes
print("\n📋 All borlettes in database:")
for borlette in Borlette.objects.all():
    print(f"  - {borlette.nom_borlette} (user: {borlette.user.username if borlette.user else 'None'})")
