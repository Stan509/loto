from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reset password of a specific user (safe, no username change)"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", default="admin1234")

    def handle(self, *args, **options):
        username = (options.get("username") or "").strip()
        password = options.get("password") or "admin1234"

        if not username:
            self.stdout.write(self.style.ERROR("Username requis"))
            return

        User = get_user_model()
        u = User.objects.filter(username=username).first()
        if not u:
            self.stdout.write(self.style.ERROR(f"Utilisateur introuvable: {username}"))
            return

        u.set_password(password)
        u.save(update_fields=["password"])

        self.stdout.write(self.style.SUCCESS(f"Password reset OK : username={u.username} password={password}"))
