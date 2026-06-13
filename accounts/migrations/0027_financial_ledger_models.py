from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_borlette_agents_eligible_share"),
    ]

    operations = [
        migrations.CreateModel(
            name="FinancialTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(choices=[("activation", "Activation"), ("subscription", "Abonnement")], max_length=32)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("months_active", models.PositiveIntegerField(default=0)),
                ("agents_count", models.PositiveIntegerField(default=0)),
                ("eligible_agents", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "borlette",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="financial_transactions", to="accounts.borlette"),
                ),
                (
                    "promo_code",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounts.promocode"),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="FinancialSplit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("owner", "Owner"),
                            ("associate_1", "Associé 1"),
                            ("associate_2", "Associé 2"),
                            ("affiliate", "Affilié"),
                            ("cash", "Caisse"),
                        ],
                        max_length=32,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "transaction",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="splits", to="accounts.financialtransaction"),
                ),
                (
                    "user",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounts.user"),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="financialtransaction",
            index=models.Index(fields=["borlette", "created_at"], name="idx_ftx_borlette_ca"),
        ),
        migrations.AddIndex(
            model_name="financialtransaction",
            index=models.Index(fields=["borlette", "type", "created_at"], name="idx_ftx_borlette_ty"),
        ),
        migrations.AddIndex(
            model_name="financialsplit",
            index=models.Index(fields=["transaction", "role"], name="idx_fsplit_tx_role"),
        ),
        migrations.AddIndex(
            model_name="financialsplit",
            index=models.Index(fields=["user", "created_at"], name="idx_fsplit_user_ca"),
        ),
    ]
