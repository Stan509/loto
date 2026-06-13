from __future__ import annotations

from django.db import migrations


def _parse_time(v: str):
    from datetime import datetime

    return datetime.strptime(v, "%H:%M").time()


TEXAS_TIRAGES = [
    {
        "nom": "Texas Morning",
        "code": "TX_MORNING",
        "heure_tirage": "11:00",
        "heure_ouverture": "11:10",
        "heure_fermeture": "10:55",
        "pays": "USA",
        "ville": "Texas",
    },
    {
        "nom": "Texas Day",
        "code": "TX_DAY",
        "heure_tirage": "13:27",
        "heure_ouverture": "13:37",
        "heure_fermeture": "13:22",
        "pays": "USA",
        "ville": "Texas",
    },
    {
        "nom": "Texas Evening",
        "code": "TX_EVENING",
        "heure_tirage": "19:00",
        "heure_ouverture": "19:10",
        "heure_fermeture": "18:55",
        "pays": "USA",
        "ville": "Texas",
    },
    {
        "nom": "Texas Night",
        "code": "TX_NIGHT",
        "heure_tirage": "23:12",
        "heure_ouverture": "23:22",
        "heure_fermeture": "23:07",
        "pays": "USA",
        "ville": "Texas",
    },
]


def seed_texas_tirages(apps, schema_editor):
    Tirage = apps.get_model("accounts", "Tirage")
    Borlette = apps.get_model("accounts", "Borlette")

    for b in Borlette.objects.all().only("id"):
        existing = set(
            Tirage.objects.filter(borlette_id=b.id)
            .exclude(code="")
            .values_list("code", flat=True)
        )

        for spec in TEXAS_TIRAGES:
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
        ("accounts", "0037_alter_auditlog_action"),
    ]

    operations = [
        migrations.RunPython(seed_texas_tirages, reverse_code=migrations.RunPython.noop),
    ]
