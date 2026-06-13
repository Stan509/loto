from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reset password of the first superadmin (safe, no username change)"

    def handle(self, *args, **options):
        User = get_user_model()

        su = User.objects.filter(is_superuser=True).order_by("id").first()

        if not su:
            self.stdout.write(self.style.ERROR("Aucun superadmin trouvé"))
            return

        su.set_password("admin1234")
        su.save(update_fields=["password"])

        self.stdout.write(
            self.style.SUCCESS(f"Superadmin reset OK : username={su.username} password=admin1234")
        )
