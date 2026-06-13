from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_adminpaymentsettings_max_boule_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="TirageNumeroStats",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "numero",
                    models.CharField(
                        max_length=2,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^\\d{2}$", message="numero doit être au format 00 à 99"
                            )
                        ],
                    ),
                ),
                ("mises_total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("plafond_admin", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("bloque_auto", models.BooleanField(default=False)),
                ("bloque_admin", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tirage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="numero_stats",
                        to="accounts.tirage",
                    ),
                ),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="TirageCombiStats",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "jeu_type",
                    models.CharField(
                        choices=[
                            ("mariage", "Mariage"),
                            ("loto3", "Loto 3"),
                            ("loto4", "Loto 4"),
                            ("loto5", "Loto 5"),
                        ],
                        max_length=20,
                    ),
                ),
                ("valeur", models.CharField(max_length=10)),
                ("mises_total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("plafond_admin", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("bloque_auto", models.BooleanField(default=False)),
                ("bloque_admin", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tirage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="combi_stats",
                        to="accounts.tirage",
                    ),
                ),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name="tiragenumerostats",
            constraint=models.UniqueConstraint(fields=("tirage", "numero"), name="uniq_tirage_numero"),
        ),
        migrations.AddIndex(
            model_name="tiragenumerostats",
            index=models.Index(fields=["tirage", "numero"], name="idx_tirage_numero"),
        ),
        migrations.AddIndex(
            model_name="tiragenumerostats",
            index=models.Index(fields=["tirage", "bloque_auto"], name="idx_tirage_num_ba"),
        ),
        migrations.AddIndex(
            model_name="tiragenumerostats",
            index=models.Index(fields=["tirage", "bloque_admin"], name="idx_tirage_num_bm"),
        ),
        migrations.AddConstraint(
            model_name="tiragecombistats",
            constraint=models.UniqueConstraint(fields=("tirage", "jeu_type", "valeur"), name="uniq_tirage_combi"),
        ),
        migrations.AddIndex(
            model_name="tiragecombistats",
            index=models.Index(fields=["tirage", "jeu_type"], name="idx_tirage_combi_j"),
        ),
        migrations.AddIndex(
            model_name="tiragecombistats",
            index=models.Index(fields=["tirage", "jeu_type", "valeur"], name="idx_tirage_combi_v"),
        ),
        migrations.AddIndex(
            model_name="tiragecombistats",
            index=models.Index(fields=["tirage", "bloque_auto"], name="idx_tirage_com_ba"),
        ),
        migrations.AddIndex(
            model_name="tiragecombistats",
            index=models.Index(fields=["tirage", "bloque_admin"], name="idx_tirage_com_bm"),
        ),
    ]
