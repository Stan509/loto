from __future__ import annotations

from datetime import datetime, timedelta

from django.db import migrations


def _parse_time(v: str):
    return datetime.strptime(v, "%H:%M").time()


# Mapping complet des codes de tirage vers leurs nouvelles heures de tirage, fermeture et ouverture
TIRAGE_UPDATES = {
    "NY_MIDI": {
        "nom": "New York Midi",
        "heure_tirage": "14:30",
        "heure_fermeture": "14:25",
        "heure_ouverture": "15:00",
    },
    "NY_SOIR": {
        "nom": "New York Soir",
        "heure_tirage": "22:30",
        "heure_fermeture": "22:25",
        "heure_ouverture": "23:00",
    },
    "FL_MIDI": {
        "nom": "Florida Midi",
        "heure_tirage": "13:30",
        "heure_fermeture": "13:25",
        "heure_ouverture": "14:00",
    },
    "FL_SOIR": {
        "nom": "Florida Soir",
        "heure_tirage": "21:45",
        "heure_fermeture": "21:40",
        "heure_ouverture": "22:15",
    },
    "GA_MIDI": {
        "nom": "Georgia Midi",
        "heure_tirage": "12:29",
        "heure_fermeture": "12:24",
        "heure_ouverture": "12:59",
    },
    "GA_5PM": {
        "nom": "Georgia Evening",
        "heure_tirage": "18:59",
        "heure_fermeture": "18:54",
        "heure_ouverture": "19:29",
        "new_code": "GA_EVENING",
    },
    "GA_8PM": {
        "nom": "Georgia 8PM",
        "heure_tirage": "20:00",
        "heure_fermeture": "19:55",
        "heure_ouverture": "20:30",
    },
    "GA_NIGHT": {
        "nom": "Georgia Night",
        "heure_tirage": "23:34",
        "heure_fermeture": "23:29",
        "heure_ouverture": "00:04",
    },
    "TN_MATIN": {
        "nom": "Tennessee Morning",
        "heure_tirage": "10:28",
        "heure_fermeture": "10:23",
        "heure_ouverture": "10:58",
        "new_code": "TN_MORNING",
    },
    "TN_MIDI": {
        "nom": "Tennessee Midi",
        "heure_tirage": "13:28",
        "heure_fermeture": "13:23",
        "heure_ouverture": "13:58",
    },
    "TN_SOIR": {
        "nom": "Tennessee Evening",
        "heure_tirage": "19:28",
        "heure_fermeture": "19:23",
        "heure_ouverture": "19:58",
        "new_code": "TN_EVENING",
    },
    "CHI_MIDI": {
        "nom": "Illinois Midi",
        "heure_tirage": "13:40",
        "heure_fermeture": "13:35",
        "heure_ouverture": "14:10",
        "new_code": "IL_MIDI",
    },
    "CHI_SOIR": {
        "nom": "Illinois Evening",
        "heure_tirage": "22:22",
        "heure_fermeture": "22:17",
        "heure_ouverture": "22:52",
        "new_code": "IL_EVENING",
    },
    "TX_MORNING": {
        "nom": "Texas Morning",
        "heure_tirage": "11:00",
        "heure_fermeture": "10:55",
        "heure_ouverture": "11:30",
    },
    "TX_DAY": {
        "nom": "Texas Day",
        "heure_tirage": "13:27",
        "heure_fermeture": "13:22",
        "heure_ouverture": "13:57",
    },
    "TX_EVENING": {
        "nom": "Texas Evening",
        "heure_tirage": "19:00",
        "heure_fermeture": "18:55",
        "heure_ouverture": "19:30",
    },
    "TX_NIGHT": {
        "nom": "Texas Night",
        "heure_tirage": "23:12",
        "heure_fermeture": "23:07",
        "heure_ouverture": "23:42",
    },
}


def update_tirage_hours_final(apps, schema_editor):
    Tirage = apps.get_model("accounts", "Tirage")

    for tirage in Tirage.objects.all():
        if tirage.code and tirage.code in TIRAGE_UPDATES:
            update_data = TIRAGE_UPDATES[tirage.code]
            
            # Mettre à jour les horaires
            tirage.heure_tirage = _parse_time(update_data["heure_tirage"])
            tirage.heure_fermeture = _parse_time(update_data["heure_fermeture"])
            tirage.heure_ouverture = _parse_time(update_data["heure_ouverture"])
            
            # Mettre à jour le nom si nécessaire
            tirage.nom = update_data["nom"]
            
            # Mettre à jour le code si nécessaire
            if "new_code" in update_data:
                tirage.code = update_data["new_code"]
            
            tirage.save(update_fields=["heure_tirage", "heure_fermeture", "heure_ouverture", "nom", "code"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0039_update_tirage_opening_hours"),
    ]

    operations = [
        migrations.RunPython(update_tirage_hours_final, reverse_code=migrations.RunPython.noop),
    ]
