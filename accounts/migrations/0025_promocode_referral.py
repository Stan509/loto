from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_staffuser"),
    ]

    operations = [
        migrations.CreateModel(
            name="PromoCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("commission_percent", models.IntegerField(default=10)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "owner",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.user"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Referral",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "new_user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.user"),
                ),
                (
                    "promo",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.promocode"),
                ),
            ],
        ),
    ]
