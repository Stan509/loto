import uuid

from django.db import migrations, models


def _parse_time(v: str):
    from datetime import datetime

    return datetime.strptime(v, "%H:%M").time()


DEFAULT_TIRAGES = [
    {
        "nom": "New York Midi",
        "code": "NY_MIDI",
        "heure_tirage": "14:15",
        "heure_ouverture": "08:00",
        "heure_fermeture": "14:00",
        "pays": "USA",
        "ville": "New York",
    },
    {
        "nom": "New York Soir",
        "code": "NY_SOIR",
        "heure_tirage": "22:20",
        "heure_ouverture": "08:00",
        "heure_fermeture": "22:00",
        "pays": "USA",
        "ville": "New York",
    },
    {
        "nom": "Florida Midi",
        "code": "FL_MIDI",
        "heure_tirage": "13:30",
        "heure_ouverture": "08:00",
        "heure_fermeture": "13:15",
        "pays": "USA",
        "ville": "Florida",
    },
    {
        "nom": "Florida Soir",
        "code": "FL_SOIR",
        "heure_tirage": "21:45",
        "heure_ouverture": "08:00",
        "heure_fermeture": "21:30",
        "pays": "USA",
        "ville": "Florida",
    },
    {
        "nom": "Georgia Night",
        "code": "GA_NIGHT",
        "heure_tirage": "23:59",
        "heure_ouverture": "08:00",
        "heure_fermeture": "23:45",
        "pays": "USA",
        "ville": "Georgia",
    },
]


def backfill_codes_and_seed_defaults(apps, schema_editor):
    Tirage = apps.get_model("accounts", "Tirage")
    Borlette = apps.get_model("accounts", "Borlette")

    # Ensure existing tirages have a non-empty unique code per borlette (needed for unique constraint).
    for t in Tirage.objects.all().only("id", "borlette_id", "nom", "code"):
        if (t.code or "").strip():
            continue
        t.code = f"LEGACY_{t.borlette_id}_{t.id}_{uuid.uuid4().hex[:6].upper()}"
        t.save(update_fields=["code"])

    # Seed defaults for existing borlettes (idempotent).
    for b in Borlette.objects.all().only("id"):
        existing = set(
            Tirage.objects.filter(borlette_id=b.id)
            .exclude(code="")
            .values_list("code", flat=True)
        )
        for spec in DEFAULT_TIRAGES:
            if spec["code"] in existing:
                continue
            Tirage.objects.create(
                borlette_id=b.id,
                nom=spec["nom"],
                code=spec["code"],
                pays=spec.get("pays") or "USA",
                ville=spec.get("ville") or "",
                heure_tirage=_parse_time(spec["heure_tirage"]),
                heure_ouverture=_parse_time(spec["heure_ouverture"]),
                heure_fermeture=_parse_time(spec["heure_fermeture"]),
                is_default=True,
                modifiable=True,
                source_api_locked=True,
                statut="ACTIF",
                fermeture_auto=True,
                jours_actifs=[],
                ordre_affichage=0,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_tirage_mariage_automatique'),
    ]

    operations = [
        migrations.AddField(
            model_name='tirage',
            name='code',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='tirage',
            name='pays',
            field=models.CharField(default='USA', max_length=50),
        ),
        migrations.AddField(
            model_name='tirage',
            name='ville',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='tirage',
            name='is_default',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tirage',
            name='modifiable',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='tirage',
            name='source_api_locked',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='tirage',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='tirages_logos/'),
        ),
        migrations.RunPython(backfill_codes_and_seed_defaults, reverse_code=migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='tirage',
            constraint=models.UniqueConstraint(fields=('borlette', 'code'), name='uniq_tirage_code_per_borlette'),
        ),
    ]
