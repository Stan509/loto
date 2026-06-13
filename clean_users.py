import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
django.setup()

from accounts.models import User, Borlette, Subscription, Agent, AffiliateProfile, PartnerProfile

# Get super user
super_users = User.objects.filter(is_superuser=True)
print(f"Super users found: {super_users.count()}")
for su in super_users:
    print(f"  - {su.username} (ID: {su.id})")

if not super_users.exists():
    print("WARNING: No super user found! Creating one...")
    User.objects.create_superuser(
        username='admin',
        email='admin@gaboom.com',
        password='admin123'
    )
    super_users = User.objects.filter(is_superuser=True)

# Keep only super users
super_user_ids = list(super_users.values_list('id', flat=True))
print(f"\nKeeping super user IDs: {super_user_ids}")

# Count users to delete
total_users = User.objects.count()
users_to_delete = User.objects.exclude(id__in=super_user_ids)
print(f"\nTotal users: {total_users}")
print(f"Users to delete: {users_to_delete.count()}")

# Delete related objects first
print("\nDeleting related objects...")
print(f"  - Agents: {Agent.objects.all().count()}")
Agent.objects.all().delete()

print(f"  - Subscriptions: {Subscription.objects.all().count()}")
Subscription.objects.all().delete()

print(f"  - Borlettes: {Borlette.objects.all().count()}")
Borlette.objects.all().delete()

print(f"  - Affiliate Profiles: {AffiliateProfile.objects.all().count()}")
AffiliateProfile.objects.all().delete()

print(f"  - Partner Profiles: {PartnerProfile.objects.all().count()}")
PartnerProfile.objects.all().delete()

# Delete users
print(f"\nDeleting {users_to_delete.count()} users...")
users_to_delete.delete()

# Verify
remaining_users = User.objects.all()
print(f"\n✅ Remaining users: {remaining_users.count()}")
for user in remaining_users:
    print(f"  - {user.username} (is_superuser: {user.is_superuser})")
