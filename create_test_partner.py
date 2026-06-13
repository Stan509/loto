"""Script to create a test partner for testing the partner dashboard."""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'centralborlette.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import User, UserRole, PartnerProfile, Borlette


def create_test_partner():
    """Create a test partner with all permissions."""
    
    # Check if partner already exists
    if User.objects.filter(username='test_partner').exists():
        print("Partner 'test_partner' already exists. Resetting password...")
        user = User.objects.get(username='test_partner')
        user.set_password('test123')
        user.save()
        print(f"Partner URL: /partner/dashboard/")
        print(f"Login: test_partner")
        print(f"Password: test123")
        return
    
    # Create partner user
    user = User.objects.create_user(
        username='test_partner',
        email='partner@test.com',
        password='test123',
        first_name='Test',
        last_name='Partner',
        role=UserRole.PARTNER,
    )
    
    # Create partner profile with all permissions
    partner_profile = PartnerProfile.objects.create(
        user=user,
        can_submit_results=True,
        can_confirm_affiliate_payments=True,
        can_renew_subscriptions=True,
    )
    
    # Give access to all borlettes (empty = all)
    # Or you can specify specific borlettes:
    # partner_profile.allowed_borlettes.set(Borlette.objects.filter(is_active=True))
    
    print("=" * 50)
    print("✓ Test Partner Created Successfully!")
    print("=" * 50)
    print()
    print("Connection Details:")
    print(f"  URL: /partner/dashboard/")
    print(f"  Username: test_partner")
    print(f"  Password: test123")
    print()
    print("Permissions:")
    print("  ✓ Can submit tirage results")
    print("  ✓ Can confirm affiliate payments")
    print("  ✓ Can renew director subscriptions")
    print()
    print("Access:")
    print("  → All borlettes (no restrictions)")
    print()
    print("=" * 50)


if __name__ == '__main__':
    create_test_partner()
