from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from accounts.models import UserRole


class Command(BaseCommand):
    help = "Reset superadmin credentials to root@gaboom509 / H@cker509"

    def handle(self, *args, **options):
        User = get_user_model()

        su = User.objects.filter(is_superuser=True).order_by("id").first()

        if not su:
            su = User.objects.create_superuser(
                username="root@gaboom509",
                email="root@gaboom509",
                password="H@cker509",
                role=UserRole.SUPER_ADMIN
            )
            self.stdout.write(self.style.SUCCESS("Nouveau superadmin créé."))
        else:
            su.username = "root@gaboom509"
            su.email = "root@gaboom509"
            su.set_password("H@cker509")
            su.role = UserRole.SUPER_ADMIN
            su.save()
            self.stdout.write(self.style.SUCCESS("Superadmin existant mis à jour."))

        self.stdout.write(
            self.style.SUCCESS(f"Superadmin configuré : username={su.username} password=H@cker509")
        )

