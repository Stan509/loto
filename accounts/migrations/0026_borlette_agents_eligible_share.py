from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_promocode_referral"),
    ]

    operations = [
        migrations.AddField(
            model_name="borlette",
            name="agents_eligible_share",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Nombre d'agents pris en compte dans la répartition des revenus.",
                verbose_name="Agents comptabilisés pour partage",
            ),
        ),
    ]
