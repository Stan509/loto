from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_agent_last_seen_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='tirage',
            name='last_opened_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tirage',
            name='last_closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tirage',
            name='cached_state',
            field=models.CharField(blank=True, db_column='cached_state', default='', max_length=10),
        ),
    ]
