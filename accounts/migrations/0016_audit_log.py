import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_tirage_scheduler_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("action", models.CharField(max_length=64)),
                ("entity_type", models.CharField(max_length=64)),
                ("entity_id", models.CharField(max_length=128)),
                ("meta", models.JSONField(default=dict, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor_agent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="accounts.agent",
                    ),
                ),
                (
                    "actor_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "borlette",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="accounts.borlette",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["borlette", "created_at"], name="idx_audit_borlette_ca"),
                    models.Index(fields=["action", "created_at"], name="idx_audit_action_ca"),
                    models.Index(fields=["entity_type", "entity_id"], name="idx_audit_entity"),
                ],
            },
        ),
    ]
