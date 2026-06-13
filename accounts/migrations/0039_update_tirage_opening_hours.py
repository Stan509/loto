from __future__ import annotations

from datetime import datetime, timedelta

from django.db import migrations


def _parse_time(v: str):
    return datetime.strptime(v, "%H:%M").time()


def _calculate_opening_hours(heure_tirage_str: str):
    """Calculer les horaires d'ouverture/fermeture basés sur la nouvelle logique:
    - Fermeture: 5 minutes avant le tirage
    - Réouverture: 30 minutes après le tirage
    """
    heure_tirage = datetime.combine(datetime.min, _parse_time(heure_tirage_str))
    heure_fermeture = (heure_tirage - timedelta(minutes=5)).time()
    heure_ouverture = (heure_tirage + timedelta(minutes=30)).time()
    return heure_ouverture, heure_fermeture


# Mapping des codes de tirage vers leurs heures de tirage
TIRAGE_TIMES = {
    "NY_MIDI": "14:15",
    "NY_SOIR": "22:20",
    "FL_MIDI": "13:30",
    "FL_SOIR": "21:45",
    "GA_MIDI": "13:00",
    "GA_5PM": "17:00",
    "GA_8PM": "20:00",
    "GA_NIGHT": "23:59",
    "TN_MATIN": "09:08",
    "TN_MIDI": "12:08",
    "TN_SOIR": "18:08",
    "CHI_MIDI": "12:40",
    "CHI_SOIR": "21:20",
    "TX_MORNING": "11:00",
    "TX_DAY": "13:27",
    "TX_EVENING": "19:00",
    "TX_NIGHT": "23:12",
}


def update_tirage_opening_hours(apps, schema_editor):
    Tirage = apps.get_model("accounts", "Tirage")

    for tirage in Tirage.objects.all():
        if tirage.code and tirage.code in TIRAGE_TIMES:
            heure_tirage_str = TIRAGE_TIMES[tirage.code]
            heure_ouverture, heure_fermeture = _calculate_opening_hours(heure_tirage_str)
            
            tirage.heure_ouverture = heure_ouverture
            tirage.heure_fermeture = heure_fermeture
            tirage.save(update_fields=["heure_ouverture", "heure_fermeture"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0038_seed_texas_tirages"),
    ]

    operations = [
        migrations.RunPython(update_tirage_opening_hours, reverse_code=migrations.RunPython.noop),
    ]
