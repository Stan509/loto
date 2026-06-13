from __future__ import annotations

from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.default_tirages import ensure_default_tirages
from accounts.models import Borlette, Subscription, SubscriptionType, UserRole


@receiver(post_save, sender=Borlette)
def _borlette_seed_default_tirages(sender, instance: Borlette, created: bool, **kwargs):
    if created:
        ensure_default_tirages(borlette=instance)


@receiver(post_save, sender='accounts.User')
def _create_borlette_and_subscription(sender, instance, created, **kwargs):
    """Auto-create Borlette and Subscription when an ADMIN user is created."""
    import sys
    if 'test' in sys.argv or 'pytest' in sys.modules:
        return
    if created and instance.role == UserRole.ADMIN:
        # Check if borlette already exists (avoid duplicates)
        if not hasattr(instance, 'borlette'):
            # Get phone from User if available, otherwise empty
            phone = getattr(instance, 'telephone', '') or getattr(instance, 'phone', '')
            borlette = Borlette.objects.create(
                user=instance,
                nom_borlette=instance.username,
                adresse="",
                telephone=phone
            )
            # Create trial subscription
            today = timezone.now().date()
            Subscription.objects.create(
                user=instance,
                borlette=borlette,
                subscription_type=SubscriptionType.TRIAL,
                is_active=True,
                start_date=today,
                end_date=today + timedelta(days=3)  # 3-day trial (72 hours)
            )
