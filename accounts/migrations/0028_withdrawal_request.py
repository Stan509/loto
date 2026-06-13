from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0027_financial_ledger_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="WithdrawalRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("approved", "Approuvé"),
                            ("rejected", "Refusé"),
                            ("paid", "Payé"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("payment_method", models.CharField(blank=True, default="", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="withdrawal_requests", to="accounts.user"),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="withdrawalrequest",
            index=models.Index(fields=["user", "created_at"], name="idx_withdraw_user_ca"),
        ),
        migrations.AddIndex(
            model_name="withdrawalrequest",
            index=models.Index(fields=["status", "created_at"], name="idx_withdraw_status"),
        ),
    ]
