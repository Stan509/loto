from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_tirage_risk_stats'),
    ]

    operations = [
        migrations.AddField(
            model_name='tiragecombistats',
            name='bloque_derived',
            field=models.BooleanField(default=False),
        ),
    ]
