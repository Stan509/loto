from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0021_resultat_validation_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="resultat",
            name="complementaire",
            field=models.CharField(blank=True, default="", max_length=1),
        ),
    ]
