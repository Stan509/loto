from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_resultat_complementaire"),
    ]

    operations = [
        migrations.CreateModel(
            name="LotteryAPIConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("api_url", models.URLField()),
                ("api_key", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
