from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_agent_payout_updates'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='last_seen_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
