from __future__ import annotations

from django.db import migrations


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
        "nom": "Georgia Midi",
        "code": "GA_MIDI",
        "heure_tirage": "13:00",
        "heure_ouverture": "08:00",
        "heure_fermeture": "12:45",
        "pays": "USA",
        "ville": "Georgia",
    },
    {
        "nom": "Georgia 5PM",
        "code": "GA_5PM",
        "heure_tirage": "17:00",
        "heure_ouverture": "08:00",
        "heure_fermeture": "16:45",
        "pays": "USA",
        "ville": "Georgia",
    },
    {
        "nom": "Georgia 8PM",
        "code": "GA_8PM",
        "heure_tirage": "20:00",
        "heure_ouverture": "08:00",
        "heure_fermeture": "19:45",
        "pays": "USA",
        "ville": "Georgia",
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
    {
        "nom": "Tennessee Matin",
        "code": "TN_MATIN",
        "heure_tirage": "09:08",
        "heure_ouverture": "08:00",
        "heure_fermeture": "08:50",
        "pays": "USA",
        "ville": "Tennessee",
    },
    {
        "nom": "Tennessee Midi",
        "code": "TN_MIDI",
        "heure_tirage": "12:08",
        "heure_ouverture": "08:00",
        "heure_fermeture": "11:50",
        "pays": "USA",
        "ville": "Tennessee",
    },
    {
        "nom": "Tennessee Soir",
        "code": "TN_SOIR",
        "heure_tirage": "18:08",
        "heure_ouverture": "08:00",
        "heure_fermeture": "17:50",
        "pays": "USA",
        "ville": "Tennessee",
    },
    {
        "nom": "Chicago Midi",
        "code": "CHI_MIDI",
        "heure_tirage": "12:40",
        "heure_ouverture": "08:00",
        "heure_fermeture": "12:25",
        "pays": "USA",
        "ville": "Chicago",
    },
    {
        "nom": "Chicago Soir",
        "code": "CHI_SOIR",
        "heure_tirage": "21:20",
        "heure_ouverture": "08:00",
        "heure_fermeture": "21:00",
        "pays": "USA",
        "ville": "Chicago",
    },
]


def seed_more_default_tirages(apps, schema_editor):
    Tirage = apps.get_model("accounts", "Tirage")
    Borlette = apps.get_model("accounts", "Borlette")

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
        ("accounts", "0019_tirage_default_system"),
    ]

    operations = [
        migrations.RunPython(seed_more_default_tirages, reverse_code=migrations.RunPython.noop),
    ]
