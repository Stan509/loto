from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0020_seed_more_default_tirages"),
    ]

    operations = [
        migrations.AddField(
            model_name="resultat",
            name="source",
            field=models.CharField(default="API", max_length=50),
        ),
        migrations.AddField(
            model_name="resultat",
            name="statut",
            field=models.CharField(
                choices=[
                    ("pending", "En attente"),
                    ("validated", "Validé"),
                    ("rejected", "Rejeté"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="resultat",
            name="is_suspicious",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="resultat",
            name="validated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="resultat",
            name="validated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="validated_resultats",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="resultat",
            name="rejected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="resultat",
            name="rejected_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rejected_resultats",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="resultat",
            constraint=models.UniqueConstraint(fields=("tirage", "date"), name="uniq_resultat_tirage_date"),
        ),
    ]
