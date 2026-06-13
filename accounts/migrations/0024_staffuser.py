from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0023_lottery_api_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("manager", "Manager"), ("finance", "Finance"), ("operator", "Opérateur")], max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("can_view_dashboard", models.BooleanField(default=True)),
                ("can_manage_agents", models.BooleanField(default=False)),
                ("can_manage_results", models.BooleanField(default=False)),
                ("can_view_finance", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "borlette",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff_users", to="accounts.borlette"),
                ),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="staffuser", to="accounts.user"),
                ),
            ],
        ),
    ]
